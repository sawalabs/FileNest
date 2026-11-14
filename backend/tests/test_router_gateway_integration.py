import json
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import AsyncClient

from backend.app.schemas.router_gateway import RouterHealthResponse, RouterModelListResponse
from backend.app.services.credential_service import CredentialService
from backend.app.services.router_gateway import RouterGatewayService


@pytest.mark.asyncio
async def test_router_health_check_disconnected(async_client: AsyncClient):
    """Verifies 9Router health check returns disconnected without unhandled errors when unreachable."""
    res = await async_client.get("/api/v1/router/health?endpoint=http://127.0.0.1:59998&timeout=1")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("disconnected", "not_configured")
    assert "127.0.0.1:59998" in data["endpoint"]
    assert data["latency_ms"] is not None


@pytest.mark.asyncio
async def test_router_health_check_connected_mock(async_client: AsyncClient):
    """Verifies health check surfaces connected state, latency, and models count."""
    mock_health = RouterHealthResponse(
        status="connected",
        endpoint="http://127.0.0.1:20128/v1",
        latency_ms=14.2,
        message="Koneksi ke 9Router gateway berhasil.",
        authenticated=True,
        models_count=5,
    )
    with patch.object(RouterGatewayService, "check_health", new_callable=AsyncMock, return_value=mock_health):
        res = await async_client.get("/api/v1/router/health?endpoint=http://127.0.0.1:20128/v1")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "connected"
        assert data["latency_ms"] == 14.2
        assert data["models_count"] == 5
        assert data["authenticated"] is True


@pytest.mark.asyncio
async def test_router_model_discovery_remote_mock(async_client: AsyncClient):
    """Verifies dynamic model discovery from 9Router OpenAI-compatible models list."""
    mock_models_response = RouterModelListResponse(
        models=[
            {"id": "gpt-4o", "name": "GPT-4o", "context_length": 128000, "provider": "openai", "supports_vision": True, "is_default": True},
            {"id": "claude-3-5-sonnet", "name": "Claude 3.5 Sonnet", "context_length": 200000, "provider": "anthropic", "supports_vision": True, "is_default": False},
        ],
        source="remote",
        total_count=2,
    )
    with patch.object(RouterGatewayService, "discover_models", new_callable=AsyncMock, return_value=mock_models_response):
        res = await async_client.get("/api/v1/router/models")
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "remote"
        assert data["total_count"] == 2
        assert data["models"][0]["id"] == "gpt-4o"
        assert data["models"][1]["id"] == "claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_router_model_discovery_fallback(async_client: AsyncClient):
    """Verifies model discovery cleanly falls back to standard models when 9Router is offline."""
    # Using an unreachable port triggers fallback logic
    res = await async_client.get("/api/v1/router/models?endpoint=http://127.0.0.1:59998")
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "fallback"
    assert data["total_count"] >= 3
    model_ids = [m["id"] for m in data["models"]]
    assert "gpt-4o-mini" in model_ids
    assert "gpt-4o" in model_ids


@pytest.mark.asyncio
async def test_router_chat_completion_success_mock(async_client: AsyncClient):
    """Verifies completion request formats OpenAI payload and records audit log."""
    mock_http_response = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={
            "id": "chatcmpl_abc123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": "File organization plan looks optimal."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 120,
                "completion_tokens": 30,
                "total_tokens": 150,
            },
        },
    )

    # Patch internal gateway caller inside RouterGatewayService
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_http_response):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a file manager assistant."},
                {"role": "user", "content": "Analyze directory structure."},
            ],
            "temperature": 0.2,
        }
        res = await async_client.post("/api/v1/router/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["id"] == "chatcmpl_abc123"
        assert data["content"] == "File organization plan looks optimal."
        assert data["usage"]["total_tokens"] == 150
        assert data["latency_ms"] is not None

    # Check audit log recorded the completion
    audit_res = await async_client.get("/api/v1/history/audit-logs?action=9router_chat_completion")
    assert audit_res.status_code == 200
    logs = audit_res.json()["items"]
    assert len(logs) >= 1
    assert logs[0]["entity_id"] == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_router_chat_completion_json_mode(async_client: AsyncClient):
    """Verifies JSON mode parses and validates structured response payload."""
    json_content = json.dumps({"action": "recommend_rename", "confidence": 0.95})
    mock_http_response = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={
            "id": "chatcmpl_json_123",
            "choices": [
                {
                    "message": {"role": "assistant", "content": json_content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
        },
    )
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_http_response):
        payload = {
            "messages": [{"role": "user", "content": "Generate structured rename JSON"}],
            "json_mode": True,
        }
        res = await async_client.post("/api/v1/router/chat", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["parsed_json"] is not None
        assert data["parsed_json"]["action"] == "recommend_rename"
        assert data["parsed_json"]["confidence"] == 0.95


@pytest.mark.asyncio
async def test_router_credential_isolation(async_client: AsyncClient):
    """Verifies API keys are securely stored via CredentialService and not leaked in SQLite or logs."""
    test_key = "sk-9router-secret-test-key-998877"

    # Save API key via settings patch
    patch_res = await async_client.patch(
        "/api/v1/settings/ai",
        json={"router_api_key": test_key},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["has_router_api_key"] is True
    # Key must be masked in API responses
    assert test_key not in json.dumps(data)
    assert "8877" in data.get("masked_router_api_key", "")

    # Retrieve from secure CredentialService
    retrieved = CredentialService.get_secret(RouterGatewayService.ROUTER_KEY_ID)
    assert retrieved == test_key

    # Verify key is NOT in audit logs
    audit_res = await async_client.get("/api/v1/history/audit-logs")
    assert audit_res.status_code == 200
    audit_text = json.dumps(audit_res.json())
    assert test_key not in audit_text


@pytest.mark.asyncio
async def test_router_unauthorized_and_timeout_errors(async_client: AsyncClient):
    """Verifies 401 Unauthorized and timeout errors return clean HTTP 400 responses."""
    # 1. 401 Unauthorized Mock
    mock_401 = httpx.Response(status_code=401, text="Unauthorized: invalid api key")
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_401):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"messages": [{"role": "user", "content": "Hello"}]},
        )
        assert res.status_code == 400
        assert "401" in res.json()["detail"] or "API key ditolak" in res.json()["detail"]

    # 2. Timeout Mock
    with patch.object(RouterGatewayService, "_post_to_gateway", side_effect=httpx.TimeoutException("Gateway timed out")):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"messages": [{"role": "user", "content": "Hello"}], "timeout_seconds": 1},
        )
        assert res.status_code == 400
        assert "melebihi batas waktu" in res.json()["detail"]
