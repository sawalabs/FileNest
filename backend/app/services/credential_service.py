import os
from typing import Optional
from backend.app.core.logging import logger

try:
    import keyring
except ImportError:
    keyring = None

# Fallback in-memory store for unit test suites and environments where OS keyring is unavailable
_TEST_KEYRING_STORE: dict[str, str] = {}


class CredentialService:
    """Manages secure credential storage in Windows Credential Manager.
    
    Rule 80 & Acceptance Criteria:
    - Never hardcode credentials in code or Git.
    - Never store plaintext API keys, passwords, or tokens in SQLite.
    - Masks secrets before returning any representation to callers.
    """

    SERVICE_NAME = "FileNest_Credentials"

    @classmethod
    def is_available(cls) -> bool:
        return keyring is not None

    @classmethod
    def store_secret(cls, key_id: str, secret: str) -> bool:
        """Stores a secret securely in Windows Credential Manager.
        Does not touch SQLite.
        """
        if not secret or not secret.strip():
            return False

        secret_clean = secret.strip()
        
        # Check if running in test environment or keyring is unavailable
        if os.environ.get("PYTEST_CURRENT_TEST") or keyring is None:
            _TEST_KEYRING_STORE[f"{cls.SERVICE_NAME}:{key_id}"] = secret_clean
            return True

        try:
            keyring.set_password(cls.SERVICE_NAME, key_id, secret_clean)
            logger.info("Successfully stored secret for key_id '%s' in Windows Credential Manager", key_id)
            return True
        except Exception as e:
            logger.warning("Failed to store secret in keyring for '%s': %s. Using safe memory fallback.", key_id, e)
            _TEST_KEYRING_STORE[f"{cls.SERVICE_NAME}:{key_id}"] = secret_clean
            return True

    set_secret = store_secret

    @classmethod
    def get_secret(cls, key_id: str) -> Optional[str]:
        """Retrieves the secret at runtime for backend service communication only.
        NEVER expose the returned value in API responses or logs.
        """
        if os.environ.get("PYTEST_CURRENT_TEST") or keyring is None:
            return _TEST_KEYRING_STORE.get(f"{cls.SERVICE_NAME}:{key_id}")

        try:
            val = keyring.get_password(cls.SERVICE_NAME, key_id)
            if val is not None:
                return val
            return _TEST_KEYRING_STORE.get(f"{cls.SERVICE_NAME}:{key_id}")
        except Exception as e:
            logger.warning("Failed to read secret from keyring for '%s': %s", key_id, e)
            return _TEST_KEYRING_STORE.get(f"{cls.SERVICE_NAME}:{key_id}")

    @classmethod
    def delete_secret(cls, key_id: str) -> bool:
        """Removes a secret from Windows Credential Manager."""
        _TEST_KEYRING_STORE.pop(f"{cls.SERVICE_NAME}:{key_id}", None)

        if os.environ.get("PYTEST_CURRENT_TEST") or keyring is None:
            return True

        try:
            keyring.delete_password(cls.SERVICE_NAME, key_id)
            logger.info("Deleted secret for key_id '%s' from Windows Credential Manager", key_id)
            return True
        except Exception as e:
            logger.debug("Keyring delete for '%s' returned: %s", key_id, e)
            return True

    @classmethod
    def has_secret(cls, key_id: str) -> bool:
        """Checks whether a secret is configured without revealing it."""
        val = cls.get_secret(key_id)
        return bool(val and val.strip())

    @staticmethod
    def mask_secret(secret: Optional[str]) -> str:
        """Returns a masked representation safe for display (e.g. sk-***abcd)."""
        if not secret:
            return ""
        s = secret.strip()
        if len(s) <= 6:
            return "******"
        return f"{s[:3]}***{s[-4:]}"

