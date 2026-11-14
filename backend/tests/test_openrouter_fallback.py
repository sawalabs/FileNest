from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import AsyncClient

from backend.app.services.credential_service import CredentialService
from backend.app.services.router_gateway import RouterGatewayService


@pytest.mark.asyncio
async def test_openrouter_test_endpoint_unauthorized(async_client: AsyncClient):
    """Testing OpenRouter connection without a key returns unauthorized status."""
    with patch.object(CredentialService, "get_secret", return_value=None):
        res = await async_client.post(
            "/api/v1/settings/ai/openrouter/test",
            json={"endpoint": "https://openrouter.ai/api/v1"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is False
        assert data["status"] == "unauthorized"


@pytest.mark.asyncio
async def test_openrouter_test_endpoint_success(async_client: AsyncClient):
    """Testing OpenRouter connection with valid key returns success."""
    mock_response = httpx.Response(
        status_code=200,
        json={"data": [{"id": "google/gemini-2.5-flash"}, {"id": "openai/gpt-4o"}]},
        request=httpx.Request("GET", "https://openrouter.ai/api/v1/models"),
    )
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        res = await async_client.post(
            "/api/v1/settings/ai/openrouter/test",
            json={"endpoint": "https://openrouter.ai/api/v1", "api_key": "sk-test-openrouter-dummy-key"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["status"] == "connected"
        assert "2 model tersedia" in data["message"]


@pytest.mark.asyncio
async def test_chat_completion_auto_fallback_when_9router_fails(async_client: AsyncClient):
    """When 9Router fails with 5xx/530 and auto_fallback is enabled, automatically route to OpenRouter."""
    # Update AI settings to enable auto fallback
    update_res = await async_client.put(
        "/api/v1/settings/ai",
        json={
            "router_endpoint": "https://9router.example.com/v1",
            "default_model": "gpt-4o-mini",
            "auto_fallback_enabled": True,
            "openrouter_endpoint": "https://openrouter.ai/api/v1",
            "openrouter_model": "google/gemini-2.5-flash",
            "openrouter_api_key": "sk-test-openrouter-mock-key",
        },
    )
    assert update_res.status_code == 200

    def mock_post(url, headers, json, timeout):
        if "9router.example.com" in url:
            return httpx.Response(
                status_code=530,
                text="Cloudflare Tunnel 1033 Error",
                request=httpx.Request("POST", url),
            )
        elif "openrouter.ai" in url:
            return httpx.Response(
                status_code=200,
                json={
                    "id": "gen-openrouter-12345",
                    "choices": [
                        {
                            "message": {
                                "role": "assistant",
                                "content": "Halo! Ini jawaban fallback dari OpenRouter.",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 15,
                        "completion_tokens": 10,
                        "total_tokens": 25,
                    },
                },
                request=httpx.Request("POST", url),
            )
        raise ValueError(f"Unexpected target url: {url}")

    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, side_effect=mock_post):
        with patch.object(CredentialService, "get_secret", return_value="sk-test-openrouter-mock-key"):
            res = await async_client.post(
                "/api/v1/router/chat",
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": "Halo AI"}],
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["fallback_triggered"] is True
            assert "OpenRouter" in data["provider_used"]
            assert "Halo! Ini jawaban fallback dari OpenRouter." in data["content"]
            assert data["usage"]["total_tokens"] == 25


@pytest.mark.asyncio
async def test_chat_completion_no_fallback_when_disabled(async_client: AsyncClient):
    """When auto_fallback_enabled is False, 9Router error is raised directly."""
    # Update AI settings to disable auto fallback
    update_res = await async_client.put(
        "/api/v1/settings/ai",
        json={
            "router_endpoint": "https://9router.example.com/v1",
            "default_model": "gpt-4o-mini",
            "auto_fallback_enabled": False,
        },
    )
    assert update_res.status_code == 200

    mock_error_resp = httpx.Response(
        status_code=530,
        text="Cloudflare Error",
        request=httpx.Request("POST", "https://9router.example.com/v1/chat/completions"),
    )

    with patch.object(RouterGatewayService, "_post_to_gateway", new_callable=AsyncMock, return_value=mock_error_resp):
        res = await async_client.post(
            "/api/v1/router/chat",
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": "Halo AI"}],
            },
        )
        assert res.status_code == 400
        data = res.json()
        assert "530" in data["detail"]
