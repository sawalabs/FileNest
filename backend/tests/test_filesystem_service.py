import os
import pytest
from pathlib import Path
from httpx import AsyncClient

from backend.app.services.filesystem import (
    FilesystemService,
    detect_file_category,
    is_reparse_point_or_symlink,
)
from backend.app.services.managed_folder import ManagedFolderException


@pytest.mark.asyncio
async def test_file_type_and_category_detection():
    assert detect_file_category("report.PDF") == "document"
    assert detect_file_category("photo.jpg") == "image"
    assert detect_file_category("song.MP3") == "audio"
    assert detect_file_category("video.mp4") == "video"
    assert detect_file_category("archive.zip") == "archive"
    assert detect_file_category("script.py") == "code"
    assert detect_file_category("unknown.xyz123") == "other"
    assert detect_file_category(None) == "other"


@pytest.mark.asyncio
async def test_safe_directory_listing_and_metadata(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "BrowseRoot"
    folder_root.mkdir()
    sub_dir = folder_root / "documents"
    sub_dir.mkdir()
    (sub_dir / "invoice.pdf").write_bytes(b"%PDF-1.4 sample content" * 10)
    (folder_root / "notes.txt").write_text("Hello world")

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Browse Root", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Browse root
    browse_res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": ""},
    )
    assert browse_res.status_code == 200
    data = browse_res.json()
    assert data["managed_folder_id"] == folder_id
    assert data["total_directories"] == 1
    assert data["total_files"] == 1

    entries = {e["name"]: e for e in data["entries"]}
    assert "documents" in entries
    assert entries["documents"]["item_type"] == "directory"
    assert "notes.txt" in entries
    assert entries["notes.txt"]["item_type"] == "file"
    assert entries["notes.txt"]["category"] == "document"
    assert entries["notes.txt"]["size_bytes"] > 0

    # 2. Browse subfolder
    sub_res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": "documents"},
    )
    assert sub_res.status_code == 200
    sub_data = sub_res.json()
    assert sub_data["total_files"] == 1
    assert sub_data["entries"][0]["name"] == "invoice.pdf"
    assert sub_data["entries"][0]["category"] == "document"


@pytest.mark.asyncio
async def test_folder_size_calculation_and_aggregation(async_client: AsyncClient, tmp_path: Path):
    summary_root = tmp_path / "SummaryRoot"
    summary_root.mkdir()
    (summary_root / "code.py").write_text("print('hello')")
    (summary_root / "pic.png").write_bytes(b"\x89PNG\r\n\x1a\n" * 20)

    sub = summary_root / "sub"
    sub.mkdir()
    (sub / "doc.pdf").write_bytes(b"%PDF-1.4" * 50)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Summary Root", "root_path": str(summary_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.get(
        "/api/v1/fs/summary",
        params={"folder_id": folder_id, "relative_path": ""},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["file_count"] == 3
    assert data["directory_count"] == 1
    assert data["total_size_bytes"] > 0
    assert data["category_counts"]["code"] == 1
    assert data["category_counts"]["image"] == 1
    assert data["category_counts"]["document"] == 1


@pytest.mark.asyncio
async def test_paths_outside_managed_folder_rejected(async_client: AsyncClient, tmp_path: Path):
    safe_root = tmp_path / "SafeRoot"
    safe_root.mkdir()
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("classified")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Safe Root", "root_path": str(safe_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Traversal attempt via browse
    browse_res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": "../"},
    )
    assert browse_res.status_code == 400
    assert "escapes managed folder root" in browse_res.json()["detail"].lower()

    # Traversal attempt via metadata
    meta_res = await async_client.get(
        "/api/v1/fs/metadata",
        params={"folder_id": folder_id, "relative_path": "../outside.txt"},
    )
    assert meta_res.status_code == 400
    assert "escapes managed folder root" in meta_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_skip_symlinks(async_client: AsyncClient, tmp_path: Path):
    link_root = tmp_path / "LinkRoot"
    link_root.mkdir()
    real_target = tmp_path / "RealTarget"
    real_target.mkdir()
    (real_target / "target_file.txt").write_text("target")

    symlink_path = link_root / "linked_folder"
    try:
        # Create directory symlink or junction if supported
        symlink_path.symlink_to(real_target, target_is_directory=True)
    except (OSError, NotImplementedError):
        # On Windows without SeCreateSymbolicLinkPrivilege, symlink creation might skip
        pass

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Link Root", "root_path": str(link_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    if symlink_path.exists():
        # Traversal into symlink directory is strictly forbidden
        res = await async_client.get(
            "/api/v1/fs/browse",
            params={"folder_id": folder_id, "relative_path": "linked_folder"},
        )
        assert res.status_code == 400
        assert "symlink" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_accessing_disabled_folder_rejected(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "DisableRoot"
    folder_root.mkdir()

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Disable Root", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Disable folder
    await async_client.post(f"/api/v1/folders/{folder_id}/disable")

    # Browse must be rejected
    res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": ""},
    )
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()
