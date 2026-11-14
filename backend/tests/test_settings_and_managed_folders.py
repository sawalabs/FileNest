import json
import pytest
from httpx import AsyncClient

from backend.app.db.models.app_setting import AppSetting
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.credential_service import CredentialService


@pytest.mark.asyncio
async def test_get_all_settings(async_client: AsyncClient):
    res = await async_client.get("/api/v1/settings")
    assert res.status_code == 200
    data = res.json()
    assert "general" in data
    assert "ai" in data
    assert "organization" in data
    assert "monitoring" in data
    assert "security" in data
    assert "storage" in data
    assert "about" in data


@pytest.mark.asyncio
async def test_update_general_settings(async_client: AsyncClient):
    payload = {
        "theme": "dark",
        "show_hidden_files": True,
        "default_file_view": "grid",
    }
    res = await async_client.patch("/api/v1/settings/general", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["theme"] == "dark"
    assert data["show_hidden_files"] is True
    assert data["default_file_view"] == "grid"


@pytest.mark.asyncio
async def test_secrets_stored_in_credential_vault_not_sqlite(async_client: AsyncClient):
    secret_key = "sk-test-dummy-key-998811"
    
    # 1. Update AI settings with API key
    payload = {
        "router_api_key": secret_key,
        "default_model": "gpt-4o",
    }
    res = await async_client.patch("/api/v1/settings/ai", json=payload)
    assert res.status_code == 200
    data = res.json()
    
    # Verify response masks the key
    assert data["has_router_api_key"] is True
    assert secret_key not in data["masked_router_api_key"]
    assert data["masked_router_api_key"].startswith("sk-")
    assert data["masked_router_api_key"].endswith("8811")

    # 2. Verify key is NOT in plaintext in SQLite app_settings
    db_gen = app.dependency_overrides[get_db]()
    db_session = next(db_gen)
    try:
        setting_row = db_session.get(AppSetting, "settings:ai")
        assert setting_row is not None
        assert secret_key not in setting_row.value_json
        assert "router_api_key" not in json.loads(setting_row.value_json)
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass

    # 3. Verify CredentialService has it in secure vault
    stored = CredentialService.get_secret("9router_api_key")
    assert stored == secret_key

    # 4. Clear key and verify removal
    res_clear = await async_client.patch("/api/v1/settings/ai", json={"clear_router_api_key": True})
    assert res_clear.status_code == 200
    assert res_clear.json()["has_router_api_key"] is False
    assert CredentialService.get_secret("9router_api_key") is None


@pytest.mark.asyncio
async def test_core_filesystem_safety_constraints_cannot_be_disabled(async_client: AsyncClient):
    # Attempt to disable mandatory safety constraints
    res1 = await async_client.patch("/api/v1/settings/security", json={"backend_path_validation": False})
    assert res1.status_code == 400
    assert "Core filesystem safety constraint cannot be disabled" in res1.json()["detail"]

    res2 = await async_client.patch("/api/v1/settings/security", json={"managed_folders_isolation": False})
    assert res2.status_code == 400
    assert "Core filesystem safety constraint cannot be disabled" in res2.json()["detail"]

    res3 = await async_client.patch("/api/v1/settings/security", json={"mandatory_policies": []})
    assert res3.status_code == 400
    assert "immutable" in res3.json()["detail"]


@pytest.mark.asyncio
async def test_database_maintenance_endpoints(async_client: AsyncClient):
    # Integrity check
    res_int = await async_client.post("/api/v1/settings/database/integrity-check")
    assert res_int.status_code == 200
    data_int = res_int.json()
    assert data_int["success"] is True

    # Database compact
    res_vac = await async_client.post("/api/v1/settings/database/compact")
    assert res_vac.status_code == 200
    assert res_vac.json()["success"] is True

    # Clear cache
    res_cache = await async_client.post("/api/v1/settings/cache/clear")
    assert res_cache.status_code == 200
    assert res_cache.json()["success"] is True


@pytest.mark.asyncio
async def test_managed_folders_capabilities_exclusions_and_health(async_client: AsyncClient, tmp_path):
    folder_dir = tmp_path / "ProjectsFolder"
    folder_dir.mkdir()

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Projects", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Capabilities
    caps_res = await async_client.get(f"/api/v1/folders/{folder_id}/capabilities")
    assert caps_res.status_code == 200
    caps = caps_res.json()
    assert caps["organization"] is True

    # Update capabilities
    update_caps_res = await async_client.put(
        f"/api/v1/folders/{folder_id}/capabilities",
        json={"organization": True, "smart_rename": False, "monitoring": True, "analysis": True, "content_extraction": False},
    )
    assert update_caps_res.status_code == 200
    assert update_caps_res.json()["smart_rename"] is False
    assert update_caps_res.json()["monitoring"] is True

    # 2. Exclusions
    add_ex_res = await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions",
        json={"exclusion_type": "extension", "value": ".bak", "reason": "Backup files"},
    )
    assert add_ex_res.status_code == 201
    ex_id = add_ex_res.json()["id"]

    list_ex_res = await async_client.get(f"/api/v1/folders/{folder_id}/exclusions")
    assert list_ex_res.status_code == 200
    assert len(list_ex_res.json()) == 1

    del_ex_res = await async_client.delete(f"/api/v1/folders/{folder_id}/exclusions/{ex_id}")
    assert del_ex_res.status_code == 204

    # 3. Health & Usage
    health_res = await async_client.get(f"/api/v1/folders/{folder_id}/health")
    assert health_res.status_code == 200
    assert health_res.json()["is_accessible"] is True
    assert health_res.json()["overall_status"] == "healthy"

    usage_res = await async_client.get(f"/api/v1/folders/{folder_id}/usage")
    assert usage_res.status_code == 200
    assert usage_res.json()["total_files_count"] == 0

    # 4. Summary Cards
    summary_res = await async_client.get("/api/v1/folders/summary")
    assert summary_res.status_code == 200
    assert summary_res.json()["total_folders"] >= 1


@pytest.mark.asyncio
async def test_lifespan_respects_start_monitoring_on_launch_setting(async_client: AsyncClient):
    """[SET-04] Verify startup monitoring watcher auto-start respects General & Monitoring flags."""
    from unittest.mock import MagicMock, patch
    from backend.app.main import lifespan, run_startup_monitoring_check

    db_gen = app.dependency_overrides[get_db]()
    db_session = next(db_gen)
    try:
        # 1. Default settings -> should auto-start watchers
        mock_mon = MagicMock()
        assert run_startup_monitoring_check(db_session, mock_mon) is True
        mock_mon.start_all_enabled.assert_called_once_with(db=db_session)

        # 2. General setting start_monitoring_on_launch=False -> must skip auto-start
        res = await async_client.patch("/api/v1/settings/general", json={"start_monitoring_on_launch": False})
        assert res.status_code == 200
        mock_mon2 = MagicMock()
        assert run_startup_monitoring_check(db_session, mock_mon2) is False
        mock_mon2.start_all_enabled.assert_not_called()

        # Verify lifespan integrates run_startup_monitoring_check
        with (
            patch("backend.app.db.session.SessionLocal", return_value=db_session),
            patch("backend.app.services.monitoring.get_monitoring_service", return_value=mock_mon2),
            patch.object(db_session, "close"),
        ):
            async with lifespan(app):
                mock_mon2.start_all_enabled.assert_not_called()
            mock_mon2.stop_all.assert_called_once()

        # 3. Restore general flag, disable monitoring.enable_monitoring -> must skip auto-start
        await async_client.patch("/api/v1/settings/general", json={"start_monitoring_on_launch": True})
        await async_client.patch("/api/v1/settings/monitoring", json={"enable_monitoring": False})
        mock_mon3 = MagicMock()
        assert run_startup_monitoring_check(db_session, mock_mon3) is False
        mock_mon3.start_all_enabled.assert_not_called()
    finally:
        await async_client.patch("/api/v1/settings/monitoring", json={"enable_monitoring": True, "start_monitoring_on_launch": True})
        try:
            next(db_gen)
        except StopIteration:
            pass


@pytest.mark.asyncio
async def test_sync_organization_and_monitoring_global_preferences(async_client: AsyncClient, tmp_path):
    """[SET-05] Verify OrganizationSettings and MonitoringGlobalSettings sync into modules."""
    from backend.app.services.monitoring import MonitoringManagerService

    folder_root = tmp_path / "SyncedOrgFolder"
    folder_root.mkdir()
    (folder_root / "notes.txt").write_text("hello")
    (folder_root / "archive_backup.zip").write_text("zipdata")

    # Pre-create existing destination collision for notes.txt under 01_documents
    existing_docs = folder_root / "01_documents"
    existing_docs.mkdir()
    (existing_docs / "notes.txt").write_text("existing")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Synced Org", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 1. Update global organization preferences
    org_patch = await async_client.patch(
        "/api/v1/settings/organization",
        json={
            "default_folder_naming": "snake_case",
            "use_number_prefix": True,
            "prefix_separator": "_",
            "default_archive_folder_name": "VaultArchive",
            "conflict_resolution_strategy": "add_sequence",
        },
    )
    assert org_patch.status_code == 200

    # Generate organization plan and check naming, prefix, archive folder name, and collision resolution
    plan_res = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_category",
            "move_unorganized_only": True,
            "include_subfolders": False,
        },
    )
    assert plan_res.status_code == 201
    plan_data = plan_res.json()
    moves = {it["source_relative_path"]: it for it in plan_data["items"] if it["operation"] == "move"}
    assert "notes.txt" in moves
    assert moves["notes.txt"]["destination_relative_path"] == "01_documents/notes_1.txt"
    assert moves["notes.txt"]["status"] == "pending"
    assert "archive_backup.zip" in moves
    assert moves["archive_backup.zip"]["destination_relative_path"].endswith("vaultarchive/archive_backup.zip")

    # 2. Update global monitoring preferences and verify sync into watcher defaults & ignore patterns
    mon_patch = await async_client.patch(
        "/api/v1/settings/monitoring",
        json={
            "enable_monitoring": True,
            "recursive_monitoring_default": False,
            "debounce_interval_ms": 2500,
            "global_ignore_patterns": ["*.bak_test"],
        },
    )
    assert mon_patch.status_code == 200

    db_gen = app.dependency_overrides[get_db]()
    db_session = next(db_gen)
    svc = MonitoringManagerService()
    try:
        watcher_info = svc.start_watcher(folder_id, persist=False, db=db_session)
        assert watcher_info["recursive"] is False
        assert watcher_info["debounce_ms"] == 2500
        assert "*.bak_test" in watcher_info["global_ignore_patterns"]
        assert svc.should_ignore(folder_id, "sample.bak_test", "sample.bak_test") is True
    finally:
        svc.stop_watcher(folder_id, persist=False, db=db_session)
        try:
            next(db_gen)
        except StopIteration:
            pass
