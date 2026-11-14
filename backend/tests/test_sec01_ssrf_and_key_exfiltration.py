from unittest.mock import AsyncMock, patch
import httpx
import pytest
from httpx import AsyncClient

from backend.app.core.security import validate_probe_url
from backend.app.services.credential_service import CredentialService
from backend.app.services.router_gateway import RouterGatewayException, RouterGatewayService
from backend.app.services.settings_service import SettingsService


def test_validate_probe_url_valid_cases():
    """Verify standard local and HTTPS endpoints are permitted."""
    assert validate_probe_url("http://localhost:8080/v1") == "http://localhost:8080/v1"
    assert validate_probe_url("http://127.0.0.1:8000/api/v1") == "http://127.0.0.1:8000/api/v1"
    assert validate_probe_url("https://api.openai.com/v1") == "https://api.openai.com/v1"
    assert validate_probe_url("https://9router.internal.corp:8443") == "https://9router.internal.corp:8443"


@pytest.mark.parametrize(
    "invalid_url",
    [
        "file:///etc/passwd",
        "file:///C:/Windows/System32/drivers/etc/hosts",
        "ftp://ftp.example.com/malicious",
        "gopher://127.0.0.1:25/",
        "dict://127.0.0.1:11211/",
        "ldap://localhost:389/",
        "javascript:alert(1)",
        "data:text/plain;base64,SGVsbG8=",
    ],
)
def test_validate_probe_url_invalid_schemes(invalid_url: str):
    """Verify non-HTTP/HTTPS schemes are strictly rejected."""
    with pytest.raises(ValueError, match="Hanya skema http dan https yang didukung"):
        validate_probe_url(invalid_url)


@pytest.mark.parametrize(
    "metadata_ip_url",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://169.254.169.254:8080/",
        "https://169.254.169.254/v1",
        "http://169.254.1.5/test",  # link-local range
        "http://2852039166/v1",  # integer representation of 169.254.169.254
        "http://0xa9fea9fe/v1",  # hex representation of 169.254.169.254
    ],
)
def test_validate_probe_url_cloud_metadata_ips(metadata_ip_url: str):
    """Verify cloud metadata and link-local IP addresses are blocked."""
    with pytest.raises(ValueError, match="(Cloud Metadata|link-local)"):
        validate_probe_url(metadata_ip_url)


@pytest.mark.parametrize(
    "metadata_domain_url",
    [
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://custom.metadata.google.internal/v1",
        "https://metadata.azure.com/metadata/instance",
        "http://instance-data/latest/meta-data",
    ],
)
def test_validate_probe_url_cloud_metadata_domains(metadata_domain_url: str):
    """Verify cloud metadata hostnames are blocked."""
    with pytest.raises(ValueError, match="metadata cloud diblokir"):
        validate_probe_url(metadata_domain_url)


def test_validate_probe_url_userinfo_blocked():
    """Verify embedded userinfo credentials in URL are rejected."""
    with pytest.raises(ValueError, match="kredensial"):
        validate_probe_url("http://admin:secret123@localhost:8080/v1")


@pytest.mark.asyncio
async def test_prevent_api_key_exfiltration_on_untrusted_override(async_client: AsyncClient):
    """Verify stored API key is NEVER attached to unverified endpoint overrides."""
    # Store secret API key
    CredentialService.store_secret(RouterGatewayService.ROUTER_KEY_ID, "sk-super-secret-leaked-key")

    captured_headers = {}

    async def mock_get(url, headers, timeout):
        nonlocal captured_headers
        captured_headers = headers
        return httpx.Response(200, json={"data": []})

    with patch.object(RouterGatewayService, "_get_from_gateway", side_effect=mock_get):
        res = await async_client.get("/api/v1/router/health?endpoint=http://attacker.example.com/v1")
        assert res.status_code == 200

        # Authorization header must NOT be present
        assert "Authorization" not in captured_headers
        assert "sk-super-secret-leaked-key" not in str(captured_headers)


@pytest.mark.asyncio
async def test_allow_stored_api_key_on_saved_endpoint(async_client: AsyncClient):
    """Verify stored API key IS attached when probing the verified saved endpoint."""
    res_set = await async_client.put(
        "/api/v1/settings/ai",
        json={
            "router_endpoint": "http://127.0.0.1:8080/v1",
            "router_api_key": "sk-legitimate-saved-key",
        },
    )
    assert res_set.status_code == 200

    captured_headers = {}

    async def mock_get(url, headers, timeout):
        nonlocal captured_headers
        captured_headers = headers
        return httpx.Response(200, json={"data": []})

    with patch.object(RouterGatewayService, "_get_from_gateway", side_effect=mock_get):
        res = await async_client.get("/api/v1/router/health")
        assert res.status_code == 200

        assert captured_headers.get("Authorization") == "Bearer sk-legitimate-saved-key"


@pytest.mark.asyncio
async def test_discover_models_no_key_exfiltration(async_client: AsyncClient):
    """Verify discover_models does not leak stored API key to custom endpoint."""
    CredentialService.store_secret(RouterGatewayService.ROUTER_KEY_ID, "sk-secret-models-token")

    captured_headers = {}

    async def mock_get(url, headers, timeout):
        nonlocal captured_headers
        captured_headers = headers
        return httpx.Response(200, json={"data": []})

    with patch.object(RouterGatewayService, "_get_from_gateway", side_effect=mock_get):
        res = await async_client.get("/api/v1/router/models?endpoint=http://attacker.example.com/v1")
        assert res.status_code == 200
        assert "Authorization" not in captured_headers


@pytest.mark.asyncio
async def test_settings_test_9router_connection_ssrf_blocked(async_client: AsyncClient):
    """Verify Settings test connection endpoint rejects SSRF metadata targets."""
    res = await async_client.post(
        "/api/v1/settings/ai/9router/test",
        json={"endpoint": "http://169.254.169.254/latest/meta-data"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert data["status"] == "error"
    assert "diblokir" in data["message"]


@pytest.mark.asyncio
async def test_error_handling_no_raw_response_body_leakage(async_client: AsyncClient):
    """Verify error messages do not leak raw response body from gateway."""
    mock_bad_response = httpx.Response(
        status_code=500,
        text="INTERNAL_ERROR: sensitive_database_credentials_exposed_xyz123",
    )

    with patch.object(RouterGatewayService, "_get_from_gateway", return_value=mock_bad_response):
        res = await async_client.get("/api/v1/router/health?endpoint=http://localhost:8080/v1")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "error"
        assert "sensitive_database_credentials" not in data["message"]
        assert "INTERNAL_ERROR" not in data["message"]
        assert data["message"] == "9Router mengembalikan status HTTP 500."
