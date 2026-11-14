import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.logging import SensitiveDataFilter, setup_logging
from backend.app.main import app, lifespan
from backend.app.schemas.health import HealthResponse
from backend.app.services.system import SystemService


@pytest.mark.asyncio
async def test_lifespan_clean_startup_and_shutdown():
    """Verify application lifespan initializes cleanly, starts monitoring, and shuts down safely."""
    with patch("backend.app.services.monitoring.get_monitoring_service") as mock_mon_getter:
        mock_mon = MagicMock()
        mock_mon_getter.return_value = mock_mon

        async with lifespan(app):
            mock_mon.start_all_enabled.assert_called_once()

        mock_mon.stop_all.assert_called_once()


@pytest.mark.asyncio
async def test_subsystem_health_diagnostics_live(async_client: AsyncClient):
    """Verify the /api/v1/health endpoint outputs complete subsystem diagnostic telemetry."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert data["project"] == settings.PROJECT_NAME
    assert data["version"] == settings.VERSION
    assert data["environment"] == settings.ENVIRONMENT
    assert "timestamp" in data

    subsystems = data["subsystems"]
    assert "database" in subsystems
    assert subsystems["database"]["status"] == "ok"
    assert "latency_ms" in subsystems["database"]
    assert subsystems["database"]["details"]["engine"] == "sqlite"

    assert "security" in subsystems
    assert subsystems["security"]["status"] in ("ok", "warning")
    assert "vault_service" in subsystems["security"]["details"]

    assert "ai_gateway" in subsystems
    assert subsystems["ai_gateway"]["status"] in ("ok", "not_configured", "warning")

    assert "monitoring" in subsystems
    assert subsystems["monitoring"]["status"] == "ok"
    assert "active_watchers" in subsystems["monitoring"]["details"]


def test_subsystem_health_database_failure_degradation():
    """Verify SystemService marks overall status degraded when database fails probe."""
    mock_db = MagicMock(spec=Session)
    mock_db.execute.side_effect = RuntimeError("SQLite database file locked or corrupted")

    health: HealthResponse = SystemService.get_health_status(db=mock_db)
    assert health.status == "degraded"
    assert health.subsystems["database"].status == "error"
    assert "locked or corrupted" in health.subsystems["database"].message


def test_structured_logging_production_redaction():
    """Verify SensitiveDataFilter redacts tokens, bearer auth, and passwords from log records."""
    log_filter = SensitiveDataFilter()

    # Test msg redaction
    rec1 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Connecting with api_key: 'sk-test1234567890abcdef' to endpoint",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(rec1) is True
    assert "sk-test1234567890abcdef" not in rec1.msg
    assert "***REDACTED***" in rec1.msg

    # Test Bearer token redaction
    rec2 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=20,
        msg="Authorization header sent: Bearer test-jwt-token-placeholder.secret",
        args=(),
        exc_info=None,
    )
    assert log_filter.filter(rec2) is True
    assert "Bearer ***REDACTED***" in rec2.msg

    # Test tuple args redaction
    rec3 = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=30,
        msg="User auth credentials %s provided",
        args=("password='supersecretpass123'",),
        exc_info=None,
    )
    assert log_filter.filter(rec3) is True
    assert "supersecretpass123" not in str(rec3.args)
    assert "***REDACTED***" in str(rec3.args)


def test_frontend_distribution_bundle_integrity():
    """Verify Vite production build output exists and contains essential production assets."""
    project_root = Path(__file__).resolve().parent.parent.parent
    dist_dir = project_root / "dist"
    index_html = dist_dir / "index.html"
    assets_dir = dist_dir / "assets"

    assert dist_dir.exists(), "dist directory must exist after pnpm build"
    assert index_html.exists(), "dist/index.html must exist"
    assert assets_dir.exists() and assets_dir.is_dir(), "dist/assets must exist"

    html_content = index_html.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content or "<!doctype html>" in html_content.lower()
    assert "/assets/" in html_content

    # Verify no raw leaked dev environment secrets in dist
    for asset_file in assets_dir.glob("*.js"):
        content = asset_file.read_text(encoding="utf-8", errors="ignore")
        assert "supersecret" not in content.lower()


def test_tauri_production_configuration():
    """Verify Tauri 2 configuration is properly configured for Windows native desktop packaging."""
    project_root = Path(__file__).resolve().parent.parent.parent
    tauri_conf_path = project_root / "src-tauri" / "tauri.conf.json"

    assert tauri_conf_path.exists(), "src-tauri/tauri.conf.json must exist"
    with open(tauri_conf_path, "r", encoding="utf-8") as f:
        conf = json.load(f)

    assert conf["productName"] == "FileNest"
    assert conf["identifier"] == "com.filenest.desktop"
    assert conf["build"]["frontendDist"] == "../dist"
    assert conf["bundle"]["active"] is True
    assert "windows" in conf["bundle"]
    assert conf.get("app", {}).get("security", {}).get("csp") is not None


def test_windows_startup_registry_sync_and_tauri_tray_integration():
    """[SET-03] Verify Windows Registry startup sync and Tauri 2 native tray & minimize behavior."""
    import sys
    import types
    from backend.app.services.settings_service import SettingsService

    project_root = Path(__file__).resolve().parent.parent.parent
    lib_rs_path = project_root / "src-tauri" / "src" / "lib.rs"
    cargo_toml_path = project_root / "src-tauri" / "Cargo.toml"

    assert "tray-icon" in cargo_toml_path.read_text(encoding="utf-8")
    lib_rs = lib_rs_path.read_text(encoding="utf-8")
    assert "TrayIconBuilder" in lib_rs
    assert "sync_desktop_behavior" in lib_rs
    assert "WindowEvent::CloseRequested" in lib_rs
    assert "prevent_close" in lib_rs

    # Mock winreg to verify HKCU Run registry writes/deletes without mutating host registry
    mock_winreg = types.SimpleNamespace(
        HKEY_CURRENT_USER=0x80000001,
        KEY_SET_VALUE=0x0002,
        REG_SZ=1,
        OpenKey=MagicMock(),
        SetValueEx=MagicMock(),
        DeleteValue=MagicMock(),
    )
    mock_key_ctx = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key_ctx)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    with (
        patch("backend.app.services.settings_service.platform.system", return_value="Windows"),
        patch.dict(sys.modules, {"winreg": mock_winreg}),
    ):
        assert SettingsService.sync_windows_startup_registry(True, executable_path="C:\\FileNest\\filenest.exe", _force_in_test=True) is True
        mock_winreg.SetValueEx.assert_called_once()
        assert SettingsService.sync_windows_startup_registry(False, _force_in_test=True) is True
        mock_winreg.DeleteValue.assert_called_once()


@pytest.mark.asyncio
async def test_auto_schema_migration_and_update_installer_endpoints(async_client: AsyncClient, tmp_path: Path):
    """Verify auto SQLite schema upgrades, tauri.localhost handshake, and update installer APIs."""
    from sqlalchemy import create_engine, inspect

    from backend.app.main import ensure_sqlite_schema_migrations

    # 1. Verify ensure_sqlite_schema_migrations upgrades legacy SQLite schemas additively
    legacy_db = tmp_path / "legacy_upgrade.db"
    legacy_engine = create_engine(f"sqlite:///{legacy_db}")
    try:
        with legacy_engine.begin() as conn:
            conn.execute(text("CREATE TABLE audit_logs (id INTEGER PRIMARY KEY, action VARCHAR NOT NULL)"))

        added = ensure_sqlite_schema_migrations(legacy_engine)
        assert any(item.startswith("audit_logs.") for item in added)
        inspector = inspect(legacy_engine)
        cols = {col["name"] for col in inspector.get_columns("audit_logs")}
        assert "details_json" in cols
        assert "created_at" in cols
    finally:
        legacy_engine.dispose()

    # 2. Verify http://tauri.localhost is accepted on /api/v1/auth/session even with Sec-Fetch-Site: cross-site
    session_resp = await async_client.get(
        "/api/v1/auth/session",
        headers={
            "Origin": "http://tauri.localhost",
            "Sec-Fetch-Site": "cross-site",
        },
    )
    assert session_resp.status_code == 200
    assert session_resp.json()["token"]

    # 3. Verify GET /api/v1/settings/update/status lists discovered installer artifacts
    fake_release_dir = tmp_path / "release"
    fake_release_dir.mkdir(parents=True, exist_ok=True)
    fake_installer = fake_release_dir / "FileNest_0.1.0_x64-setup.exe"
    fake_installer.write_bytes(b"MZ-fake-nsis-installer")

    with patch(
        "backend.app.services.settings_service.SettingsService._candidate_installer_dirs",
        return_value=[fake_release_dir],
    ):
        status_resp = await async_client.get("/api/v1/settings/update/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["current_version"] == settings.VERSION
    assert status_data["latest_version"] == "0.1.0"
    assert len(status_data["installers"]) == 1
    assert status_data["installers"][0]["installer_type"] == "nsis"
    assert status_data["installers"][0]["filename"] == "FileNest_0.1.0_x64-setup.exe"

    # 4. Verify POST /api/v1/settings/update/apply validates extension & triggers dry-run launch
    bad_file = tmp_path / "not_an_installer.txt"
    bad_file.write_text("bad", encoding="utf-8")
    bad_resp = await async_client.post(
        "/api/v1/settings/update/apply",
        json={"installer_path": str(bad_file)},
    )
    assert bad_resp.status_code == 400

    apply_resp = await async_client.post(
        "/api/v1/settings/update/apply",
        json={"installer_path": str(fake_installer)},
    )
    assert apply_resp.status_code == 200
    apply_data = apply_resp.json()
    assert apply_data["success"] is True
    assert apply_data["installer_path"] == str(fake_installer.resolve())


@pytest.mark.asyncio
async def test_protected_project_and_dll_tool_folders_skipped_in_organization(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify tool/DLL bundles (e.g. platform-tools) and manual flags are never disassembled by Organize."""
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)

    # Loose personal files that SHOULD be organized
    (workspace / "notes.txt").write_text("hello", encoding="utf-8")

    # Self-contained platform-tools folder with .exe & .dll files that MUST NOT be organized
    platform_tools = workspace / "platform-tools"
    platform_tools.mkdir(parents=True, exist_ok=True)
    (platform_tools / "adb.exe").write_bytes(b"MZ-adb")
    (platform_tools / "AdbWinApi.dll").write_bytes(b"MZ-dll-1")
    (platform_tools / "AdbWinUsbApi.dll").write_bytes(b"MZ-dll-2")

    # Normal folder that user manually flags later
    manual_folder = workspace / "MyCustomKit"
    manual_folder.mkdir(parents=True, exist_ok=True)
    (manual_folder / "readme.txt").write_text("keep together", encoding="utf-8")

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Workspace", "root_path": str(workspace)},
    )
    assert reg_resp.status_code == 201
    folder_id = reg_resp.json()["id"]

    # 1. Explicit smart detect finds platform-tools automatically
    detect_resp = await async_client.post(
        f"/api/v1/organization/protected-folders/{folder_id}/detect?use_ai=false"
    )
    assert detect_resp.status_code == 200
    detect_data = detect_resp.json()
    assert detect_data["newly_flagged_count"] >= 1
    assert any(
        it["relative_path"] == "platform-tools" and it["category"] in ("tool_bundle", "sdk_runtime")
        for it in detect_data["protected_folders"]
    )

    # 2. Manual flag MyCustomKit
    manual_resp = await async_client.post(
        f"/api/v1/organization/protected-folders/{folder_id}",
        json={"relative_path": "MyCustomKit"},
    )
    assert manual_resp.status_code == 201
    manual_item_id = manual_resp.json()["id"]
    assert manual_resp.json()["source"] == "manual"
    assert manual_resp.json()["is_protected"] is True

    # 3. Generate organization plan -> loose notes.txt moves, platform-tools/*.dll & MyCustomKit/* are skipped
    plan_resp = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_category",
            "include_subfolders": True,
            "move_unorganized_only": True,
        },
    )
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    moved_sources = [it["source_relative_path"] for it in plan_data["items"] if it["operation"] == "move"]
    assert "notes.txt" in moved_sources
    assert not any(src.startswith("platform-tools/") for src in moved_sources)
    assert not any(src.startswith("MyCustomKit/") for src in moved_sources)
    assert "platform-tools" in plan_data["protected_folders_skipped"]
    assert "MyCustomKit" in plan_data["protected_folders_skipped"]

    # 4. Toggle MyCustomKit to paused (is_protected=False) -> now MyCustomKit/readme.txt is included
    toggle_resp = await async_client.patch(
        f"/api/v1/organization/protected-folders/{folder_id}/{manual_item_id}",
        json={"is_protected": False},
    )
    assert toggle_resp.status_code == 200
    assert toggle_resp.json()["is_protected"] is False

    plan_resp_2 = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_category",
            "include_subfolders": True,
            "move_unorganized_only": True,
        },
    )
    assert plan_resp_2.status_code == 201
    plan_data_2 = plan_resp_2.json()
    moved_sources_2 = [it["source_relative_path"] for it in plan_data_2["items"] if it["operation"] == "move"]
    assert "MyCustomKit/readme.txt" in moved_sources_2
    assert not any(src.startswith("platform-tools/") for src in moved_sources_2)
