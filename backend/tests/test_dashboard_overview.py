import pytest
from httpx import AsyncClient

from backend.app.db.models.file import FileRecord
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.change_plan import ChangePlan
from backend.app.db.session import get_db
from backend.app.main import app


@pytest.mark.asyncio
async def test_get_dashboard_overview_empty(async_client: AsyncClient):
    """Verifies dashboard overview returns clean empty state without errors."""
    response = await async_client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()
    assert "summary_cards" in data
    assert data["summary_cards"]["managed_folders_count"] == 0
    assert data["summary_cards"]["total_files_count"] == 0
    assert data["summary_cards"]["total_size_bytes"] == 0
    assert data["summary_cards"]["pending_changes_count"] == 0
    assert "storage_categories" in data
    assert "folder_distribution" in data
    assert "managed_folders" in data
    assert "recent_activities" in data
    assert "recommendations" in data
    assert "jobs" in data
    assert "storage_history" in data
    assert data["is_stale"] is False


@pytest.mark.asyncio
async def test_get_dashboard_overview_populated(async_client: AsyncClient, tmp_path):
    """Verifies summary cards, storage categories, and folder distributions with data."""
    test_folder = tmp_path / "DashboardTest"
    test_folder.mkdir()

    # Register folder via API
    create_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "DashboardTest", "root_path": str(test_folder.resolve())},
    )
    assert create_res.status_code == 201
    folder_data = create_res.json()
    folder_id = folder_data["id"]

    # Create dummy files on disk and trigger metadata scan
    (test_folder / "doc1.pdf").write_bytes(b"A" * 2048)
    (test_folder / "img1.png").write_bytes(b"B" * 4096)

    scan_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": folder_id, "calculate_hashes": False},
    )
    assert scan_res.status_code == 200

    # Create a change plan via transactions API
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Pending Plan",
        "items": [
            {
                "operation": "rename",
                "source_relative_path": "doc1.pdf",
                "destination_relative_path": "renamed_doc.pdf",
            }
        ],
    }
    plan_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert plan_res.status_code == 201

    # Now get dashboard overview
    response = await async_client.get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    data = response.json()

    cards = data["summary_cards"]
    assert cards["managed_folders_count"] == 1
    assert cards["total_files_count"] == 2
    assert cards["total_size_bytes"] == 6144
    assert cards["pending_changes_count"] == 1

    # Check folder distribution
    assert len(data["folder_distribution"]) == 1
    assert data["folder_distribution"][0]["name"] == "DashboardTest"
    assert data["folder_distribution"][0]["size_bytes"] == 6144

    # Check managed folders
    assert len(data["managed_folders"]) == 1
    assert data["managed_folders"][0]["id"] == folder_id
    assert data["managed_folders"][0]["is_accessible"] is True

    # Check recommendations
    assert len(data["recommendations"]) >= 1


@pytest.mark.asyncio
async def test_trigger_dashboard_analyze_metadata(async_client: AsyncClient, tmp_path):
    """Verifies the analyze action triggers a metadata scan job without error."""
    test_folder = tmp_path / "AnalyzeFolder"
    test_folder.mkdir()
    (test_folder / "file.txt").write_text("sample content")

    create_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "AnalyzeFolder", "root_path": str(test_folder.resolve())},
    )
    assert create_res.status_code == 201
    folder_id = create_res.json()["id"]

    response = await async_client.post(
        "/api/v1/dashboard/analyze",
        json={"folder_id": folder_id, "mode": "metadata"},
    )
    assert response.status_code == 200
    job = response.json()
    assert job["status"] == "completed"
    assert job["progress_percent"] == 100
    assert "AnalyzeFolder" in job["job_name"]
