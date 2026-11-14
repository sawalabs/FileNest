import json
from pathlib import Path
import pytest
from httpx import AsyncClient

from backend.app.services.monitoring import MonitoringManagerService


@pytest.mark.asyncio
async def test_rule_creation_and_versioning(async_client: AsyncClient, tmp_path: Path):
    """Verifies that rule modification increments version and revokes approval."""
    folder_dir = tmp_path / "rules_version_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Version Test", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Create Rule
    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Auto Invoices Mover",
            "rule_type": "organize",
            "scope": {"subpath": "", "extensions": ["pdf"]},
            "conditions": [{"field": "name", "operator": "contains", "value": "invoice"}],
            "actions": [{"action_type": "move", "target_directory": "Invoices"}],
            "is_enabled": False,
        },
    )
    assert create_res.status_code == 201
    rule = create_res.json()
    assert rule["version"] == 1
    assert rule["is_approved"] is False
    assert rule["approved_at"] is None
    rule_id = rule["id"]

    # 2. Approve Rule
    app_res = await async_client.post(
        f"/api/v1/rules/{rule_id}/approve",
        json={"approved_by": "test_user"},
    )
    assert app_res.status_code == 200
    app_data = app_res.json()
    assert app_data["is_approved"] is True
    assert app_data["approved_by"] == "test_user"
    assert app_data["version"] == 1

    # 3. Non-material update (rename title) -> preserves approval & version
    patch_name = await async_client.patch(
        f"/api/v1/rules/{rule_id}",
        json={"name": "Auto Invoices Organizer"},
    )
    assert patch_name.status_code == 200
    name_data = patch_name.json()
    assert name_data["version"] == 1
    assert name_data["is_approved"] is True

    # 4. Material update (change scope extensions) -> increments version and revokes approval!
    patch_scope = await async_client.patch(
        f"/api/v1/rules/{rule_id}",
        json={"scope": {"subpath": "", "extensions": ["pdf", "docx"]}},
    )
    assert patch_scope.status_code == 200
    scope_data = patch_scope.json()
    assert scope_data["version"] == 2
    assert scope_data["is_approved"] is False
    assert scope_data["approved_at"] is None


@pytest.mark.asyncio
async def test_unapproved_rule_routed_to_review(async_client: AsyncClient, tmp_path: Path):
    """Verifies that matching files under unapproved rules are routed to Review Changes."""
    folder_dir = tmp_path / "rules_unapproved_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "invoice_999.pdf").write_text("pdf dummy content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Unapproved Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # Create unapproved rule and enable it
    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Unapproved Move",
            "rule_type": "organize",
            "scope": {"subpath": "", "extensions": ["pdf"]},
            "conditions": [],
            "actions": [{"action_type": "move", "target_directory": "Invoices"}],
            "is_enabled": True,
        },
    )
    rule_id = create_res.json()["id"]

    # Evaluate file
    eval_res = await async_client.post(
        "/api/v1/rules/evaluate-file",
        json={"managed_folder_id": folder_id, "relative_path": "invoice_999.pdf"},
    )
    assert eval_res.status_code == 200
    eval_list = eval_res.json()
    assert len(eval_list) == 1
    result = eval_list[0]
    assert result["matched"] is True
    assert result["eligible_for_auto_execution"] is False
    assert result["execution_status"] == "routed_to_review"
    assert result["plan_id"] is not None

    # Original file must NOT have been moved automatically
    assert (folder_dir / "invoice_999.pdf").exists()
    assert not (folder_dir / "Invoices" / "invoice_999.pdf").exists()


@pytest.mark.asyncio
async def test_approved_rule_auto_execution_within_scope(async_client: AsyncClient, tmp_path: Path):
    """Verifies that an approved, enabled rule executes automatically within its verified scope."""
    folder_dir = tmp_path / "rules_auto_exec_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    target_file = folder_dir / "monthly_invoice_2026.pdf"
    target_file.write_text("invoice content for auto execution", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Auto Exec Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # 1. Create, Approve, and Enable Rule
    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Auto Move Monthly Invoices",
            "rule_type": "organize",
            "scope": {"subpath": "", "extensions": ["pdf"]},
            "conditions": [{"field": "name", "operator": "starts_with", "value": "monthly_invoice"}],
            "actions": [{"action_type": "move", "target_directory": "Archive/Invoices"}],
            "is_enabled": True,
        },
    )
    rule_id = create_res.json()["id"]

    # Approve
    await async_client.post(f"/api/v1/rules/{rule_id}/approve")

    # 2. Evaluate file
    eval_res = await async_client.post(
        "/api/v1/rules/evaluate-file",
        json={"managed_folder_id": folder_id, "relative_path": "monthly_invoice_2026.pdf"},
    )
    assert eval_res.status_code == 200
    eval_list = eval_res.json()
    assert len(eval_list) == 1
    result = eval_list[0]
    assert result["matched"] is True
    assert result["eligible_for_auto_execution"] is True
    assert result["execution_status"] == "executed"

    # File must be physically moved to the destination
    assert not (folder_dir / "monthly_invoice_2026.pdf").exists()
    assert (folder_dir / "Archive" / "Invoices" / "monthly_invoice_2026.pdf").exists()

    # Verify execution history
    exec_res = await async_client.get(f"/api/v1/rules/executions?rule_id={rule_id}")
    assert exec_res.status_code == 200
    exec_history = exec_res.json()
    assert len(exec_history) >= 1
    assert exec_history[0]["status"] == "executed"


@pytest.mark.asyncio
async def test_collision_routing_to_review_changes(async_client: AsyncClient, tmp_path: Path):
    """Verifies that destination collisions are NEVER overwritten and are safely routed to Review Changes."""
    folder_dir = tmp_path / "rules_collision_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    dest_dir = folder_dir / "Documents"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Collision condition: destination already exists with distinct content!
    existing_dest = dest_dir / "important_contract.pdf"
    existing_dest.write_text("existing confidential contract v1", encoding="utf-8")

    source_file = folder_dir / "important_contract.pdf"
    source_file.write_text("new incoming contract v2", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Collision Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # Create & Approve Rule
    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Move Contracts to Documents",
            "rule_type": "organize",
            "scope": {"subpath": "", "extensions": ["pdf"]},
            "conditions": [],
            "actions": [{"action_type": "move", "target_directory": "Documents"}],
            "is_enabled": True,
        },
    )
    rule_id = create_res.json()["id"]
    await async_client.post(f"/api/v1/rules/{rule_id}/approve")

    # Evaluate rule on conflicting file
    eval_res = await async_client.post(
        "/api/v1/rules/evaluate-file",
        json={"managed_folder_id": folder_id, "relative_path": "important_contract.pdf"},
    )
    assert eval_res.status_code == 200
    res_data = eval_res.json()[0]

    # MUST NOT OVERWRITE
    assert res_data["execution_status"] == "routed_to_review"
    assert "Tabrakan tujuan terdeteksi" in res_data["message"] or "already exists" in res_data["message"]
    assert res_data["plan_id"] is not None

    # CRITICAL CHECK: existing destination content was NOT overwritten
    assert existing_dest.read_text(encoding="utf-8") == "existing confidential contract v1"
    assert source_file.read_text(encoding="utf-8") == "new incoming contract v2"

    # Execution history must record status="pending_review"
    exec_res = await async_client.get(f"/api/v1/rules/executions?rule_id={rule_id}")
    assert exec_res.status_code == 200
    history = exec_res.json()
    assert history[0]["status"] == "pending_review"


@pytest.mark.asyncio
async def test_scope_confinement_blocks_unauthorized_paths(async_client: AsyncClient, tmp_path: Path):
    """Verifies that files outside the rule's specified scope subpath are ignored."""
    folder_dir = tmp_path / "rules_scope_confinement"
    folder_dir.mkdir(parents=True, exist_ok=True)
    sub = folder_dir / "Work"
    sub.mkdir(parents=True, exist_ok=True)

    (folder_dir / "unscoped_doc.pdf").write_text("doc in root", encoding="utf-8")
    (sub / "scoped_doc.pdf").write_text("doc in work", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Confinement Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # Rule restricted to subpath="Work"
    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Scoped Work Rule",
            "rule_type": "organize",
            "scope": {"subpath": "Work", "extensions": ["pdf"]},
            "conditions": [],
            "actions": [{"action_type": "move", "target_directory": "Work/Processed"}],
            "is_enabled": True,
        },
    )
    rule_id = create_res.json()["id"]
    await async_client.post(f"/api/v1/rules/{rule_id}/approve")

    # 1. Unscoped file in root -> skipped
    eval_unscoped = await async_client.post(
        "/api/v1/rules/evaluate-file",
        json={"managed_folder_id": folder_id, "relative_path": "unscoped_doc.pdf"},
    )
    assert eval_unscoped.json()[0]["execution_status"] == "skipped"

    # 2. Scoped file in Work -> executed
    eval_scoped = await async_client.post(
        "/api/v1/rules/evaluate-file",
        json={"managed_folder_id": folder_id, "relative_path": "Work/scoped_doc.pdf"},
    )
    assert eval_scoped.json()[0]["execution_status"] == "executed"
    assert (folder_dir / "Work" / "Processed" / "scoped_doc.pdf").exists()


@pytest.mark.asyncio
async def test_monitoring_event_triggers_rule(async_client: AsyncClient, tmp_path: Path):
    """Verifies that persist_event triggers approved rule evaluation and execution."""
    folder_dir = tmp_path / "rules_monitor_trigger"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "auto_event.pdf").write_text("event file content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rules Monitor Trigger Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    create_res = await async_client.post(
        "/api/v1/rules",
        json={
            "managed_folder_id": folder_id,
            "name": "Monitor Triggered Move",
            "rule_type": "organize",
            "scope": {"subpath": "", "extensions": ["pdf"]},
            "conditions": [],
            "actions": [{"action_type": "move", "target_directory": "FromMonitoring"}],
            "is_enabled": True,
        },
    )
    rule_id = create_res.json()["id"]
    await async_client.post(f"/api/v1/rules/{rule_id}/approve")

    # Initialize monitoring service DB session
    await async_client.get("/api/v1/monitoring/watchers")

    # Directly trigger monitoring persist_event
    mon_service = MonitoringManagerService()
    mon_service.persist_event(
        folder_id=folder_id,
        event_type="created",
        relative_path="auto_event.pdf",
    )

    # Verify rule was executed
    exec_res = await async_client.get(f"/api/v1/rules/executions?rule_id={rule_id}")
    assert exec_res.status_code == 200
    history = exec_res.json()
    assert len(history) >= 1
    assert history[0]["status"] == "executed"
    assert (folder_dir / "FromMonitoring" / "auto_event.pdf").exists()
