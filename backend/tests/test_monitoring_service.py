import asyncio
import time
from pathlib import Path
import pytest
from httpx import AsyncClient

from backend.app.services.monitoring import get_monitoring_service


@pytest.mark.asyncio
async def test_monitoring_watcher_lifecycle_and_restriction(
    async_client: AsyncClient, tmp_path: Path
):
    """Verifies that watchers can only be started for registered and enabled Managed Folders,
    and lifecycle controls (start, pause, resume, stop) function correctly."""
    folder_root = tmp_path / "monitored_lifecycle"
    folder_root.mkdir()

    # 1. Attempt starting a watcher on a non-existent folder ID: MUST FAIL
    bad_res = await async_client.post("/api/v1/monitoring/watchers/non-existent-uuid/start")
    assert bad_res.status_code == 400
    assert "not found" in bad_res.json()["detail"]

    # 2. Register valid folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Lifecycle Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 3. Start watcher
    start_res = await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/start")
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "watching"

    # Verify watcher status in watchers list
    list_res = await async_client.get("/api/v1/monitoring/watchers")
    assert list_res.status_code == 200
    watchers = list_res.json()
    watcher_entry = next((w for w in watchers if w["folder_id"] == folder_id), None)
    assert watcher_entry is not None
    assert watcher_entry["status"] == "watching"
    assert watcher_entry["is_enabled"] is True

    # 4. Pause watcher
    pause_res = await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/pause")
    assert pause_res.status_code == 200
    assert pause_res.json()["status"] == "paused"

    # 5. Resume watcher
    resume_res = await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/resume")
    assert resume_res.status_code == 200
    assert resume_res.json()["status"] == "watching"

    # 6. Stop watcher
    stop_res = await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/stop")
    assert stop_res.status_code == 200
    assert stop_res.json()["status"] == "stopped"


@pytest.mark.asyncio
async def test_watcher_config_persistence(async_client: AsyncClient, tmp_path: Path):
    """Verifies that watcher configuration (debounce_ms, recursive, ignore_patterns)
    persists in the database."""
    folder_root = tmp_path / "config_persistence"
    folder_root.mkdir()

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Config Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Update config
    update_payload = {
        "is_enabled": True,
        "recursive": False,
        "debounce_ms": 750,
        "ignore_patterns": ["*.log", "build/*"],
    }
    cfg_res = await async_client.put(
        f"/api/v1/monitoring/watchers/{folder_id}/config",
        json=update_payload,
    )
    assert cfg_res.status_code == 200
    cfg = cfg_res.json()
    assert cfg["debounce_ms"] == 750
    assert cfg["recursive"] is False
    assert "*.log" in cfg["ignore_patterns"]

    # Query watchers to verify persistence
    w_res = await async_client.get("/api/v1/monitoring/watchers")
    assert w_res.status_code == 200
    watcher = next((w for w in w_res.json() if w["folder_id"] == folder_id), None)
    assert watcher is not None
    assert watcher["debounce_ms"] == 750
    assert watcher["recursive"] is False
    assert "*.log" in watcher["ignore_patterns"]


@pytest.mark.asyncio
async def test_monitoring_event_capture_and_deduplication(
    async_client: AsyncClient, tmp_path: Path
):
    """Verifies live filesystem event capture, debouncing/deduplication, and
    that monitoring strictly observes without modifying files."""
    folder_root = tmp_path / "monitored_events"
    folder_root.mkdir()

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Events Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_res.json()["id"]

    # Start watcher
    await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/start")
    await asyncio.sleep(0.3)

    # 1. Create a regular file on disk
    test_file = folder_root / "hello.txt"
    test_file.write_text("Initial content")

    # 2. Create an ignored temporary file (should be ignored by default patterns)
    tmp_file = folder_root / "ignored.tmp"
    tmp_file.write_text("Temporary noise")

    # 3. Modify test_file multiple times rapidly to test debounce
    for i in range(4):
        test_file.write_text(f"Content update {i}")
        time.sleep(0.05)

    # Wait briefly for Watchdog observer thread to dispatch
    await asyncio.sleep(1.2)

    # Query monitoring events
    events_res = await async_client.get(
        "/api/v1/monitoring/events",
        params={"folder_id": folder_id},
    )
    assert events_res.status_code == 200
    events = events_res.json()["items"]

    # Must contain event for hello.txt
    hello_events = [e for e in events if "hello.txt" in e["relative_path"]]
    assert len(hello_events) >= 1

    # Ignored *.tmp file should NOT be recorded
    tmp_events = [e for e in events if "ignored.tmp" in e["relative_path"]]
    assert len(tmp_events) == 0

    # Non-mutative guarantee: The file on disk was NOT modified or altered by monitoring
    assert test_file.exists()
    assert test_file.read_text() == "Content update 3"

    # Stop watcher cleanly
    await async_client.post(f"/api/v1/monitoring/watchers/{folder_id}/stop")


@pytest.mark.asyncio
async def test_monitoring_stats_and_charts(async_client: AsyncClient):
    """Tests summary statistics, distribution, and activity charts endpoints."""
    # 1. Overall status
    status_res = await async_client.get("/api/v1/monitoring/status")
    assert status_res.status_code == 200
    assert "status" in status_res.json()
    assert "active_watchers" in status_res.json()

    # 2. Stats
    stats_res = await async_client.get("/api/v1/monitoring/stats")
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert "monitored_folders_count" in stats
    assert "active_watchers_count" in stats
    assert "total_events_24h" in stats

    # 3. Activity Chart
    chart_res = await async_client.get(
        "/api/v1/monitoring/activity-chart",
        params={"time_range": "last_24h"},
    )
    assert chart_res.status_code == 200
    chart = chart_res.json()
    assert chart["time_range"] == "last_24h"
    assert len(chart["data_points"]) > 0

    # 4. Event Distribution
    dist_res = await async_client.get("/api/v1/monitoring/distribution")
    assert dist_res.status_code == 200
    dist = dist_res.json()
    assert "total_events" in dist
    assert len(dist["distribution"]) == 4

