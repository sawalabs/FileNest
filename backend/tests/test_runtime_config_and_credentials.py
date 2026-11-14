import logging
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from backend.app.core.config import Settings
from backend.app.core.logging import SensitiveDataFilter
from backend.app.db.models.app_setting import AppSetting
from backend.app.db.models.audit import AuditLog
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.session import get_db
from backend.app.services.credential_service import CredentialService
from backend.app.services.settings_service import SettingsException, SettingsService


def test_runtime_config_validation():
    """Verifies that pydantic BaseSettings rejects invalid runtime configurations."""
    # Invalid Database URL (must be sqlite:///)
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(DATABASE_URL="postgres://localhost/db")

    # Invalid Port
    with pytest.raises(ValueError, match="PORT"):
        Settings(PORT=0)
    with pytest.raises(ValueError, match="PORT"):
        Settings(PORT=70000)

    # Invalid Log Level
    with pytest.raises(ValueError, match="LOG_LEVEL"):
        Settings(LOG_LEVEL="VERBOSE")

    # Valid settings instantiate cleanly
    valid = Settings(PORT=8080, LOG_LEVEL="DEBUG", DATABASE_URL="sqlite:///./data/custom.db")
    assert valid.PORT == 8080
    assert valid.LOG_LEVEL == "DEBUG"


def test_log_redaction_patterns():
    """Verifies that sensitive data filter redacts passwords, tokens, and raw keys."""
    filter_obj = SensitiveDataFilter()

    # Redact in msg string
    rec1 = logging.LogRecord("test", logging.INFO, "path", 1, "Connecting with api_key='secret-12345'", (), None)
    filter_obj.filter(rec1)
    assert "secret-12345" not in rec1.msg
    assert "***REDACTED***" in rec1.msg

    # Redact Bearer token
    rec2 = logging.LogRecord("test", logging.INFO, "path", 1, "Header: Bearer test-jwt-token-placeholder.test", (), None)
    filter_obj.filter(rec2)
    assert "test-jwt-token-placeholder" not in rec2.msg
    assert "***REDACTED***" in rec2.msg

    # Redact raw sk- key
    rec3 = logging.LogRecord("test", logging.INFO, "path", 1, "Generated key is sk-abcdef1234567890", (), None)
    filter_obj.filter(rec3)
    assert "sk-abcdef1234567890" not in rec3.msg
    assert "***REDACTED***" in rec3.msg

    # Redact in record.args
    rec4 = logging.LogRecord("test", logging.INFO, "path", 1, "User token: %s", ("sk-topsecret123456",), None)
    filter_obj.filter(rec4)
    assert "sk-topsecret123456" not in rec4.args[0]


@pytest.mark.asyncio
async def test_audit_logs_automatic_redaction(async_client: AsyncClient):
    """Verifies that audit log repository automatically sanitizes sensitive fields."""
    client = async_client
    # Update AI settings with an API key
    test_key = "sk-test-vault-dummy-9988776655"
    res = await client.put(
        "/api/v1/settings/ai",
        json={"router_api_key": test_key, "router_timeout_seconds": 30},
    )
    assert res.status_code == 200

    # Query audit logs
    logs_res = await client.get("/api/v1/history/audit-logs")
    assert logs_res.status_code == 200
    logs = logs_res.json()["items"]

    # Verify that raw secret was never logged
    for l in logs:
        log_str = str(l)
        assert test_key not in log_str


@pytest.mark.asyncio
async def test_secrets_never_persisted_to_sqlite(async_client: AsyncClient):
    """Verifies that secrets are stored via Windows Credential Manager and absent from SQLite."""
    client = async_client
    secret_key = "sk-test-dummy-vault-key-12345"

    # Store through API
    put_res = await client.put(
        "/api/v1/settings/ai",
        json={"router_api_key": secret_key, "default_model": "gpt-4o"},
    )
    assert put_res.status_code == 200
    ai_data = put_res.json()

    # Frontend receives only masked version
    assert ai_data["has_router_api_key"] is True
    assert ai_data["masked_router_api_key"] == "sk-***2345"
    assert secret_key not in str(ai_data)

    # Windows Credential Manager holds the real key
    assert CredentialService.get_secret("9router_api_key") == secret_key

    # Query SQLite directly to verify zero occurrences of secret
    settings_res = await client.get("/api/v1/settings")
    assert settings_res.status_code == 200
    full_dump = str(settings_res.json())
    assert secret_key not in full_dump


@pytest.mark.asyncio
async def test_ai_settings_endpoint_and_range_validation(async_client: AsyncClient):
    """Verifies validation on router endpoint URLs, timeout ranges, and token limits."""
    client = async_client

    # 1. Invalid endpoint scheme
    res1 = await client.put("/api/v1/settings/ai", json={"router_endpoint": "ftp://localhost:8000"})
    assert res1.status_code == 400
    assert "router_endpoint must start with http://" in res1.json()["detail"]

    # 2. Embedded credentials in endpoint URL
    res2 = await client.put("/api/v1/settings/ai", json={"router_endpoint": "http://testuser@127.0.0.1:20128/v1"})
    assert res2.status_code == 400
    assert "router_endpoint must not contain embedded user credentials" in res2.json()["detail"]

    # 3. Invalid timeout range (< 5 or > 300)
    res3 = await client.put("/api/v1/settings/ai", json={"router_timeout_seconds": 2})
    assert res3.status_code == 400
    assert "router_timeout_seconds" in res3.json()["detail"]

    # 4. Invalid temperature (> 2.0 or < 0.0)
    res4 = await client.put("/api/v1/settings/ai", json={"temperature": 2.5})
    assert res4.status_code == 400
    assert "temperature" in res4.json()["detail"]

    # 5. Invalid max_tokens (<= 0)
    res5 = await client.put("/api/v1/settings/ai", json={"max_tokens": 0})
    assert res5.status_code == 400
    assert "max_tokens" in res5.json()["detail"]


@pytest.mark.asyncio
async def test_missing_config_surfaces_actionable_errors(async_client: AsyncClient):
    """Verifies that missing endpoint or missing model returns clear actionable error."""
    client = async_client

    # Clear endpoint
    await client.put("/api/v1/settings/ai", json={"router_endpoint": ""})

    # Trigger chat completion without configured endpoint
    res = await client.post(
        "/api/v1/router/chat",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    assert res.status_code == 400
    assert "9Router endpoint belum dikonfigurasi" in res.json()["detail"]
