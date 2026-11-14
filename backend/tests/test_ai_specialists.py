import json
from pathlib import Path
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_disk_analyst_workflow(async_client: AsyncClient, tmp_path: Path):
    """Verifies Disk Analyst evaluates storage health, waste sources, and recommendations."""
    folder_dir = tmp_path / "spec_disk_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Put sample files
    (folder_dir / "large_data.bin").write_bytes(b"\x00" * (1024 * 1024 * 60))  # 60MB
    (folder_dir / "notes.txt").write_text("sample notes", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Disk Test", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/specialists/disk-analyst",
        json={"managed_folder_id": folder_id, "large_file_threshold_mb": 50},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["specialist"] == "disk_analyst"
    assert data["total_storage_bytes"] >= 60 * 1024 * 1024
    assert data["total_files"] == 2
    assert 0 <= data["health_score"] <= 100
    assert len(data["actionable_recommendations"]) > 0
    assert any(ws["category"] == "large_files" for ws in data["waste_sources"])


@pytest.mark.asyncio
async def test_folder_architect_workflow(async_client: AsyncClient, tmp_path: Path):
    """Verifies Folder Architect proposes structured hierarchy and creates draft plan without mutating files."""
    folder_dir = tmp_path / "spec_architect_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Create loose files
    (folder_dir / "report.pdf").write_text("pdf content", encoding="utf-8")
    (folder_dir / "picture.jpg").write_bytes(b"\xff\xd8\xff" + b"\x00" * 20)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Architect Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/specialists/folder-architect",
        json={
            "managed_folder_id": folder_id,
            "organization_style": "category",
            "create_draft_plan": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["specialist"] == "folder_architect"
    assert data["moves_count"] == 2
    assert "Document" in data["proposed_structure"]
    assert "Image" in data["proposed_structure"]
    assert data["plan_id"] is not None
    assert data["plan_status"] == "pending_review"
    assert data["requires_approval"] is True

    # Files must NOT be physically moved yet!
    assert (folder_dir / "report.pdf").exists()
    assert (folder_dir / "picture.jpg").exists()
    assert not (folder_dir / "Document" / "report.pdf").exists()


@pytest.mark.asyncio
async def test_rename_specialist_workflow(async_client: AsyncClient, tmp_path: Path):
    """Verifies Rename Specialist generates standardized filenames and drafts rename plans."""
    folder_dir = tmp_path / "spec_rename_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Messy filenames
    (folder_dir / "my messy file 2026.txt").write_text("content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Rename Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/specialists/rename-specialist",
        json={
            "managed_folder_id": folder_id,
            "naming_convention": "standard",
            "create_draft_plan": True,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["specialist"] == "rename_specialist"
    assert data["renames_count"] == 1
    rename_item = data["renames"][0]
    assert rename_item["original_name"] == "my messy file 2026.txt"
    assert " " not in rename_item["proposed_name"]
    assert data["plan_id"] is not None
    assert data["plan_status"] == "pending_review"

    # Original file remains untouched
    assert (folder_dir / "my messy file 2026.txt").exists()


@pytest.mark.asyncio
async def test_duplicate_analyst_workflow(async_client: AsyncClient, tmp_path: Path):
    """Verifies Duplicate Analyst clusters duplicate files and determines optimal retention."""
    folder_dir = tmp_path / "spec_dup_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    dup_content = "identical duplicate test bytes " * 50
    (folder_dir / "original.txt").write_text(dup_content, encoding="utf-8")
    (folder_dir / "copy1.txt").write_text(dup_content, encoding="utf-8")
    (folder_dir / "copy2.txt").write_text(dup_content, encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Dup Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/specialists/duplicate-analyst",
        json={
            "managed_folder_id": folder_id,
            "min_size_bytes": 10,
            "retention_strategy": "keep_oldest",
            "create_cleanup_plan": False,
        },
    )
    assert res.status_code == 200
    data = res.json()

    assert data["specialist"] == "duplicate_analyst"
    assert data["total_clusters"] == 1
    assert data["total_duplicate_files"] == 3
    assert data["potential_savings_bytes"] > 0
    cluster = data["clusters"][0]
    assert cluster["keep_file"] != ""
    assert len(cluster["cleanup_candidates"]) == 2


@pytest.mark.asyncio
async def test_review_agent_safety_audit(async_client: AsyncClient, tmp_path: Path):
    """Verifies Review Agent audits change plans for collisions, stale files, and safety risks."""
    folder_dir = tmp_path / "spec_review_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    (folder_dir / "source.txt").write_text("source content", encoding="utf-8")
    (folder_dir / "existing_dest.txt").write_text("existing content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Review Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # 1. Create a plan with a collision risk (moving source.txt -> existing_dest.txt)
    plan_create_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Risky Plan with Collision",
            "plan_type": "manual",
            "items": [
                {
                    "operation": "move",
                    "source_relative_path": "source.txt",
                    "destination_relative_path": "existing_dest.txt",
                }
            ],
        },
    )
    assert plan_create_res.status_code == 201
    plan_id = plan_create_res.json()["id"]

    # 2. Run Review Agent on the risky plan
    rev_res = await async_client.post(
        "/api/v1/specialists/review-agent",
        json={"plan_id": plan_id},
    )
    assert rev_res.status_code == 200
    rev_data = rev_res.json()

    assert rev_data["specialist"] == "review_agent"
    assert rev_data["risk_level"] == "HIGH"
    assert rev_data["safety_verdict"] == "BLOCKED_HIGH_RISK"
    assert rev_data["can_safely_execute"] is False
    assert any(r["category"] == "COLLISION" for r in rev_data["risks"])

    # 3. Create a safe plan (moving to new name)
    safe_plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Clean Safe Plan",
            "plan_type": "manual",
            "items": [
                {
                    "operation": "move",
                    "source_relative_path": "source.txt",
                    "destination_relative_path": "new_safe_file.txt",
                }
            ],
        },
    )
    assert safe_plan_res.status_code == 201
    safe_plan_id = safe_plan_res.json()["id"]

    safe_rev_res = await async_client.post(
        "/api/v1/specialists/review-agent",
        json={"plan_id": safe_plan_id},
    )
    assert safe_rev_res.status_code == 200
    safe_data = safe_rev_res.json()
    assert safe_data["risk_level"] == "LOW"
    assert safe_data["safety_verdict"] == "APPROVED_RECOMMENDED"
    assert safe_data["can_safely_execute"] is True


@pytest.mark.asyncio
async def test_specialist_general_dispatcher(async_client: AsyncClient, tmp_path: Path):
    """Verifies general specialist dispatcher /specialists/run."""
    folder_dir = tmp_path / "spec_dispatch_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "sample.txt").write_text("dispatch sample", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Dispatch Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/specialists/run",
        json={
            "managed_folder_id": folder_id,
            "specialist": "disk_analyst",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["specialist"] == "disk_analyst"
    assert data["total_files"] == 1


@pytest.mark.asyncio
async def test_specialist_validation_and_audit(async_client: AsyncClient, tmp_path: Path):
    """Verifies error handling for non-existent folders and checks audit log recording."""
    # 1. Non-existent folder
    res = await async_client.post(
        "/api/v1/specialists/disk-analyst",
        json={"managed_folder_id": "non-existent-id"},
    )
    assert res.status_code == 400
    assert "tidak ditemukan" in res.json()["detail"]

    # 2. Review agent on invalid plan
    rev_bad = await async_client.post(
        "/api/v1/specialists/review-agent",
        json={"plan_id": "non-existent-plan-id"},
    )
    assert rev_bad.status_code == 400

    # 3. Valid specialist call to generate audit log
    folder_dir = tmp_path / "spec_audit_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "audit_sample.txt").write_text("audit log test", encoding="utf-8")
    reg = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Spec Audit Test", "root_path": str(folder_dir)},
    )
    folder_id = reg.json()["id"]

    await async_client.post(
        "/api/v1/specialists/disk-analyst",
        json={"managed_folder_id": folder_id},
    )

    # 4. Verify audit log was recorded for specialist actions
    audit_res = await async_client.get("/api/v1/history/audit-logs")
    assert audit_res.status_code == 200
    audit_data = audit_res.json()
    actions = [log["action"] for log in audit_data["items"]]
    assert any("specialist_" in a for a in actions)

