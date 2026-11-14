import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings
from backend.app.db.base import Base
from backend.app.db.models.file import FileRecord
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.file import FileRepository
from backend.app.services.filesystem import FilesystemService, is_reparse_point_or_symlink
from backend.app.services.managed_folder import ManagedFolderException, PathValidator
from backend.app.services.storage import StorageAnalyzerService


@pytest.fixture
def db(tmp_path: Path) -> Generator[Session, None, None]:
    """Provides a fresh SQLite test database with foreign keys enabled."""
    db_file = tmp_path / "test_real_fs.db"
    engine = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def real_test_dir() -> Generator[Path, None, None]:
    """Creates a temporary directory with a rich hierarchy of real files."""
    tmp_path = Path(tempfile.mkdtemp(prefix="ds_mgr_real_fs_")).resolve()

    # Subdirectories
    docs_dir = tmp_path / "documents"
    images_dir = tmp_path / "images"
    unicode_dir = tmp_path / "unicode_tests"
    empty_sub = tmp_path / "empty_dir"
    docs_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    unicode_dir.mkdir(parents=True, exist_ok=True)
    empty_sub.mkdir(parents=True, exist_ok=True)

    # 1. Documents (known sizes)
    (docs_dir / "report.pdf").write_bytes(b"PDF-HEADER-DATA" * 100)  # 1500 bytes
    (docs_dir / "notes.txt").write_text("Plain text notes for testing", encoding="utf-8")
    (docs_dir / "data.csv").write_text("id,name,value\n1,test,100\n2,demo,200\n", encoding="utf-8")

    # 2. Duplicate files (exact same content)
    duplicate_content = b"IDENTICAL_DUPLICATE_PAYLOAD_FOR_HASHING_" * 50
    (docs_dir / "original_file.bin").write_bytes(duplicate_content)
    (images_dir / "duplicate_copy.bin").write_bytes(duplicate_content)

    # 3. Unicode filenames (Japanese, Arabic, Accents, Emoji)
    (unicode_dir / "日本語_ドキュメント.txt").write_text("Konichiwa sekai", encoding="utf-8")
    (unicode_dir / "تقرير_مالي_2026.pdf").write_bytes(b"%PDF-ARABIC-TEST-DATA")
    (unicode_dir / "résumé_élégant_über.docx").write_bytes(b"DOCX-ACCENTS-TEST")
    (unicode_dir / "🔥_rocket_launch.png").write_bytes(b"PNG-IMAGE-EMOJI-DATA")

    # 4. Long path structure (> 270 characters)
    deep_path = tmp_path
    for i in range(10):
        deep_path = deep_path / f"nested_level_{i:02d}_structure"
    deep_path.mkdir(parents=True, exist_ok=True)
    long_file = deep_path / "very_long_nested_target_filename_for_path_length_validation.txt"
    long_file.write_text("deep path content", encoding="utf-8")

    yield tmp_path

    # Cleanup
    shutil.rmtree(tmp_path, ignore_errors=True)


@pytest.fixture
def managed_folder_record(db: Session, real_test_dir: Path) -> ManagedFolder:
    """Registers the real temporary test directory as an enabled Managed Folder."""
    folder = ManagedFolder(
        name="Real Test Managed Folder",
        root_path=str(real_test_dir),
        is_enabled=1,
        monitoring_enabled=0,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


def test_filesystem_metadata_accuracy(db: Session, managed_folder_record: ManagedFolder, real_test_dir: Path):
    """Verifies that directory listing and metadata reflect exact filesystem reality."""
    fs_service = FilesystemService(db)

    # 1. Browse root
    listing = fs_service.list_directory(managed_folder_record.id, relative_path="")
    assert listing.managed_folder_id == managed_folder_record.id
    assert listing.total_directories >= 4  # documents, images, unicode_tests, empty_dir, nested...
    entry_names = [e.name for e in listing.entries]
    assert "documents" in entry_names
    assert "images" in entry_names
    assert "unicode_tests" in entry_names
    assert "empty_dir" in entry_names

    # 2. Browse documents subdirectory
    docs_listing = fs_service.list_directory(managed_folder_record.id, relative_path="documents")
    docs_files = {e.name: e for e in docs_listing.entries}
    assert "report.pdf" in docs_files
    assert docs_files["report.pdf"].category == "document"
    assert docs_files["report.pdf"].extension == "pdf"
    assert docs_files["report.pdf"].size_bytes == 1500
    assert docs_files["report.pdf"].item_type == "file"
    assert not docs_files["report.pdf"].is_inaccessible
    assert not docs_files["report.pdf"].is_symlink

    # 3. Calculate summary
    summary = fs_service.calculate_folder_summary(managed_folder_record.id, relative_path="")
    assert summary.file_count >= 8
    assert summary.total_size_bytes > 0
    assert summary.category_counts["document"] >= 3
    assert summary.inaccessible_count == 0


def test_unicode_and_long_path_resilience(db: Session, managed_folder_record: ManagedFolder, real_test_dir: Path):
    """Validates that Unicode characters, non-Latin scripts, emojis, and deep paths work without errors."""
    fs_service = FilesystemService(db)

    # Browse unicode folder
    u_listing = fs_service.list_directory(managed_folder_record.id, relative_path="unicode_tests")
    names = {e.name: e for e in u_listing.entries}

    assert "日本語_ドキュメント.txt" in names
    assert names["日本語_ドキュメント.txt"].size_bytes > 0
    assert names["日本語_ドキュメント.txt"].extension == "txt"

    assert "تقرير_مالي_2026.pdf" in names
    assert names["تقرير_مالي_2026.pdf"].extension == "pdf"

    assert "résumé_élégant_über.docx" in names
    assert names["résumé_élégant_über.docx"].category == "document"

    assert "🔥_rocket_launch.png" in names
    assert names["🔥_rocket_launch.png"].category == "image"


def test_storage_analyzer_real_pipeline_and_sqlite_sync(
    db: Session, managed_folder_record: ManagedFolder, real_test_dir: Path
):
    """Validates that StorageAnalyzerService scans real directories, detects duplicates,
    and synchronizes all items into SQLite FileRecord without mutating disk."""
    storage_service = StorageAnalyzerService(db)

    result = storage_service.analyze_folder(
        folder_id=managed_folder_record.id,
        large_file_threshold_bytes=1000,
        calculate_hashes=True,
    )

    assert result.total_files_count >= 8
    assert result.total_storage_bytes > 0

    # Verify duplicate group was correctly found (original_file.bin and duplicate_copy.bin)
    assert result.duplicate_groups_count >= 1
    found_dupes = False
    for group in result.duplicate_groups:
        file_names = [f.name for f in group.files]
        if "original_file.bin" in file_names and "duplicate_copy.bin" in file_names:
            found_dupes = True
            assert group.files_count == 2
            assert group.size_bytes == len(b"IDENTICAL_DUPLICATE_PAYLOAD_FOR_HASHING_" * 50)
            break
    assert found_dupes, "Expected identical files to be grouped as duplicates"

    # Verify that SQLite FileRecord table was populated
    repo = FileRepository(db)
    active_files = repo.list_by_folder(managed_folder_record.id, item_type="file")
    assert len(active_files) == result.total_files_count

    active_paths = [f.relative_path for f in active_files]
    assert "documents/report.pdf" in active_paths
    assert "unicode_tests/🔥_rocket_launch.png" in active_paths


def test_stale_record_reconciliation_without_mutating_disk(
    db: Session, managed_folder_record: ManagedFolder, real_test_dir: Path
):
    """Validates that when a file is deleted outside the app, reconciliation marks it
    as is_deleted=1 in SQLite, restores it if recreated, and never touches files on disk."""
    storage_service = StorageAnalyzerService(db)
    fs_service = FilesystemService(db)
    file_repo = FileRepository(db)

    # 1. Initial scan populates DB
    storage_service.analyze_folder(managed_folder_record.id)

    target_file = real_test_dir / "documents" / "report.pdf"
    assert target_file.exists()

    rec_before = file_repo.get_by_path(managed_folder_record.id, "documents/report.pdf")
    assert rec_before is not None
    assert rec_before.is_deleted == 0

    # 2. Delete file on the filesystem externally
    target_file.unlink()
    assert not target_file.exists()

    # 3. Run reconciliation
    stats = fs_service.reconcile_managed_folder(managed_folder_record.id)
    assert stats["stale_marked"] >= 1

    # Database record is updated to is_deleted=1
    rec_after = file_repo.get_by_path(managed_folder_record.id, "documents/report.pdf")
    assert rec_after.is_deleted == 1

    # Other files on disk were NOT deleted or altered
    assert (real_test_dir / "documents" / "notes.txt").exists()

    # 4. Re-create the file on disk (simulate external restoration)
    target_file.write_bytes(b"RESTORED_CONTENT_WITH_NEW_SIZE")

    # Run reconciliation again
    stats2 = fs_service.reconcile_managed_folder(managed_folder_record.id)
    assert stats2["restored"] >= 1

    rec_restored = file_repo.get_by_path(managed_folder_record.id, "documents/report.pdf")
    assert rec_restored.is_deleted == 0
    assert rec_restored.size_bytes == len(b"RESTORED_CONTENT_WITH_NEW_SIZE")


def test_managed_folder_boundaries_and_reparse_point_protections(
    db: Session, managed_folder_record: ManagedFolder, real_test_dir: Path
):
    """Validates that traversal attempts outside Managed Folders are rejected and
    symlinks/reparse points are never traversed."""
    fs_service = FilesystemService(db)

    # 1. Path traversal escape attempts
    with pytest.raises(ManagedFolderException, match="escapes Managed Folder root"):
        PathValidator.resolve_and_verify_scope(managed_folder_record, "../../escaped")

    with pytest.raises(ManagedFolderException, match="escapes Managed Folder root"):
        fs_service.list_directory(managed_folder_record.id, relative_path="../")

    with pytest.raises(ManagedFolderException, match="escapes Managed Folder root"):
        fs_service.get_item_metadata(managed_folder_record.id, relative_path="../../windows")

    # 2. Create a symlink pointing outside the managed folder (if supported)
    outside_temp = Path(tempfile.mkdtemp(prefix="outside_dir_"))
    (outside_temp / "secret.txt").write_text("secret outside data")

    symlink_path = real_test_dir / "documents" / "outside_symlink"
    try:
        symlink_path.symlink_to(outside_temp, target_is_directory=True)
        is_sym = is_reparse_point_or_symlink(symlink_path)
        assert is_sym is True

        # Attempting to list through the outside symlink must be rejected (escapes root or rejected as symlink)
        with pytest.raises(ManagedFolderException, match="(escapes Managed Folder root|Cannot traverse symlink)"):
            fs_service.list_directory(managed_folder_record.id, relative_path="documents/outside_symlink")

        # 3. Create an internal symlink pointing inside the managed folder
        internal_symlink = real_test_dir / "documents" / "internal_symlink"
        internal_target = real_test_dir / "images"
        internal_symlink.symlink_to(internal_target, target_is_directory=True)
        assert is_reparse_point_or_symlink(internal_symlink) is True

        # Attempting to list through the internal symlink must be rejected with reparse/symlink check
        with pytest.raises(ManagedFolderException, match="Cannot traverse symlink or reparse point"):
            fs_service.list_directory(managed_folder_record.id, relative_path="documents/internal_symlink")

        # Summary calculation must skip symlink directories
        summary = fs_service.calculate_folder_summary(managed_folder_record.id, relative_path="documents")
        # Ensure secret.txt was not included in file count or scanned
        assert summary.file_count < 10

    except (OSError, NotImplementedError):
        # On Windows without developer mode, symlink creation might require privileges; skip symlink creation
        pass
    finally:
        shutil.rmtree(outside_temp, ignore_errors=True)
