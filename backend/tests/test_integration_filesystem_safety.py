import json
import os
import shutil
from pathlib import Path
import pytest
from httpx import AsyncClient

from backend.app.db.models.app_setting import AppSetting
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.credential_service import CredentialService
from backend.app.services.managed_folder import PathValidator, ManagedFolderException


# ==============================================================================
# 1. Canonical Path Confinement & Traversal Rejection
# ==============================================================================
@pytest.mark.asyncio
async def test_canonical_path_confinement_and_traversal_rejection(async_client: AsyncClient, tmp_path: Path):
    safe_folder = tmp_path / "SafeManagedFolder"
    safe_folder.mkdir()
    (safe_folder / "sub").mkdir()
    (safe_folder / "sub" / "file.txt").write_text("Hello World", encoding="utf-8")

    # Outside secret folder
    outside_folder = tmp_path / "SecretOutsideFolder"
    outside_folder.mkdir()
    (outside_folder / "secret.txt").write_text("Top Secret", encoding="utf-8")

    # 1. Register only safe_folder
    res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "SafeFolder", "root_path": str(safe_folder)},
    )
    assert res.status_code == 201
    folder_id = res.json()["id"]

    # 2. Attempt directory listing with traversal escaping root
    traversal_paths = [
        "../SecretOutsideFolder",
        "..\\SecretOutsideFolder",
        "../../",
        "..\\..\\",
        "sub/../../SecretOutsideFolder/secret.txt",
    ]

    for bad_path in traversal_paths:
        res = await async_client.get(
            f"/api/v1/fs/list?folder_id={folder_id}&relative_path={bad_path}"
        )
        assert res.status_code in (400, 403, 404), f"Path traversal '{bad_path}' should be blocked!"
        assert "escape" in res.json()["detail"].lower() or "violation" in res.json()["detail"].lower() or "not found" in res.json()["detail"].lower()


# ==============================================================================
# 2. Windows System & Protected Directory Protection
# ==============================================================================
def test_windows_system_and_protected_directories_rejected(tmp_path: Path):
    protected_paths = [
        "C:\\Windows",
        "C:\\Windows\\System32",
        "C:\\Program Files",
        "C:\\Program Files (x86)",
        "C:\\",
        "D:\\",
    ]

    for sys_path in protected_paths:
        p = Path(sys_path)
        if p.exists():
            with pytest.raises(ManagedFolderException) as exc_info:
                PathValidator.validate_new_root_path(sys_path, [])
            msg = str(exc_info.value).lower()
            assert any(term in msg for term in ["protected", "system", "drive root", "entire drive"])


# ==============================================================================
# 3. Symlinks and Reparse Points Rejected
# ==============================================================================
def test_symlinks_rejected_as_managed_folders(tmp_path: Path):
    real_target = tmp_path / "RealDir"
    real_target.mkdir()
    symlink_dir = tmp_path / "SymlinkDir"

    try:
        os.symlink(real_target, symlink_dir, target_is_directory=True)
    except (OSError, NotImplementedError):
        # In environments without symlink privilege, test skips symlink creation
        pytest.skip("Symlink creation not permitted in this user environment")

    with pytest.raises(ManagedFolderException) as exc_info:
        PathValidator.validate_new_root_path(str(symlink_dir), [])
    assert "symbolic link" in str(exc_info.value).lower()


# ==============================================================================
# 4. Transaction Overwrite Collision Detection & Rollback
# ==============================================================================
@pytest.mark.asyncio
async def test_transaction_collision_prevention_and_best_effort_rollback(async_client: AsyncClient, tmp_path: Path):
    work_dir = tmp_path / "TransactionWorkFolder"
    work_dir.mkdir()
    (work_dir / "doc1.txt").write_text("Document 1 content", encoding="utf-8")
    (work_dir / "doc2.txt").write_text("Document 2 content", encoding="utf-8")
    (work_dir / "target_existing.txt").write_text("Existing file will cause collision", encoding="utf-8")

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "WorkFolder", "root_path": str(work_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Create a plan targeting an existing file (Collision!)
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Test collision detection",
        "plan_type": "manual",
        "items": [
            {
                "operation": "rename",
                "source_relative_path": "doc1.txt",
                "destination_relative_path": "target_existing.txt",
                "sequence_no": 1,
            }
        ],
    }

    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code == 201
    plan_data = create_res.json()
    plan_id = plan_data["id"]

    # 2. Validate plan — collision MUST be flagged and execution prevented
    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["can_execute"] is False
    assert any(iss["issue_type"] == "conflict" for iss in val_data["issues"])

    # 3. Execution without approval or with conflicts MUST be rejected
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 400
    assert "pre-execution validation checks" in exec_res.json()["detail"].lower() or "approval" in exec_res.json()["detail"].lower()

    # Original files must be completely intact
    assert (work_dir / "doc1.txt").read_text(encoding="utf-8") == "Document 1 content"
    assert (work_dir / "target_existing.txt").read_text(encoding="utf-8") == "Existing file will cause collision"


# ==============================================================================
# 5. Monitoring Strict Non-Mutative Guarantee
# ==============================================================================
@pytest.mark.asyncio
async def test_monitoring_never_mutates_files_on_disk(async_client: AsyncClient, tmp_path: Path):
    mon_dir = tmp_path / "MonitoringStrictFolder"
    mon_dir.mkdir()
    sample_file = mon_dir / "data.txt"
    original_content = "Precious User Content"
    sample_file.write_text(original_content, encoding="utf-8")
    original_stat = sample_file.stat()

    # Register folder with monitoring enabled
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MonitoredSafe", "root_path": str(mon_dir), "monitoring_enabled": True},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Start watcher
    start_res = await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/start")
    assert start_res.status_code == 200

    # Read events
    events_res = await async_client.get(f"/api/v1/monitoring/events?folder_id={folder_id}")
    assert events_res.status_code == 200

    # Verify underlying file is completely untouched
    assert sample_file.exists()
    assert sample_file.read_text(encoding="utf-8") == original_content
    current_stat = sample_file.stat()
    assert current_stat.st_mtime == original_stat.st_mtime


# ==============================================================================
# 6. Audit Logging Without Secrets & SQLite Secret Isolation
# ==============================================================================
@pytest.mark.asyncio
async def test_audit_logs_redact_secrets_and_sqlite_contains_no_keys(async_client: AsyncClient):
    raw_api_key = "sk-test-dummy-token-776655"

    # Store API key via settings
    update_res = await async_client.patch(
        "/api/v1/settings/ai",
        json={"router_api_key": raw_api_key},
    )
    assert update_res.status_code == 200

    # Verify SQLite AppSetting does not contain raw key
    db_gen = app.dependency_overrides[get_db]()
    db_session = next(db_gen)
    try:
        setting = db_session.get(AppSetting, "settings:ai")
        assert setting is not None
        assert raw_api_key not in setting.value_json

        # Verify Audit Logs do not contain raw key
        logs = db_session.query(AuditLog).filter(AuditLog.entity_type == "settings").all()
        for l in logs:
            if l.details_json:
                assert raw_api_key not in l.details_json
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


# ==============================================================================
# 7. Security Policies Cannot Be Disabled
# ==============================================================================
@pytest.mark.asyncio
async def test_immutable_security_constraints_cannot_be_disabled(async_client: AsyncClient):
    prohibited_payloads = [
        {"backend_path_validation": False},
        {"managed_folders_isolation": False},
        {"prevent_silent_overwrite": False},
        {"no_permanent_delete": False},
        {"transaction_manager_required": False},
    ]

    for p in prohibited_payloads:
        res = await async_client.patch("/api/v1/settings/security", json=p)
        assert res.status_code == 400
        assert "Core filesystem safety constraint cannot be disabled" in res.json()["detail"]
