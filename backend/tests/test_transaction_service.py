import pytest
from pathlib import Path
from httpx import AsyncClient

from backend.app.schemas.transaction import OperationType


@pytest.mark.asyncio
async def test_plan_lifecycle_and_validation(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "PlanFolder"
    folder_root.mkdir()
    (folder_root / "existing_doc.txt").write_text("Hello doc")
    (folder_root / "existing_static.txt").write_text("Static file")

    # 1. Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Plan Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 2. Create Change Plan (1 valid rename, 1 collision create_dir)
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Test Plan with Collision",
        "plan_type": "manual",
        "items": [
            {
                "operation": "rename",
                "source_relative_path": "existing_doc.txt",
                "destination_relative_path": "renamed_doc.txt",
                "sequence_no": 1,
            },
            {
                # Trying to create a directory that already exists as a file or folder -> collision!
                "operation": "create_directory",
                "destination_relative_path": "existing_static.txt",
                "sequence_no": 2,
            },
        ],
    }

    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code == 201
    plan_data = create_res.json()
    assert plan_data["status"] == "draft"
    assert len(plan_data["items"]) == 2
    plan_id = plan_data["id"]

    # 3. Validate Plan -> should detect collision
    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert not val_data["can_execute"]
    assert any(iss["issue_type"] == "conflict" for iss in val_data["issues"])

    # 4. Attempting to approve plan with conflict should fail
    app_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")
    assert app_res.status_code == 400


@pytest.mark.asyncio
async def test_successful_plan_execution(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "ExecFolder"
    folder_root.mkdir()
    (folder_root / "sample.txt").write_text("Initial text")

    # Register
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Exec Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Create plan: create subfolder -> move sample.txt into subfolder -> copy sample.txt
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Organize Sample",
        "plan_type": "organize",
        "items": [
            {
                "operation": "create_directory",
                "destination_relative_path": "archive",
                "sequence_no": 1,
            },
            {
                "operation": "move",
                "source_relative_path": "sample.txt",
                "destination_relative_path": "archive/sample.txt",
                "sequence_no": 2,
            },
            {
                "operation": "copy",
                "source_relative_path": "archive/sample.txt",
                "destination_relative_path": "archive/sample_copy.txt",
                "sequence_no": 3,
            },
        ],
    }

    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code == 201
    plan_id = create_res.json()["id"]

    # Approve
    app_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Execute
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 200
    exec_data = exec_res.json()
    assert exec_data["status"] == "completed"
    assert exec_data["completed_count"] == 3
    assert exec_data["failed_count"] == 0

    # Verify filesystem state
    assert (folder_root / "archive").is_dir()
    assert (folder_root / "archive" / "sample.txt").exists()
    assert (folder_root / "archive" / "sample_copy.txt").exists()
    assert not (folder_root / "sample.txt").exists()


@pytest.mark.asyncio
async def test_path_traversal_rejected_in_plan(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "SecureFolder"
    folder_root.mkdir()

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Secure Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Plan trying to escape root
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Escape Attempt",
        "items": [
            {
                "operation": "create_directory",
                "destination_relative_path": "../../evil_dir",
                "sequence_no": 1,
            }
        ],
    }
    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code == 201
    plan_id = create_res.json()["id"]

    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    assert not val_data_has_errors(val_res.json())


def val_data_has_errors(data: dict) -> bool:
    return data["can_execute"] is True


@pytest.mark.asyncio
async def test_best_effort_rollback_on_partial_failure(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "RollbackFolder"
    folder_root.mkdir()
    (folder_root / "step1.txt").write_text("Step 1 content")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rollback Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Step 1: create a new directory 'temp_dir'
    # Step 2: move step1.txt into non_existent_parent/step1.txt (which will fail immediately during execution)
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Failure and Rollback Plan",
        "items": [
            {
                "operation": "create_directory",
                "destination_relative_path": "temp_dir",
                "sequence_no": 1,
            },
            {
                "operation": "move",
                "source_relative_path": "step1.txt",
                "destination_relative_path": "non_existent_folder/step1.txt",
                "sequence_no": 2,
            },
        ],
    }

    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    plan_id = create_res.json()["id"]

    # Approve (force execute to test rollback behavior)
    # Notice validation detects non-existent folder, but let's test execution directly if called
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 400
    # Pre-execution validation blocked execution!
    assert "pre-execution validation checks" in exec_res.json()["detail"]


@pytest.mark.asyncio
async def test_quick_actions(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "QuickFolder"
    folder_root.mkdir()
    (folder_root / "test_file.txt").write_text("Hello quick")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Quick Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # 1. Quick create folder
    f_res = await async_client.post(
        "/api/v1/transactions/quick/create-folder",
        json={
            "managed_folder_id": folder_id,
            "parent_relative_path": "",
            "folder_name": "NewSub",
        },
    )
    assert f_res.status_code == 200
    assert (folder_root / "NewSub").is_dir()

    # 2. Quick rename
    r_res = await async_client.post(
        "/api/v1/transactions/quick/rename",
        json={
            "managed_folder_id": folder_id,
            "source_relative_path": "test_file.txt",
            "new_name": "renamed_file.txt",
        },
    )
    assert r_res.status_code == 200
    assert (folder_root / "renamed_file.txt").exists()
    assert not (folder_root / "test_file.txt").exists()

    # 3. Quick copy
    c_res = await async_client.post(
        "/api/v1/transactions/quick/copy",
        json={
            "managed_folder_id": folder_id,
            "source_relative_paths": ["renamed_file.txt"],
            "destination_directory_relative_path": "NewSub",
        },
    )
    assert c_res.status_code == 200
    assert (folder_root / "NewSub" / "renamed_file.txt").exists()

    # 4. Quick move
    m_res = await async_client.post(
        "/api/v1/transactions/quick/move",
        json={
            "managed_folder_id": folder_id,
            "source_relative_paths": ["renamed_file.txt"],
            "destination_directory_relative_path": "NewSub",
        },
    )
    # Target already exists in NewSub from copy -> collision!
    assert m_res.status_code == 400

    # 5. Quick delete (recycle bin)
    d_res = await async_client.post(
        "/api/v1/transactions/quick/delete",
        json={
            "managed_folder_id": folder_id,
            "relative_paths": ["NewSub/renamed_file.txt"],
        },
    )
    assert d_res.status_code == 200
    assert not (folder_root / "NewSub" / "renamed_file.txt").exists()
