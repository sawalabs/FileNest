import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient

from backend.app.schemas.router_gateway import (
    RouterChatMessage,
    RouterChatRequest,
    RouterHealthResponse,
    RouterModelItem,
    RouterModelListResponse,
)
from backend.app.services.credential_service import CredentialService
from backend.app.services.router_gateway import (
    RouterGatewayException,
    RouterGatewayService,
)


@pytest.mark.asyncio
async def test_9router_connectivity_diagnostics(async_client: AsyncClient):
    """Verifies that 9Router health checks diagnose connected, disconnected, unauthorized,
    and unconfigured states with precise messages and latency metrics."""

    # 1. Connected state with dynamic models count
    mock_ok = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={"data": [{"id": "meta-llama/Llama-3-8B"}, {"id": "mistralai/Mistral-7B"}]},
    )
    with patch.object(RouterGatewayService, "_get_from_gateway", new_callable=AsyncMock, return_value=mock_ok):
        res = await async_client.get("/api/v1/router/health?endpoint=http://127.0.0.1:20128/v1")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "connected"
        assert data["models_count"] == 2
        assert data["latency_ms"] is not None

    # 2. 401 Unauthorized diagnosis
    mock_401 = httpx.Response(status_code=401, text="Unauthorized: invalid api key")
    with patch.object(RouterGatewayService, "_get_from_gateway", new_callable=AsyncMock, return_value=mock_401):
        res = await async_client.get("/api/v1/router/health?endpoint=http://127.0.0.1:20128/v1")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "unauthorized"
        assert "401" in data["message"] or "ditolak" in data["message"]

    # 3. Timeout diagnosis
    with patch.object(RouterGatewayService, "_get_from_gateway", side_effect=httpx.TimeoutException("Connection timed out")):
        res = await async_client.get("/api/v1/router/health?endpoint=http://127.0.0.1:20128/v1&timeout=2")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "disconnected"
        assert "Timeout" in data["message"]

    # 4. Not configured when endpoint is empty
    res_empty = await async_client.get("/api/v1/router/health?endpoint=")
    assert res_empty.status_code == 200
    assert res_empty.json()["status"] == "not_configured"


@pytest.mark.asyncio
async def test_dynamic_model_discovery_without_hardcoded_ids(async_client: AsyncClient):
    """Verifies that model discovery accepts arbitrary models served by 9Router without hardcoding."""

    arbitrary_remote_models = {
        "data": [
            {"id": "qwen2.5-72b-instruct", "owned_by": "alibaba", "context_window": 131072},
            {"id": "deepseek-coder-v2", "owned_by": "deepseek", "context_window": 65536},
            {"id": "custom-finetuned-classifier", "owned_by": "local-org", "context_window": 32768},
        ]
    }
    mock_res = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json=arbitrary_remote_models,
    )
    with patch.object(RouterGatewayService, "_get_from_gateway", new_callable=AsyncMock, return_value=mock_res):
        res = await async_client.get("/api/v1/router/models?endpoint=http://127.0.0.1:20128/v1")
        assert res.status_code == 200
        data = res.json()
        assert data["source"] == "remote"
        assert data["total_count"] == 3
        model_ids = [m["id"] for m in data["models"]]
        assert "qwen2.5-72b-instruct" in model_ids
        assert "deepseek-coder-v2" in model_ids
        assert "custom-finetuned-classifier" in model_ids


@pytest.mark.asyncio
async def test_provider_errors_mapping_and_retries(async_client: AsyncClient):
    """Verifies mapping of 403 Forbidden, 404 Not Found, 429 Rate Limit, and retry on transient 502/503."""

    # 1. 403 Forbidden
    mock_403 = httpx.Response(status_code=403, text="Forbidden access to model")
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_403):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"model": "restricted-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert res.status_code == 400
        assert "403" in res.json()["detail"] or "Akses ke model atau endpoint ditolak" in res.json()["detail"]

    # 2. 404 Not Found
    mock_404 = httpx.Response(status_code=404, text="Model not found")
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_404):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"model": "non-existent-model", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert res.status_code == 400
        assert "404" in res.json()["detail"] or "tidak ditemukan" in res.json()["detail"]

    # 3. 429 Rate Limit
    mock_429 = httpx.Response(status_code=429, text="Rate limit exceeded")
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_429):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hi"}]},
        )
        assert res.status_code == 400
        assert "429" in res.json()["detail"] or "rate limit" in res.json()["detail"].lower()

    # 4. Transient 502 Gateway Error -> Retries and succeeds on second attempt
    mock_502 = httpx.Response(status_code=502, text="Bad Gateway")
    mock_success = httpx.Response(
        status_code=200,
        headers={"content-type": "application/json"},
        json={
            "id": "chatcmpl_retry_ok",
            "choices": [{"message": {"role": "assistant", "content": "Recovered after retry."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
        },
    )
    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, side_effect=[mock_502, mock_success]):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={"model": "gpt-4o-mini", "messages": [{"role": "user", "content": "Hello after retry"}]},
        )
        assert res.status_code == 200
        assert res.json()["content"] == "Recovered after retry."


@pytest.mark.asyncio
async def test_ai_output_remains_advisory_cannot_bypass_approval(async_client: AsyncClient, tmp_path):
    """Verifies that AI specialist tools produce draft structured plans only and
    CANNOT bypass the approval check or execute filesystem changes directly."""

    test_folder = tmp_path / "ai_advisory_folder"
    test_folder.mkdir(parents=True, exist_ok=True)
    (test_folder / "old_name_2026.txt").write_text("sample content")

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "AI Advisory Test Folder", "root_path": str(test_folder)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Request plan creation from AI specialist tool
    res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "plan_create_rename",
            "arguments": {
                "managed_folder_id": folder_id,
                "title": "Smart AI Rename Proposal",
                "renames": [
                    {
                        "source_relative_path": "old_name_2026.txt",
                        "new_file_name": "renamed_by_ai_2026.txt",
                    }
                ],
            },
        },
    )
    assert res.status_code == 200
    plan_data = res.json()["data"]
    assert plan_data["status"] in ("draft", "pending_review")
    assert plan_data["requires_approval"] is True
    plan_id = plan_data["plan_id"]

    # Verify that the file on disk was NOT renamed yet (strict advisory check)
    assert (test_folder / "old_name_2026.txt").exists()
    assert not (test_folder / "renamed_by_ai_2026.txt").exists()

    # Attempting to execute unapproved plan directly via transaction execution endpoint must fail
    exec_res = await async_client.post(
        f"/api/v1/transactions/plans/{plan_id}/execute",
        json={},
    )
    # Execution requires approved status
    assert exec_res.status_code == 400
    assert "approved" in exec_res.json()["detail"].lower()
