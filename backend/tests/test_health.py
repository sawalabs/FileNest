import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check_returns_ok(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["project"] == "Desktop & Storage Manager"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert "subsystems" in data
    subsystems = data["subsystems"]
    assert "database" in subsystems
    assert subsystems["database"]["status"] == "ok"
    assert "security" in subsystems
    assert "ai_gateway" in subsystems
    assert "monitoring" in subsystems


@pytest.mark.asyncio
async def test_root_status(async_client: AsyncClient):
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "running"
