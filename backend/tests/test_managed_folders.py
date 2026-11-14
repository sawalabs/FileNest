import pytest
from pathlib import Path
from httpx import AsyncClient

from backend.app.services.managed_folder import PathValidator, ManagedFolderException
from backend.app.db.models.scan_job import ScanJob
from backend.app.db.models.managed_folder import ManagedFolder


@pytest.mark.asyncio
async def test_register_managed_folder_success(async_client: AsyncClient, tmp_path: Path):
    target_dir = tmp_path / "MyDocuments"
    target_dir.mkdir()

    response = await async_client.post(
        "/api/v1/folders/register",
        json={
            "name": "My Documents",
            "root_path": str(target_dir),
            "monitoring_enabled": False,
            "scan_on_startup": False,
            "exclude_patterns": ["*.tmp", ".git/*"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "My Documents"
    assert data["is_enabled"] is True
    assert data["monitoring_enabled"] is False
    assert data["exclude_patterns"] == ["*.tmp", ".git/*"]
    assert data["last_scanned_at"] is None


@pytest.mark.asyncio
async def test_register_duplicate_and_nested_rejected(async_client: AsyncClient, tmp_path: Path):
    parent_dir = tmp_path / "ParentWork"
    parent_dir.mkdir()
    child_dir = parent_dir / "ChildProject"
    child_dir.mkdir()

    # Register parent
    res1 = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Parent", "root_path": str(parent_dir)},
    )
    assert res1.status_code == 201

    # Exact duplicate rejected
    res_dup = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Parent Dup", "root_path": str(parent_dir)},
    )
    assert res_dup.status_code == 400
    assert "already registered" in res_dup.json()["detail"].lower()

    # Nested child rejected
    res_nested = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Child", "root_path": str(child_dir)},
    )
    assert res_nested.status_code == 400
    assert "nested" in res_nested.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_non_existent_and_protected_paths_rejected(async_client: AsyncClient):
    # Non-existent
    res_none = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Fake", "root_path": "Z:/NonExistentPath/123456"},
    )
    assert res_none.status_code == 400
    assert "does not exist" in res_none.json()["detail"].lower()

    # Protected Windows folder
    res_win = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Windows System", "root_path": "C:/Windows"},
    )
    assert res_win.status_code == 400
    assert "protected" in res_win.json()["detail"].lower()


@pytest.mark.asyncio
async def test_registration_does_not_trigger_automatic_scan(async_client: AsyncClient, tmp_path: Path):
    """Verifies acceptance criteria: Registration does not trigger an automatic recursive scan."""
    test_dir = tmp_path / "NoAutoScan"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_text("content")

    res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "No Auto Scan", "root_path": str(test_dir)},
    )
    assert res.status_code == 201
    folder_id = res.json()["id"]

    # Verify no scan job was created
    res_folder = await async_client.get(f"/api/v1/folders/{folder_id}")
    assert res_folder.status_code == 200
    assert res_folder.json()["last_scanned_at"] is None


@pytest.mark.asyncio
async def test_scope_enforcement_and_traversal_rejection(tmp_path: Path):
    root_dir = tmp_path / "ScopeRoot"
    root_dir.mkdir()
    (root_dir / "inside.txt").write_text("hello")

    folder = ManagedFolder(
        id="folder-uuid",
        name="Scope Root",
        root_path=str(root_dir.resolve()),
        is_enabled=1,
    )

    # Valid relative path inside root
    resolved = PathValidator.resolve_and_verify_scope(folder, "inside.txt")
    assert resolved == (root_dir / "inside.txt").resolve()

    # Traversal attempt escaping root must be rejected
    with pytest.raises(ManagedFolderException) as excinfo:
        PathValidator.resolve_and_verify_scope(folder, "../outside.txt")
    assert "escapes managed folder root" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_folder_update_disable_and_unregister(async_client: AsyncClient, tmp_path: Path):
    test_dir = tmp_path / "LifecycleFolder"
    test_dir.mkdir()
    sample_file = test_dir / "important.docx"
    sample_file.write_text("data")

    # 1. Register
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Lifecycle", "root_path": str(test_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 2. Update
    patch_res = await async_client.patch(
        f"/api/v1/folders/{folder_id}",
        json={"name": "Lifecycle Renamed", "monitoring_enabled": True},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Lifecycle Renamed"
    assert patch_res.json()["monitoring_enabled"] is True

    # 3. Disable
    disable_res = await async_client.post(f"/api/v1/folders/{folder_id}/disable")
    assert disable_res.status_code == 200
    assert disable_res.json()["is_enabled"] is False

    # 4. Enable
    enable_res = await async_client.post(f"/api/v1/folders/{folder_id}/enable")
    assert enable_res.status_code == 200
    assert enable_res.json()["is_enabled"] is True

    # 5. Unregister (delete)
    unreg_res = await async_client.delete(f"/api/v1/folders/{folder_id}")
    assert unreg_res.status_code == 200
    assert unreg_res.json()["is_enabled"] is False

    # Verify physical files remain on disk!
    assert sample_file.exists()
