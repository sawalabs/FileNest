import os
from pathlib import Path
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_approve_and_execute_strict_separation(async_client: AsyncClient, tmp_path: Path):
    """Verifies that approve and execute are separate actions, and execution is strictly
    blocked unless the plan is explicitly approved."""
    folder_root = tmp_path / "strict_sep_test"
    folder_root.mkdir()
    sample_file = folder_root / "document.txt"
    sample_file.write_text("Confidential Content")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Strict Sep Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Create a draft change plan
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Strict Move Plan",
        "plan_type": "manual",
        "items": [
            {
                "operation": "move",
                "source_relative_path": "document.txt",
                "destination_relative_path": "archive_document.txt",
                "sequence_no": 1,
            }
        ],
    }
    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code == 201
    plan_id = create_res.json()["id"]
    assert create_res.json()["status"] == "draft"

    # 2. Attempt execution while still in draft: MUST BE REJECTED
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 400
    assert "Plan must be approved before execution" in exec_res.json()["detail"]

    # Verify document.txt still in place
    assert sample_file.exists()
    assert not (folder_root / "archive_document.txt").exists()

    # 3. Explicitly approve the plan
    approve_res = await async_client.post(
        f"/api/v1/transactions/plans/{plan_id}/approve",
        json={"approved_by": "security_admin"},
    )
    assert approve_res.status_code == 200
    assert approve_res.json()["status"] == "approved"
    assert approve_res.json()["approved_by"] == "security_admin"

    # 4. Now execute the approved plan
    exec_ok_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_ok_res.status_code == 200
    assert exec_ok_res.json()["status"] == "completed"

    # Verify disk mutation completed
    assert not sample_file.exists()
    assert (folder_root / "archive_document.txt").exists()


@pytest.mark.asyncio
async def test_prevent_execution_of_conflicting_plans(async_client: AsyncClient, tmp_path: Path):
    """Verifies that plans with conflicts (e.g. destination collision) cannot be executed,
    and validation errors are surfaced clearly."""
    folder_root = tmp_path / "conflict_test"
    folder_root.mkdir()
    (folder_root / "source.txt").write_text("Source Data")
    (folder_root / "existing_dest.txt").write_text("Already Present")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Conflict Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Plan with destination collision
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Colliding Move Plan",
        "plan_type": "manual",
        "items": [
            {
                "operation": "move",
                "source_relative_path": "source.txt",
                "destination_relative_path": "existing_dest.txt",
                "sequence_no": 1,
            }
        ],
    }
    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    plan_id = create_res.json()["id"]

    # 1. Validation check surfaces collision
    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert not val_data["can_execute"]
    assert any("Destination collision" in iss["message"] for iss in val_data["issues"])

    # 2. Approval is blocked
    app_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")
    assert app_res.status_code == 400
    assert "Cannot approve plan with" in app_res.json()["detail"]

    # 3. Execution is blocked
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 400


@pytest.mark.asyncio
async def test_audit_and_history_persistence_after_file_deletion(
    async_client: AsyncClient, tmp_path: Path
):
    """Ensures audit records, execution logs, and historical transactions persist even
    after related physical files are deleted or disappear from disk."""
    folder_root = tmp_path / "persistence_test"
    folder_root.mkdir()
    file_a = folder_root / "important_file.txt"
    file_a.write_text("Permanent Data")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Persistence Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Create, approve, and execute a plan
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Audit Persistence Plan",
        "plan_type": "organize",
        "items": [
            {
                "operation": "rename",
                "source_relative_path": "important_file.txt",
                "destination_relative_path": "renamed_file.txt",
                "sequence_no": 1,
            }
        ],
    }
    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    plan_id = create_res.json()["id"]

    await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 200
    job_id = exec_res.json()["id"]

    # Verify file is renamed on disk
    renamed_file = folder_root / "renamed_file.txt"
    assert renamed_file.exists()

    # NOW: Physically delete the renamed file and directory completely from disk!
    renamed_file.unlink()
    assert not renamed_file.exists()

    # Query Audit Logs: Audit log MUST STILL EXIST with complete details
    audit_res = await async_client.get(
        "/api/v1/history/audit-logs",
        params={"category": "plans_approvals"},
    )
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    assert audit_data["total"] > 0
    plan_audit_found = any(
        log["entity_id"] == plan_id for log in audit_data["items"]
    )
    assert plan_audit_found

    # Query Executions: Execution job & operation snapshot logs MUST STILL EXIST
    exec_history_res = await async_client.get(
        "/api/v1/history/executions",
        params={"status": "completed"},
    )
    assert exec_history_res.status_code == 200
    history_data = exec_history_res.json()
    job_record = next((j for j in history_data["items"] if j["id"] == job_id), None)
    assert job_record is not None
    assert job_record["status"] == "completed"
    assert len(job_record["operation_logs"]) == 1
    assert job_record["operation_logs"][0]["source_path_snapshot"] == "important_file.txt"
    assert job_record["operation_logs"][0]["destination_path_snapshot"] == "renamed_file.txt"


@pytest.mark.asyncio
async def test_history_stats_and_export(async_client: AsyncClient, tmp_path: Path):
    """Tests summary statistics, filtering by search/category, and CSV/JSON export."""
    # 1. Stats
    stats_res = await async_client.get("/api/v1/history/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "total_activities" in stats
    assert "executions_succeeded" in stats
    assert stats["total_activities"] >= 0

    # 2. Export JSON
    json_export = await async_client.get("/api/v1/history/export?format=json")
    assert json_export.status_code == 200
    assert json_export.headers["content-type"] == "application/json"
    assert "attachment; filename=\"activity_history.json\"" in json_export.headers["content-disposition"]

    # 3. Export CSV
    csv_export = await async_client.get("/api/v1/history/export?format=csv")
    assert csv_export.status_code == 200
    assert "text/csv" in csv_export.headers["content-type"]
    assert "attachment; filename=\"activity_history.csv\"" in csv_export.headers["content-disposition"]
    assert "Timestamp (UTC)" in csv_export.text


@pytest.mark.asyncio
async def test_batch_approval_and_execution(async_client: AsyncClient, tmp_path: Path):
    """Verifies batch approve and batch execute approved endpoints."""
    folder_root = tmp_path / "batch_test"
    folder_root.mkdir()
    (folder_root / "f1.txt").write_text("f1")
    (folder_root / "f2.txt").write_text("f2")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Batch Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Create plan 1
    p1_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Batch Plan 1",
            "plan_type": "manual",
            "items": [
                {
                    "operation": "rename",
                    "source_relative_path": "f1.txt",
                    "destination_relative_path": "f1_renamed.txt",
                    "sequence_no": 1,
                }
            ],
        },
    )
    p1_id = p1_res.json()["id"]

    # Create plan 2
    p2_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Batch Plan 2",
            "plan_type": "manual",
            "items": [
                {
                    "operation": "rename",
                    "source_relative_path": "f2.txt",
                    "destination_relative_path": "f2_renamed.txt",
                    "sequence_no": 1,
                }
            ],
        },
    )
    p2_id = p2_res.json()["id"]

    # Batch approve
    batch_app_res = await async_client.post(
        "/api/v1/transactions/plans/batch-approve",
        json={"plan_ids": [p1_id, p2_id], "approved_by": "batch_tester"},
    )
    assert batch_app_res.status_code == 200
    assert len(batch_app_res.json()) == 2
    assert all(p["status"] == "approved" for p in batch_app_res.json())

    # Batch execute approved
    batch_exec_res = await async_client.post(
        "/api/v1/transactions/plans/execute-approved",
        json={"plan_ids": [p1_id, p2_id]},
    )
    assert batch_exec_res.status_code == 200
    jobs = batch_exec_res.json()
    assert len(jobs) == 2
    assert all(j["status"] == "completed" for j in jobs)

    # Verify disk state
    assert (folder_root / "f1_renamed.txt").exists()
    assert (folder_root / "f2_renamed.txt").exists()


@pytest.mark.asyncio
async def test_approve_plan_with_20_nested_organization_items(async_client: AsyncClient, tmp_path: Path):
    """Verifies that an organization plan with 20 files moving to nested subdirectories
    validates with zero conflicts and can be cleanly approved and executed."""
    folder_root = tmp_path / "nested_org_20_test"
    folder_root.mkdir()

    # Create 20 files
    for i in range(1, 21):
        f = folder_root / f"document_{i:02d}.pdf"
        f.write_text(f"Document content {i}")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Org 20 Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Generate organization plan by date (creates nested dirs e.g. 2026/2026-03 or by_date subfolder)
    org_res = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_date",
            "subfolder_prefix": "Archive",
            "move_unorganized_only": False,
        },
    )
    assert org_res.status_code in (200, 201)
    plan_data = org_res.json()
    plan_id = plan_data["change_plan_id"]
    assert plan_data["conflicts_count"] == 0

    # Validate plan via API
    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["can_execute"] is True
    assert val_data["is_valid"] is True
    assert len(val_data["issues"]) == 0

    # Approve plan — this previously crashed with "Cannot approve plan with 20 validation issues or conflicts"
    app_res = await async_client.post(
        f"/api/v1/transactions/plans/{plan_id}/approve",
        json={"approved_by": "test_user"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Execute plan
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "completed"

    # Verify all 20 files exist in their nested destinations (e.g. Archive/2026/2026-11/document_*.pdf)
    nested_files = [f for f in folder_root.rglob("*.pdf") if f.parent != folder_root]
    assert len(nested_files) == 20


@pytest.mark.asyncio
async def test_approve_plan_with_20_case_only_rename_items(async_client: AsyncClient, tmp_path: Path):
    """Verifies that 20 case-only renames (e.g. DOC_01.TXT -> doc_01.txt)
    do not trigger false collision errors on Windows and approve cleanly."""
    folder_root = tmp_path / "case_rename_20_test"
    folder_root.mkdir()

    items = []
    for i in range(1, 21):
        upper_name = f"DOC_{i:02d}.TXT"
        lower_name = f"doc_{i:02d}.txt"
        (folder_root / upper_name).write_text(f"Case test {i}")
        items.append({
            "operation": "rename",
            "source_relative_path": upper_name,
            "destination_relative_path": lower_name,
            "sequence_no": i,
        })

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Case Rename 20 Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Case Rename 20 Plan",
            "plan_type": "rename",
            "items": items,
        },
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    # Validate plan
    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    assert val_res.json()["can_execute"] is True
    assert val_res.json()["is_valid"] is True

    # Approve plan
    app_res = await async_client.post(
        f"/api/v1/transactions/plans/{plan_id}/approve",
        json={"approved_by": "test_user"},
    )
    assert app_res.status_code == 200
    assert app_res.json()["status"] == "approved"

    # Execute plan
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 200
    assert exec_res.json()["status"] == "completed"


