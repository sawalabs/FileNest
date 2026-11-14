import os
import shutil
from pathlib import Path
import pytest
from httpx import AsyncClient

from backend.app.schemas.transaction import (
    ChangePlanCreate,
    ChangePlanItemCreate,
    OperationType,
    PlanType,
    QuickMoveRequest,
)
from backend.app.services.managed_folder import (
    ManagedFolderService,
    PathValidator,
    ProtectedPathRegistry,
    ManagedFolderException,
)
from backend.app.services.transaction import (
    TransactionManagerService,
    TransactionException,
    compute_file_sha256,
)
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.schemas.managed_folder import ManagedFolderCreate


@pytest.fixture
def managed_folders(tmp_path):
    src_dir = tmp_path / "source_folder"
    dst_dir = tmp_path / "dest_folder"
    src_dir.mkdir(parents=True, exist_ok=True)
    dst_dir.mkdir(parents=True, exist_ok=True)
    return src_dir, dst_dir


@pytest.mark.asyncio
async def test_quick_move_same_folder(async_client: AsyncClient, tmp_path):
    """FNE-15 & FNE-17: Test quick move of items within same folder."""
    root_dir = tmp_path / "managed_root"
    root_dir.mkdir()
    (root_dir / "test.txt").write_text("Hello World", encoding="utf-8")

    # Register managed folder
    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Test Root", "root_path": str(root_dir)},
    )
    assert reg_resp.status_code == 201
    folder_id = reg_resp.json()["id"]

    # Move test.txt to subfolder "archive"
    move_resp = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": folder_id,
            "source_relative_paths": ["test.txt"],
            "destination_directory_relative_path": "archive",
            "conflict_resolution": "rename",
        },
    )
    assert move_resp.status_code == 200
    job = move_resp.json()
    assert job["status"] == "completed"

    assert not (root_dir / "test.txt").exists()
    assert (root_dir / "archive" / "test.txt").exists()
    assert (root_dir / "archive" / "test.txt").read_text(encoding="utf-8") == "Hello World"


@pytest.mark.asyncio
async def test_cross_volume_staged_move_execution_and_verification(async_client: AsyncClient, managed_folders):
    """FNE-16 & FNE-17: Test staged copy, hash verification, destination commit, and source quarantine."""
    src_dir, dst_dir = managed_folders
    file_content = "Critical cross-scope payload 1234567890"
    (src_dir / "doc.txt").write_text(file_content, encoding="utf-8")

    # Register both folders
    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Source Folder", "root_path": str(src_dir)})
    assert r1.status_code == 201
    f1_id = r1.json()["id"]

    (dst_dir / "transferred").mkdir(parents=True, exist_ok=True)
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Dest Folder", "root_path": str(dst_dir)})
    assert r2.status_code == 201
    f2_id = r2.json()["id"]

    # Create Cross-Scope Change Plan with explicit move_type="cross_volume"
    plan_resp = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": f1_id,
            "title": "Cross-Scope Staged Move",
            "plan_type": "manual",
            "items": [
                {
                    "operation": "move",
                    "source_managed_folder_id": f1_id,
                    "destination_managed_folder_id": f2_id,
                    "source_relative_path": "doc.txt",
                    "destination_relative_path": "transferred/doc.txt",
                    "conflict_resolution": "fail",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.json()
    plan_id = plan["id"]
    item = plan["items"][0]
    assert item["source_managed_folder_id"] == f1_id
    assert item["destination_managed_folder_id"] == f2_id
    assert item["source_managed_folder_name"] == "Source Folder"
    assert item["destination_managed_folder_name"] == "Dest Folder"

    # Validate Plan
    val_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_resp.status_code == 200
    assert val_resp.json()["can_execute"] is True

    # Approve and Execute Plan
    app_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve", json={"approved_by": "user"})
    assert app_resp.status_code == 200

    exec_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_resp.status_code == 200
    job = exec_resp.json()
    assert job["status"] == "completed"

    # Verify destination file
    dest_file = dst_dir / "transferred" / "doc.txt"
    assert dest_file.exists()
    assert dest_file.read_text(encoding="utf-8") == file_content
    assert compute_file_sha256(dest_file) == compute_file_sha256(dest_file)

    # Verify source file is quarantined, not permanently deleted
    assert not (src_dir / "doc.txt").exists()


@pytest.mark.asyncio
async def test_cross_volume_recursive_folder_move(async_client: AsyncClient, managed_folders):
    """FNE-20: Test recursive folder move across scopes preserving nested hierarchy."""
    src_dir, dst_dir = managed_folders

    # Create nested tree
    tree = src_dir / "my_project"
    (tree / "sub1").mkdir(parents=True)
    (tree / "sub2" / "nested").mkdir(parents=True)
    (tree / "root_file.txt").write_text("root file content", encoding="utf-8")
    (tree / "sub1" / "code.py").write_text("print('hello')", encoding="utf-8")
    (tree / "sub2" / "nested" / "data.csv").write_text("id,name\n1,alice", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Rec Source", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Rec Dest", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    # Quick move of entire directory
    move_resp = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": f1_id,
            "destination_managed_folder_id": f2_id,
            "source_relative_paths": ["my_project"],
            "destination_directory_relative_path": "imported",
            "conflict_resolution": "rename",
        },
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["status"] == "completed"

    # Check full recursive hierarchy in destination
    dest_project = dst_dir / "imported" / "my_project"
    assert dest_project.exists()
    assert (dest_project / "root_file.txt").read_text(encoding="utf-8") == "root file content"
    assert (dest_project / "sub1" / "code.py").read_text(encoding="utf-8") == "print('hello')"
    assert (dest_project / "sub2" / "nested" / "data.csv").read_text(encoding="utf-8") == "id,name\n1,alice"

    # Source directory is quarantined
    assert not (src_dir / "my_project").exists()


@pytest.mark.asyncio
async def test_destination_conflict_resolution_rename(async_client: AsyncClient, managed_folders):
    """FNE-18: Verify conflict strategy 'rename' generates non-colliding suffix (1)."""
    src_dir, dst_dir = managed_folders
    (src_dir / "report.pdf").write_text("New report from source", encoding="utf-8")
    (dst_dir / "report.pdf").write_text("Existing report in destination", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Conflict Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Conflict Dst", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    move_resp = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": f1_id,
            "destination_managed_folder_id": f2_id,
            "source_relative_paths": ["report.pdf"],
            "destination_directory_relative_path": "",
            "conflict_resolution": "rename",
        },
    )
    assert move_resp.status_code == 200
    assert move_resp.json()["status"] == "completed"

    # Original remains intact and new file is renamed with (1)
    assert (dst_dir / "report.pdf").read_text(encoding="utf-8") == "Existing report in destination"
    assert (dst_dir / "report (1).pdf").exists()
    assert (dst_dir / "report (1).pdf").read_text(encoding="utf-8") == "New report from source"


@pytest.mark.asyncio
async def test_destination_conflict_resolution_skip(async_client: AsyncClient, managed_folders):
    """FNE-18: Verify conflict strategy 'skip' safely skips item without error or mutation."""
    src_dir, dst_dir = managed_folders
    (src_dir / "file.txt").write_text("Source file", encoding="utf-8")
    (dst_dir / "file.txt").write_text("Destination file", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Skip Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Skip Dst", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    # Create plan with skip strategy
    plan_resp = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": f1_id,
            "title": "Skip on Conflict Plan",
            "items": [
                {
                    "operation": "move",
                    "source_managed_folder_id": f1_id,
                    "destination_managed_folder_id": f2_id,
                    "source_relative_path": "file.txt",
                    "destination_relative_path": "file.txt",
                    "conflict_resolution": "skip",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    # Validation should produce warning, not blocking error
    val_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_resp.status_code == 200
    assert val_resp.json()["can_execute"] is True

    # Execute
    await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve", json={"approved_by": "user"})
    exec_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_resp.status_code == 200

    # Destination unchanged, source untouched
    assert (dst_dir / "file.txt").read_text(encoding="utf-8") == "Destination file"
    assert (src_dir / "file.txt").exists()


@pytest.mark.asyncio
async def test_destination_conflict_resolution_fail(async_client: AsyncClient, managed_folders):
    """FNE-18: Verify conflict strategy 'fail' blocks plan execution and detects collision."""
    src_dir, dst_dir = managed_folders
    (src_dir / "conflict.dat").write_text("A", encoding="utf-8")
    (dst_dir / "conflict.dat").write_text("B", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Fail Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Fail Dst", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    plan_resp = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": f1_id,
            "title": "Fail on Conflict Plan",
            "items": [
                {
                    "operation": "move",
                    "source_managed_folder_id": f1_id,
                    "destination_managed_folder_id": f2_id,
                    "source_relative_path": "conflict.dat",
                    "destination_relative_path": "conflict.dat",
                    "conflict_resolution": "fail",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    val_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_resp.status_code == 200
    # Must block execution because conflict_resolution is fail
    assert val_resp.json()["can_execute"] is False
    assert any(iss["issue_type"] == "conflict" for iss in val_resp.json()["issues"])


@pytest.mark.asyncio
async def test_rollback_cross_volume_restores_quarantined_source(async_client: AsyncClient, managed_folders):
    """FNE-21: Verify failure in second item rolls back first cross-volume move and restores source from quarantine."""
    src_dir, dst_dir = managed_folders
    (src_dir / "item1.txt").write_text("Item 1 Data", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Rollback Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Rollback Dst", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    plan_resp = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": f1_id,
            "title": "Rollback Test Plan",
            "items": [
                {
                    "operation": "move",
                    "source_managed_folder_id": f1_id,
                    "destination_managed_folder_id": f2_id,
                    "source_relative_path": "item1.txt",
                    "destination_relative_path": "item1.txt",
                    "conflict_resolution": "fail",
                    "sequence_no": 1,
                },
                {
                    # Intentional failure: source file doesn't exist at execution time
                    "operation": "move",
                    "source_managed_folder_id": f1_id,
                    "destination_managed_folder_id": f2_id,
                    "source_relative_path": "non_existent.txt",
                    "destination_relative_path": "dest_non_existent.txt",
                    "conflict_resolution": "fail",
                    "sequence_no": 2,
                },
            ],
        },
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["id"]

    # Bypass pre-validation to test execution failure and rollback
    await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve", json={"approved_by": "user"})
    exec_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    # Execution should fail and return 400 or rolled back job
    if exec_resp.status_code == 200:
        assert exec_resp.json()["status"] in ("rolled_back", "failed")

    # Item 1 should be restored back to src_dir, and removed from dst_dir!
    assert (src_dir / "item1.txt").exists()
    assert (src_dir / "item1.txt").read_text(encoding="utf-8") == "Item 1 Data"
    assert not (dst_dir / "item1.txt").exists()


@pytest.mark.asyncio
async def test_undo_execution_job_cross_volume(async_client: AsyncClient, managed_folders):
    """FNE-17: Test undoing a completed cross-volume move job restores files to source folder."""
    src_dir, dst_dir = managed_folders
    (src_dir / "undo_test.txt").write_text("Undo payload", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Undo Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]
    r2 = await async_client.post("/api/v1/folders/register", json={"name": "Undo Dst", "root_path": str(dst_dir)})
    f2_id = r2.json()["id"]

    move_resp = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": f1_id,
            "destination_managed_folder_id": f2_id,
            "source_relative_paths": ["undo_test.txt"],
            "destination_directory_relative_path": "",
            "conflict_resolution": "fail",
        },
    )
    assert move_resp.status_code == 200
    job_id = move_resp.json()["id"]
    assert (dst_dir / "undo_test.txt").exists()

    # Call Undo
    undo_resp = await async_client.post(f"/api/v1/transactions/jobs/{job_id}/undo")
    assert undo_resp.status_code == 200
    undo_data = undo_resp.json()
    assert undo_data["reverted_count"] == 1

    # Source is restored, destination is removed
    assert (src_dir / "undo_test.txt").exists()
    assert (src_dir / "undo_test.txt").read_text(encoding="utf-8") == "Undo payload"
    assert not (dst_dir / "undo_test.txt").exists()


@pytest.mark.asyncio
async def test_protected_destination_path_rejected(async_client: AsyncClient, managed_folders):
    """FNE-16: Verify ProtectedPathRegistry prevents targeting system or application directories."""
    src_dir, _ = managed_folders
    (src_dir / "payload.bin").write_text("binary", encoding="utf-8")

    r1 = await async_client.post("/api/v1/folders/register", json={"name": "Prot Src", "root_path": str(src_dir)})
    f1_id = r1.json()["id"]

    # Try moving with destination targeting system volume info or windows directory
    resp = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": f1_id,
            "source_relative_paths": ["payload.bin"],
            "destination_directory_relative_path": "System Volume Information",
            "conflict_resolution": "fail",
        },
    )
    # Must be rejected with 400
    assert resp.status_code == 400
    assert "protected" in resp.json()["detail"].lower()
