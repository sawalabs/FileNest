import os
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from alembic import command
from alembic.config import Config

from backend.app.db.base import Base
from backend.app.db.models import (
    ManagedFolder,
    ScanJob,
    FileRecord,
    ChangePlan,
    ChangePlanItem,
    ExecutionJob,
    OperationLog,
    AuditLog,
)
from backend.app.db.repositories.managed_folder import ManagedFolderRepository
from backend.app.db.repositories.file import FileRepository
from backend.app.db.repositories.audit import AuditLogRepository


@pytest.fixture
def test_db_session(tmp_path):
    """Provides a fresh SQLite test database with foreign keys enabled."""
    db_file = tmp_path / "test.db"
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


def test_managed_folder_unique_root_path(test_db_session):
    repo = ManagedFolderRepository(test_db_session)
    repo.create(name="Documents", root_path="C:/Users/Test/Documents")
    
    with pytest.raises(IntegrityError):
        repo.create(name="Duplicate Docs", root_path="C:/Users/Test/Documents")
    test_db_session.rollback()


def test_foreign_key_enforcement(test_db_session):
    """Verifies that inserting a file without a valid ManagedFolder fails."""
    orphan_file = FileRecord(
        managed_folder_id="non-existent-uuid",
        relative_path="file.txt",
        name="file.txt",
    )
    test_db_session.add(orphan_file)
    with pytest.raises(IntegrityError):
        test_db_session.commit()
    test_db_session.rollback()


def test_file_relative_path_uniqueness(test_db_session):
    folder_repo = ManagedFolderRepository(test_db_session)
    folder = folder_repo.create(name="Work", root_path="D:/Work")

    file_repo = FileRepository(test_db_session)
    file_repo.upsert(
        managed_folder_id=folder.id,
        relative_path="reports/q1.pdf",
        name="q1.pdf",
        size_bytes=1024,
    )

    # Upsert with same relative path updates the record without creating a duplicate
    updated = file_repo.upsert(
        managed_folder_id=folder.id,
        relative_path="reports/q1.pdf",
        name="q1.pdf",
        size_bytes=2048,
    )
    assert updated.size_bytes == 2048
    assert len(file_repo.list_by_folder(folder.id)) == 1


def test_cascade_delete_on_managed_folder(test_db_session):
    folder_repo = ManagedFolderRepository(test_db_session)
    folder = folder_repo.create(name="Project", root_path="D:/Project")

    file_repo = FileRepository(test_db_session)
    file_repo.upsert(
        managed_folder_id=folder.id,
        relative_path="code.py",
        name="code.py",
    )

    # Deleting managed folder cascades to files
    test_db_session.delete(folder)
    test_db_session.commit()

    files = file_repo.list_by_folder(folder.id)
    assert len(files) == 0


def test_audit_log_append_only(test_db_session):
    audit_repo = AuditLogRepository(test_db_session)
    log = audit_repo.record(
        actor_type="user",
        action="folder_registered",
        entity_type="managed_folder",
        entity_id="folder-uuid-1",
        details={"path": "D:/Work"},
    )
    assert log.id is not None
    logs = audit_repo.list_by_entity("managed_folder", "folder-uuid-1")
    assert len(logs) == 1
    assert logs[0].action == "folder_registered"


def test_alembic_migration_lifecycle(tmp_path):
    """Verifies that Alembic can apply migrations cleanly to an empty database and reverse them."""
    test_db_file = tmp_path / "migration_test.db"
    db_url = f"sqlite:///{test_db_file.as_posix()}"

    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # Upgrade to head from empty db
    command.upgrade(alembic_cfg, "head")

    # Verify database file was created
    assert test_db_file.exists()

    # Downgrade to base
    command.downgrade(alembic_cfg, "base")

    # Re-upgrade to head
    command.upgrade(alembic_cfg, "head")
