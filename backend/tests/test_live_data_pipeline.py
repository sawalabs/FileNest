import pytest
from httpx import AsyncClient
from backend.app.db.models.scan_job import ScanJob
from backend.app.db.models.file import FileRecord
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.session import get_db
from backend.app.main import app


@pytest.mark.asyncio
async def test_live_data_empty_state_consistency(async_client: AsyncClient):
    """Verifies that all API data sources return clean empty states without invented data."""
    # 1. Dashboard Overview
    dash_res = await async_client.get("/api/v1/dashboard/overview")
    assert dash_res.status_code == 200
    dash_data = dash_res.json()
    assert dash_data["summary_cards"]["managed_folders_count"] == 0
    assert dash_data["summary_cards"]["total_files_count"] == 0
    assert dash_data["summary_cards"]["total_size_bytes"] == 0
    assert dash_data["summary_cards"]["pending_changes_count"] == 0
    assert dash_data["folder_distribution"] == []
    assert dash_data["managed_folders"] == []
    assert dash_data["recommendations"] == []
    assert dash_data["jobs"] == []
    assert dash_data["storage_history"] == []
    assert dash_data["is_stale"] is False

    # 2. Managed Folders
    folders_res = await async_client.get("/api/v1/folders")
    assert folders_res.status_code == 200
    assert folders_res.json() == []

    # 3. Storage Analysis Latest
    storage_res = await async_client.get("/api/v1/storage/analysis")
    assert storage_res.status_code == 200
    assert storage_res.json() is None

    # 4. Monitoring Stats & Watchers
    mon_res = await async_client.get("/api/v1/monitoring/stats")
    assert mon_res.status_code == 200
    mon_stats = mon_res.json()
    assert mon_stats["monitored_folders_count"] == 0
    assert mon_stats["active_watchers_count"] == 0
    assert mon_stats["total_events_24h"] == 0

    watchers_res = await async_client.get("/api/v1/monitoring/watchers")
    assert watchers_res.status_code == 200
    assert watchers_res.json() == []

    # 5. Review Changes Plans
    plans_res = await async_client.get("/api/v1/transactions/plans")
    assert plans_res.status_code == 200
    assert plans_res.json() == []

    # 6. History Stats & Executions
    hist_stats = await async_client.get("/api/v1/history/stats")
    assert hist_stats.status_code == 200
    assert hist_stats.json()["total_activities"] == 0
    assert hist_stats.json()["executions_succeeded"] == 0

    exec_res = await async_client.get("/api/v1/history/executions")
    assert exec_res.status_code == 200
    assert exec_res.json()["items"] == []
    assert exec_res.json()["total"] == 0


@pytest.mark.asyncio
async def test_live_data_flow_filesystem_to_api(async_client: AsyncClient, tmp_path):
    """Verifies end-to-end data pipeline from physical files to SQLite and API responses."""
    test_root = tmp_path / "LiveDataManaged"
    test_root.mkdir()

    # Create distinct files with exact known byte sizes
    f1 = test_root / "report.pdf"
    f1.write_bytes(b"P" * 1024)  # 1024 bytes (document)
    f2 = test_root / "photo.jpg"
    f2.write_bytes(b"J" * 2048)  # 2048 bytes (image)
    sub = test_root / "subfolder"
    sub.mkdir()
    f3 = sub / "script.py"
    f3.write_bytes(b"C" * 512)   # 512 bytes (code)

    total_expected_bytes = 1024 + 2048 + 512  # 3584 bytes

    # 1. Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "LiveDataManaged", "root_path": str(test_root.resolve())},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 2. Before scanning, dashboard marks data as stale because folder is registered but unindexed
    pre_dash = await async_client.get("/api/v1/dashboard/overview")
    assert pre_dash.status_code == 200
    assert pre_dash.json()["is_stale"] is True

    # 3. Trigger storage analysis (real scan)
    scan_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": folder_id, "calculate_hashes": True},
    )
    assert scan_res.status_code == 200
    analysis = scan_res.json()
    assert analysis["total_files_count"] == 3
    assert analysis["total_storage_bytes"] == total_expected_bytes

    # 4. Dashboard Overview now consumes typed persisted data
    post_dash = await async_client.get("/api/v1/dashboard/overview")
    assert post_dash.status_code == 200
    dash_data = post_dash.json()

    cards = dash_data["summary_cards"]
    assert cards["managed_folders_count"] == 1
    assert cards["total_files_count"] == 3
    assert cards["total_size_bytes"] == total_expected_bytes
    assert dash_data["is_stale"] is False

    # Check category distribution
    cats = {c["category"]: c for c in dash_data["storage_categories"]}
    assert "Dokumen" in cats or "document" in cats
    assert "Gambar" in cats or "image" in cats

    # Check managed folder entry
    assert len(dash_data["managed_folders"]) == 1
    mf = dash_data["managed_folders"][0]
    assert mf["id"] == folder_id
    assert mf["size_bytes"] == total_expected_bytes
    assert mf["files_count"] == 3
    assert mf["is_accessible"] is True
    assert mf["last_scanned_at"] is not None

    # 5. File Manager Browse consumes actual filesystem directory
    browse_root = await async_client.get(f"/api/v1/fs/browse?folder_id={folder_id}&relative_path=")
    assert browse_root.status_code == 200
    root_entries = browse_root.json()["entries"]
    entry_names = [e["name"] for e in root_entries]
    assert "report.pdf" in entry_names
    assert "photo.jpg" in entry_names
    assert "subfolder" in entry_names

    # Check specific metadata
    pdf_item = next(e for e in root_entries if e["name"] == "report.pdf")
    assert pdf_item["size_bytes"] == 1024
    assert pdf_item["category"] == "document"
    assert pdf_item["is_inaccessible"] is False


@pytest.mark.asyncio
async def test_refresh_reads_persisted_state_without_scanning(async_client: AsyncClient, tmp_path):
    """Verifies that calling refresh reads persisted DB state and does not trigger disk scans."""
    test_root = tmp_path / "RefreshFolder"
    test_root.mkdir()
    (test_root / "test.txt").write_text("persisted data")

    reg = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "RefreshFolder", "root_path": str(test_root.resolve())},
    )
    folder_id = reg.json()["id"]

    # Initial scan
    await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": folder_id, "calculate_hashes": False},
    )

    # Count jobs after scan
    dash1 = await async_client.get("/api/v1/dashboard/overview")
    jobs_count_1 = len(dash1.json()["jobs"])
    refreshed_at_1 = dash1.json()["last_refreshed_at"]

    # Refresh 10 times in succession
    for _ in range(5):
        dash_n = await async_client.get("/api/v1/dashboard/overview")
        assert dash_n.status_code == 200
        # Jobs count should NOT increase from read-only overview
        assert len(dash_n.json()["jobs"]) == jobs_count_1
        assert dash_n.json()["summary_cards"]["managed_folders_count"] == 1


@pytest.mark.asyncio
async def test_inaccessible_folder_detection_and_safety(async_client: AsyncClient, tmp_path):
    """Verifies that deleted or inaccessible managed folders are flagged safely in API."""
    temp_folder = tmp_path / "WillBeDeleted"
    temp_folder.mkdir()

    reg = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "WillBeDeleted", "root_path": str(temp_folder.resolve())},
    )
    folder_id = reg.json()["id"]

    # Physically delete the directory from disk
    import shutil
    shutil.rmtree(temp_folder)

    # Dashboard overview should gracefully report is_accessible=False without throwing 500
    res = await async_client.get("/api/v1/dashboard/overview")
    assert res.status_code == 200
    data = res.json()
    folder_item = next(f for f in data["managed_folders"] if f["id"] == folder_id)
    assert folder_item["is_accessible"] is False

    # Browse should return a safe 400 or actionable error without crashing
    browse_res = await async_client.get(f"/api/v1/fs/browse?folder_id={folder_id}&relative_path=")
    assert browse_res.status_code in (400, 404)
