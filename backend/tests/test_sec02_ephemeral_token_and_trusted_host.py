import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from backend.app.core.security import get_or_create_app_token, reset_app_token
from backend.app.main import app


@pytest.fixture
def clean_token():
    token = reset_app_token()
    yield token


@pytest.mark.asyncio
async def test_session_token_generation_and_handshake():
    """Verify runtime ephemeral session token generation and /auth/session handshake endpoint."""
    token = get_or_create_app_token()
    assert len(token) == 64  # 32 bytes hex encoded
    assert token == get_or_create_app_token()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Handshake endpoint is unauthenticated
        res = await client.get("/api/v1/auth/session")
        assert res.status_code == 200
        data = res.json()
        assert data["token"] == token
        assert data["status"] == "active"


@pytest.mark.asyncio
async def test_exempt_endpoints_without_token():
    """Verify public system routes (health check, root, openapi, auth handshake) require no token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Root redirect
        res_root = await client.get("/")
        assert res_root.status_code == 200

        # 2. Health check probe
        res_health = await client.get("/api/v1/health")
        assert res_health.status_code == 200

        # 3. Auth session handshake
        res_auth = await client.get("/api/v1/auth/session")
        assert res_auth.status_code == 200

        # 4. OpenAPI spec
        res_spec = await client.get("/api/v1/openapi.json")
        assert res_spec.status_code == 200


@pytest.mark.asyncio
async def test_protected_endpoints_rejected_without_token():
    """Verify API data and mutation endpoints return 401 when X-App-Token is omitted."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Folders
        res1 = await client.get("/api/v1/folders")
        assert res1.status_code == 401
        assert "Autentikasi sesi aplikasi lokal diperlukan" in res1.json()["detail"]

        # Settings
        res2 = await client.get("/api/v1/settings/all")
        assert res2.status_code == 401

        # Dashboard
        res3 = await client.get("/api/v1/dashboard/overview")
        assert res3.status_code == 401

        # Filesystem
        res4 = await client.get("/api/v1/fs/browse?folder_id=dummy")
        assert res4.status_code == 401

        # Mutations (create transaction)
        res5 = await client.post("/api/v1/transactions/create", json={"operations": []})
        assert res5.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoints_rejected_with_invalid_token():
    """Verify requests with forged or invalid X-App-Token are rejected with 401."""
    transport = ASGITransport(app=app)
    headers = {"X-App-Token": "forged_malicious_token_abcdef123456"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as client:
        res = await client.get("/api/v1/folders")
        assert res.status_code == 401
        assert "Autentikasi sesi aplikasi lokal diperlukan" in res.json()["detail"]


@pytest.mark.asyncio
async def test_protected_endpoints_accepted_with_valid_token(async_client: AsyncClient):
    """Verify requests with valid X-App-Token succeed as expected."""
    # async_client in conftest is pre-configured with valid X-App-Token
    res = await async_client.get("/api/v1/folders")
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_cors_options_preflight_exempt():
    """Verify CORS preflight OPTIONS requests do not require X-App-Token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.options(
            "/api/v1/folders",
            headers={
                "Origin": "http://localhost:1420",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-App-Token, Content-Type",
            },
        )
        assert res.status_code == 200
        assert "access-control-allow-origin" in res.headers


@pytest.mark.asyncio
async def test_trusted_host_protection_against_dns_rebinding():
    """Verify TrustedHostMiddleware blocks requests targeting invalid/rebinding host headers."""
    transport = ASGITransport(app=app)
    token = get_or_create_app_token()

    # 1. Blocked host (attacker.com DNS rebinding target)
    async with AsyncClient(
        transport=transport,
        base_url="http://attacker.com",
        headers={"Host": "attacker.com", "X-App-Token": token},
    ) as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 400
        assert "Invalid host header" in res.text

    # 2. Blocked host variation (rebind.local)
    async with AsyncClient(
        transport=transport,
        base_url="http://rebind.local",
        headers={"Host": "rebind.local", "X-App-Token": token},
    ) as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 400

    # 3. Permitted host (localhost)
    async with AsyncClient(
        transport=transport,
        base_url="http://localhost:8000",
        headers={"Host": "localhost:8000", "X-App-Token": token},
    ) as client:
        res = await client.get("/api/v1/health")
        assert res.status_code == 200
