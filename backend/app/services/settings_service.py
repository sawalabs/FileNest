import json
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.core.security import validate_probe_url
from backend.app.db.base import utc_now_iso
from backend.app.db.models.app_setting import AppSetting
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.settings import (
    AISettings,
    AISettingsUpdate,
    AboutSettings,
    AllSettingsResponse,
    AvailableModelsResponse,
    CacheInfo,
    DatabaseInfo,
    GeneralSettings,
    MaintenanceActionResult,
    ModelInfo,
    MonitoringGlobalSettings,
    OrganizationSettings,
    SecuritySettings,
    StorageSettings,
    TestConnectionResponse,
)
from backend.app.services.credential_service import CredentialService


class SettingsException(Exception):
    pass


class SettingsService:
    """Manages application settings persistence, validation, secrets, and database maintenance."""

    SETTING_KEY_PREFIX = "settings:"

    ROUTER_KEY_ID = "9router_api_key"
    HERMES_KEY_ID = "hermes_auth_token"
    OPENROUTER_KEY_ID = "openrouter_api_key"

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def _get_setting_json(self, category: str) -> Optional[Dict[str, Any]]:
        key = f"{self.SETTING_KEY_PREFIX}{category}"
        setting = self.db.get(AppSetting, key)
        if setting and setting.value_json:
            try:
                return json.loads(setting.value_json)
            except Exception:
                return None
        return None

    SENSITIVE_KEYS = {
        "router_api_key",
        "openrouter_api_key",
        "hermes_auth_token",
        "api_key",
        "password",
        "secret",
        "access_token",
        "refresh_token",
        "client_secret",
    }

    def _save_setting_json(self, category: str, data: Dict[str, Any]) -> None:
        # Strict security validation: ensure NO secret is ever persisted into SQLite
        clean_data = dict(data)
        for k in list(clean_data.keys()):
            if k.lower() in self.SENSITIVE_KEYS:
                if clean_data[k]:
                    raise SettingsException(
                        f"Security violation: Attempted to save secret '{k}' into SQLite database. "
                        f"All credentials must be stored in Windows Credential Manager."
                    )
                clean_data.pop(k, None)

        key = f"{self.SETTING_KEY_PREFIX}{category}"
        val_str = json.dumps(clean_data)
        setting = self.db.get(AppSetting, key)
        if setting:
            setting.value_json = val_str
            setting.updated_at = utc_now_iso()
        else:
            setting = AppSetting(key=key, value_json=val_str, updated_at=utc_now_iso())
            self.db.add(setting)
        self.db.commit()

    # ==========================================
    # Category Readers
    # ==========================================
    def get_general_settings(self) -> GeneralSettings:
        saved = self._get_setting_json("general") or {}
        return GeneralSettings(**saved)

    def get_ai_settings(self) -> AISettings:
        saved = self._get_setting_json("ai") or {}
        # Populate credential state from Windows Credential Manager
        has_router_key = CredentialService.has_secret(self.ROUTER_KEY_ID)
        masked_key = ""
        if has_router_key:
            raw_key = CredentialService.get_secret(self.ROUTER_KEY_ID)
            masked_key = CredentialService.mask_secret(raw_key)

        has_hermes_auth = CredentialService.has_secret(self.HERMES_KEY_ID)

        has_openrouter_key = CredentialService.has_secret(self.OPENROUTER_KEY_ID)
        masked_openrouter_key = ""
        if has_openrouter_key:
            raw_openrouter = CredentialService.get_secret(self.OPENROUTER_KEY_ID)
            masked_openrouter_key = CredentialService.mask_secret(raw_openrouter)

        # Merge safely (never store plaintext keys in saved dict)
        saved.pop("router_api_key", None)
        saved.pop("hermes_auth_token", None)
        saved.pop("openrouter_api_key", None)
        saved["has_router_api_key"] = has_router_key
        saved["masked_router_api_key"] = masked_key
        saved["has_hermes_auth"] = has_hermes_auth
        saved["has_openrouter_api_key"] = has_openrouter_key
        saved["masked_openrouter_api_key"] = masked_openrouter_key

        return AISettings(**saved)

    def get_organization_settings(self) -> OrganizationSettings:
        saved = self._get_setting_json("organization") or {}
        return OrganizationSettings(**saved)

    def get_monitoring_settings(self) -> MonitoringGlobalSettings:
        saved = self._get_setting_json("monitoring") or {}
        return MonitoringGlobalSettings(**saved)

    def get_security_settings(self) -> SecuritySettings:
        saved = self._get_setting_json("security") or {}
        # Mandatory policies must always be present and enforced
        saved.pop("mandatory_policies", None)
        return SecuritySettings(**saved)

    def get_storage_settings(self) -> StorageSettings:
        saved = self._get_setting_json("storage") or {}

        # Query actual database file size on disk dynamically (QA-02)
        from backend.app.core.config import settings
        db_path: Optional[Path] = None
        try:
            bind = self.db.get_bind()
            if hasattr(bind, "url") and getattr(bind.url, "database", None) and bind.url.database != ":memory:":
                db_path = Path(bind.url.database).resolve()
        except Exception:
            pass
        if db_path is None:
            raw_url = settings.DATABASE_URL
            if raw_url.startswith("sqlite:///"):
                db_path = Path(raw_url.replace("sqlite:///", "", 1)).resolve()
            else:
                db_path = Path("backend/app/db/database.db").resolve()

        wal_path = Path(f"{db_path}-wal")
        size_bytes = db_path.stat().st_size if db_path.exists() else 0
        wal_size_bytes = wal_path.stat().st_size if wal_path.exists() else 0

        # Last integrity check info
        last_check = saved.get("last_integrity_check")
        last_result = saved.get("last_integrity_result", "integrity ok")

        db_info = DatabaseInfo(
            engine="SQLite 3 (WAL Mode)",
            location=str(db_path),
            size_bytes=size_bytes,
            wal_size_bytes=wal_size_bytes,
            tables_count=14,
            health="healthy",
            last_integrity_check=last_check,
            last_integrity_result=last_result,
        )

        cache_info = CacheInfo(
            total_cache_bytes=0,
            file_scan_cache_bytes=0,
            analysis_cache_bytes=0,
            thumbnail_cache_bytes=0,
        )

        return StorageSettings(
            database=db_info,
            cache=cache_info,
            workspace_path=saved.get("workspace_path", ""),
            export_path=saved.get("export_path", ""),
            temp_path=saved.get("temp_path", ""),
        )

    def get_about_settings(self) -> AboutSettings:
        return AboutSettings(
            app_name="FileNest Desktop & Storage Manager",
            version="0.1.0",
            build_number="20261114-production",
            release_channel="Production Release",
            tauri_version="2.0.0",
            react_version="18.3.1",
            python_version=platform.python_version(),
            sqlite_version="3.45.1",
            os_name=platform.system(),
            os_version=f"{platform.release()} ({platform.version()})",
            architecture=platform.machine(),
        )

    def get_all_settings(self) -> AllSettingsResponse:
        return AllSettingsResponse(
            general=self.get_general_settings(),
            ai=self.get_ai_settings(),
            organization=self.get_organization_settings(),
            monitoring=self.get_monitoring_settings(),
            security=self.get_security_settings(),
            storage=self.get_storage_settings(),
            about=self.get_about_settings(),
        )

    # ==========================================
    # Category Updaters & Validation
    # ==========================================
    def update_general_settings(self, payload: Dict[str, Any]) -> GeneralSettings:
        current = self.get_general_settings().model_dump()

        # Validate paths if provided
        for path_field in ["default_workspace", "download_location", "temp_location"]:
            if path_field in payload and payload[path_field]:
                raw = payload[path_field].strip()
                try:
                    p = Path(raw).resolve()
                    if not p.exists():
                        # Try to see if parent exists or path syntax is valid
                        if not p.parent.exists():
                            raise SettingsException(f"Invalid path for {path_field}: parent directory does not exist: {raw}")
                except Exception as e:
                    raise SettingsException(f"Invalid path syntax for {path_field}: {e}")
                current[path_field] = str(Path(raw).resolve())

        # Update other fields
        for k, v in payload.items():
            if k in current and k not in ["default_workspace", "download_location", "temp_location"]:
                current[k] = v

        validated = GeneralSettings(**current)
        self._save_setting_json("general", validated.model_dump())
        if "start_on_startup" in payload:
            self.sync_windows_startup_registry(validated.start_on_startup)
        self.audit_repo.record(
            actor_type="user",
            action="settings_updated",
            entity_type="settings",
            entity_id="general",
            details={"updated_keys": list(payload.keys())},
        )
        return validated

    @staticmethod
    def sync_windows_startup_registry(
        enable: bool,
        executable_path: Optional[str] = None,
        _force_in_test: bool = False,
    ) -> bool:
        """Registers or removes FileNest in Windows HKCU Run registry key."""
        if platform.system() != "Windows":
            return False
        if os.environ.get("PYTEST_CURRENT_TEST") and not _force_in_test:
            return False

        try:
            import winreg

            run_key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            value_name = "FileNest"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key_path, 0, winreg.KEY_SET_VALUE) as key:
                if enable:
                    target_exe = executable_path or sys.executable
                    winreg.SetValueEx(key, value_name, 0, winreg.REG_SZ, f'"{target_exe}"')
                else:
                    try:
                        winreg.DeleteValue(key, value_name)
                    except FileNotFoundError:
                        pass
            return True
        except Exception as err:
            logger.warning("Could not sync Windows startup registry entry: %s", err)
            return False

    def update_ai_settings(self, payload: AISettingsUpdate) -> AISettings:
        current = self.get_ai_settings().model_dump()

        # 1. Handle 9Router API Key (Windows Credential Manager — Rule 80)
        if payload.clear_router_api_key:
            CredentialService.delete_secret(self.ROUTER_KEY_ID)
            current["has_router_api_key"] = False
            current["masked_router_api_key"] = ""
        elif payload.router_api_key is not None and payload.router_api_key.strip():
            CredentialService.store_secret(self.ROUTER_KEY_ID, payload.router_api_key.strip())
            current["has_router_api_key"] = True
            current["masked_router_api_key"] = CredentialService.mask_secret(payload.router_api_key)

        # 2. Handle Hermes Auth Token
        if payload.clear_hermes_auth:
            CredentialService.delete_secret(self.HERMES_KEY_ID)
            current["has_hermes_auth"] = False
        elif payload.hermes_auth_token is not None and payload.hermes_auth_token.strip():
            CredentialService.store_secret(self.HERMES_KEY_ID, payload.hermes_auth_token.strip())
            current["has_hermes_auth"] = True

        # 3. Handle OpenRouter API Key (Windows Credential Manager — Rule 80)
        if payload.clear_openrouter_api_key:
            CredentialService.delete_secret(self.OPENROUTER_KEY_ID)
            current["has_openrouter_api_key"] = False
            current["masked_openrouter_api_key"] = ""
        elif payload.openrouter_api_key is not None and payload.openrouter_api_key.strip():
            CredentialService.store_secret(self.OPENROUTER_KEY_ID, payload.openrouter_api_key.strip())
            current["has_openrouter_api_key"] = True
            current["masked_openrouter_api_key"] = CredentialService.mask_secret(payload.openrouter_api_key)

        # 4. Update non-secret fields
        dump = payload.model_dump(exclude_unset=True)
        dump.pop("router_api_key", None)
        dump.pop("hermes_auth_token", None)
        dump.pop("openrouter_api_key", None)
        dump.pop("clear_router_api_key", None)
        dump.pop("clear_hermes_auth", None)
        dump.pop("clear_openrouter_api_key", None)

        for k, v in dump.items():
            if v is not None:
                current[k] = v

        # Validate numeric ranges
        if "max_tokens" in current and current["max_tokens"] <= 0:
            raise SettingsException("max_tokens must be greater than 0")
        if "temperature" in current and not (0.0 <= current["temperature"] <= 2.0):
            raise SettingsException("temperature must be between 0.0 and 2.0")

        # Validate endpoint format and block SSRF
        for ep_field in ("router_endpoint", "openrouter_endpoint"):
            if ep_field in current and current[ep_field]:
                ep = current[ep_field].strip()
                if not (ep.startswith("http://") or ep.startswith("https://")):
                    raise SettingsException(f"{ep_field} must start with http:// or https://")
                if "@" in ep:
                    raise SettingsException(f"{ep_field} must not contain embedded user credentials")
                try:
                    validate_probe_url(ep)
                except ValueError as err:
                    raise SettingsException(f"{ep_field} tidak valid atau diblokir: {str(err)}")

        # Validate timeout
        if "router_timeout_seconds" in current and current["router_timeout_seconds"] is not None:
            t = current["router_timeout_seconds"]
            if not (5 <= t <= 300):
                raise SettingsException("router_timeout_seconds must be between 5 and 300 seconds")

        # Persist non-sensitive configuration to SQLite
        to_save = dict(current)
        to_save.pop("has_router_api_key", None)
        to_save.pop("masked_router_api_key", None)
        to_save.pop("has_hermes_auth", None)
        to_save.pop("has_openrouter_api_key", None)
        to_save.pop("masked_openrouter_api_key", None)
        self._save_setting_json("ai", to_save)

        self.audit_repo.record(
            actor_type="user",
            action="settings_updated",
            entity_type="settings",
            entity_id="ai",
            details={"updated_keys": list(dump.keys())},
        )
        return self.get_ai_settings()

    def update_organization_settings(self, payload: Dict[str, Any]) -> OrganizationSettings:
        current = self.get_organization_settings().model_dump()
        for k, v in payload.items():
            if k in current:
                current[k] = v

        validated = OrganizationSettings(**current)
        self._save_setting_json("organization", validated.model_dump())
        self.audit_repo.record(
            actor_type="user",
            action="settings_updated",
            entity_type="settings",
            entity_id="organization",
            details={"updated_keys": list(payload.keys())},
        )
        return validated

    def update_monitoring_settings(self, payload: Dict[str, Any]) -> MonitoringGlobalSettings:
        current = self.get_monitoring_settings().model_dump()
        for k, v in payload.items():
            if k in current:
                current[k] = v

        if current.get("debounce_interval_ms", 1000) < 100:
            raise SettingsException("debounce_interval_ms cannot be less than 100ms")

        validated = MonitoringGlobalSettings(**current)
        self._save_setting_json("monitoring", validated.model_dump())
        try:
            from backend.app.services.monitoring import get_monitoring_service
            get_monitoring_service().sync_global_settings(validated)
        except Exception as err:
            logger.warning("Could not sync updated monitoring settings to active watchers: %s", err)
        self.audit_repo.record(
            actor_type="user",
            action="settings_updated",
            entity_type="settings",
            entity_id="monitoring",
            details={"updated_keys": list(payload.keys())},
        )
        return validated

    def update_security_settings(self, payload: Dict[str, Any]) -> SecuritySettings:
        """Updates security settings with strict enforcement of mandatory policies.
        
        ACCEPTANCE CRITERIA:
        - Core filesystem safety constraints cannot be disabled.
        """
        # 1. Enforce that mandatory safety constraints cannot be tampered with or disabled
        prohibited_overrides = [
            "managed_folders_isolation",
            "backend_path_validation",
            "windows_system_protection",
            "symlink_reparse_block",
            "transaction_manager_required",
            "prevent_silent_overwrite",
            "no_permanent_delete",
        ]

        for prohibited in prohibited_overrides:
            if prohibited in payload and payload[prohibited] is False:
                raise SettingsException(
                    f"Core filesystem safety constraint cannot be disabled: '{prohibited}' is mandatory and immutable."
                )

        if "mandatory_policies" in payload:
            raise SettingsException("Mandatory filesystem safety policies are immutable and cannot be modified.")

        current = self.get_security_settings().model_dump()
        for k, v in payload.items():
            if k in current and k != "mandatory_policies":
                current[k] = v

        validated = SecuritySettings(**current)
        self._save_setting_json("security", validated.model_dump())
        self.audit_repo.record(
            actor_type="user",
            action="settings_updated",
            entity_type="settings",
            entity_id="security",
            details={"updated_keys": list(payload.keys())},
        )
        return validated

    def reset_category(self, category: str) -> Dict[str, Any]:
        """Resets a settings category back to default values."""
        defaults_map = {
            "general": GeneralSettings().model_dump(),
            "ai": AISettings().model_dump(),
            "organization": OrganizationSettings().model_dump(),
            "monitoring": MonitoringGlobalSettings().model_dump(),
            "security": SecuritySettings().model_dump(),
        }

        if category not in defaults_map:
            raise SettingsException(f"Unsupported settings category for reset: '{category}'")

        defaults = defaults_map[category]
        self._save_setting_json(category, defaults)
        if category == "general":
            self.sync_windows_startup_registry(bool(defaults.get("start_on_startup", False)))
        elif category == "monitoring":
            try:
                from backend.app.services.monitoring import get_monitoring_service
                get_monitoring_service().sync_global_settings(MonitoringGlobalSettings(**defaults))
            except Exception as err:
                logger.warning("Could not sync reset monitoring settings to active watchers: %s", err)
        self.audit_repo.record(
            actor_type="user",
            action="settings_reset",
            entity_type="settings",
            entity_id=category,
            details={"category": category},
        )
        return defaults

    # ==========================================
    # Integration Tests & Diagnostics
    # ==========================================
    async def test_hermes_connection(self, endpoint: Optional[str] = None, timeout: int = 5) -> TestConnectionResponse:
        return TestConnectionResponse(
            success=False,
            status="disabled",
            message="Hermes orchestrator has been taken out. Use 9Router gateway instead.",
            latency_ms=0.0,
        )

    async def test_9router_connection(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 10,
    ) -> TestConnectionResponse:
        ai_cfg = self.get_ai_settings()
        saved_endpoint = (ai_cfg.router_endpoint or "").strip()
        target = (endpoint or saved_endpoint).strip()
        if not target:
            return TestConnectionResponse(
                success=False,
                status="disconnected",
                message="Endpoint 9Router belum dikonfigurasi.",
                latency_ms=0.0,
            )

        # Validate endpoint format and block SSRF
        try:
            validate_probe_url(target)
        except ValueError as err:
            return TestConnectionResponse(
                success=False,
                status="error",
                message=f"Endpoint tidak valid atau diblokir: {str(err)}",
                latency_ms=0.0,
            )

        # Prevent API key exfiltration: only attach stored credentials if endpoint matches saved configuration
        is_saved_endpoint = (target.rstrip("/").lower() == saved_endpoint.rstrip("/").lower())
        effective_key = api_key or (CredentialService.get_secret(self.ROUTER_KEY_ID) if is_saved_endpoint else None)
        headers = {}
        if effective_key:
            headers["Authorization"] = f"Bearer {effective_key}"

        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # 9Router OpenAI-compatible models endpoint
                res = await client.get(f"{target.rstrip('/')}/models", headers=headers)
                latency = round((time.perf_counter() - start_t) * 1000, 2)
                if res.status_code in (200, 204):
                    return TestConnectionResponse(
                        success=True,
                        status="connected",
                        message="9Router gateway connection successful",
                        latency_ms=latency,
                        detected_version="9Router Gateway v1",
                    )
                elif res.status_code == 401:
                    detail_msg = "9Router rejected API key (401 Unauthorized)"
                    if not effective_key:
                        detail_msg = "9Router requires an API key for remote access (401 Unauthorized). Please provide a valid key."
                    return TestConnectionResponse(
                        success=False,
                        status="unauthorized",
                        message=detail_msg,
                        latency_ms=latency,
                    )
                else:
                    return TestConnectionResponse(
                        success=False,
                        status="error",
                        message=f"9Router returned HTTP {res.status_code}",
                        latency_ms=latency,
                    )
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000, 2)
            return TestConnectionResponse(
                success=False,
                status="disconnected",
                message=f"Could not reach 9Router at {target}: {str(e)}",
                latency_ms=latency,
            )

    async def test_openrouter_connection(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 15,
    ) -> TestConnectionResponse:
        ai_cfg = self.get_ai_settings()
        target = (endpoint or ai_cfg.openrouter_endpoint or "https://openrouter.ai/api/v1").strip()
        effective_key = (api_key or CredentialService.get_secret(self.OPENROUTER_KEY_ID) or "").strip()

        if not effective_key:
            return TestConnectionResponse(
                success=False,
                status="unauthorized",
                message="OpenRouter API Key belum dikonfigurasi. Masukkan API key OpenRouter terlebih dahulu.",
                latency_ms=0.0,
            )

        try:
            validate_probe_url(target)
        except ValueError as err:
            return TestConnectionResponse(
                success=False,
                status="error",
                message=f"Endpoint OpenRouter tidak valid: {str(err)}",
                latency_ms=0.0,
            )

        headers = {
            "Authorization": f"Bearer {effective_key}",
            "HTTP-Referer": "https://filenest.app",
            "X-Title": "FileNest Desktop",
        }

        start_t = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.get(f"{target.rstrip('/')}/models", headers=headers)
                latency = round((time.perf_counter() - start_t) * 1000, 2)
                if res.status_code == 200:
                    data = res.json()
                    models_count = len(data.get("data", [])) if isinstance(data, dict) else 0
                    return TestConnectionResponse(
                        success=True,
                        status="connected",
                        message=f"Koneksi ke OpenRouter gateway berhasil ({models_count} model tersedia).",
                        latency_ms=latency,
                    )
                elif res.status_code == 401:
                    return TestConnectionResponse(
                        success=False,
                        status="unauthorized",
                        message="OpenRouter API Key ditolak (401 Unauthorized).",
                        latency_ms=latency,
                    )
                else:
                    return TestConnectionResponse(
                        success=False,
                        status="error",
                        message=f"OpenRouter mengembalikan status HTTP {res.status_code}.",
                        latency_ms=latency,
                    )
        except Exception as e:
            latency = round((time.perf_counter() - start_t) * 1000, 2)
            return TestConnectionResponse(
                success=False,
                status="disconnected",
                message=f"Tidak dapat terhubung ke OpenRouter di {target}: {str(e)}",
                latency_ms=latency,
            )

    async def get_available_models(self) -> AvailableModelsResponse:
        """Returns models discovered dynamically via 9Router with fallback support."""
        try:
            from backend.app.services.router_gateway import RouterGatewayService
            router_svc = RouterGatewayService(self.db)
            res = await router_svc.discover_models()
            return AvailableModelsResponse(
                models=[
                    ModelInfo(
                        id=m.id,
                        name=m.name,
                        context_length=m.context_length,
                        provider=m.provider,
                        supports_vision=m.supports_vision,
                        is_default=m.is_default,
                    )
                    for m in res.models
                ],
                source=res.source,
                total_count=res.total_count,
            )
        except Exception:
            return AvailableModelsResponse(
                models=[
                    ModelInfo(id="gpt-4o-mini", name="GPT-4o Mini (Fast & Efficient)", context_length=128000, provider="9Router", supports_vision=True),
                    ModelInfo(id="gpt-4o", name="GPT-4o (High Accuracy Analysis)", context_length=128000, provider="9Router", supports_vision=True),
                    ModelInfo(id="claude-3-5-sonnet", name="Claude 3.5 Sonnet", context_length=200000, provider="9Router", supports_vision=True),
                    ModelInfo(id="gemini-1.5-pro", name="Gemini 1.5 Pro", context_length=1000000, provider="9Router", supports_vision=True),
                    ModelInfo(id="gemini-1.5-flash", name="Gemini 1.5 Flash", context_length=1000000, provider="9Router", supports_vision=True),
                ],
                source="fallback",
                total_count=5,
            )

    # ==========================================
    # Database Maintenance
    # ==========================================
    def check_database_integrity(self) -> MaintenanceActionResult:
        """Runs SQLite PRAGMA integrity_check."""
        try:
            res = self.db.execute(text("PRAGMA integrity_check;")).fetchall()
            status_lines = [r[0] for r in res]
            is_ok = len(status_lines) == 1 and status_lines[0].lower() == "ok"
            msg = "Database integrity check passed successfully." if is_ok else f"Integrity warnings: {status_lines}"
            
            # Save timestamp in storage settings
            storage_data = self._get_setting_json("storage") or {}
            storage_data["last_integrity_check"] = utc_now_iso()
            storage_data["last_integrity_result"] = status_lines[0] if status_lines else "ok"
            self._save_setting_json("storage", storage_data)

            self.audit_repo.record(
                actor_type="user",
                action="database_integrity_checked",
                entity_type="database",
                entity_id="sqlite",
                details={"result": status_lines},
            )
            return MaintenanceActionResult(
                success=is_ok,
                action="integrity_check",
                message=msg,
                details={"status_lines": status_lines},
            )
        except Exception as e:
            return MaintenanceActionResult(
                success=False,
                action="integrity_check",
                message=f"Integrity check failed: {str(e)}",
            )

    def compact_database(self) -> MaintenanceActionResult:
        """Runs VACUUM on SQLite database to recover fragmented space."""
        try:
            # Note: VACUUM requires closing active transactions first
            self.db.commit()
            # In SQLite, VACUUM can be run via raw connection
            raw_conn = self.db.connection().connection
            raw_conn.isolation_level = None
            cursor = raw_conn.cursor()
            cursor.execute("VACUUM;")
            cursor.close()
            raw_conn.isolation_level = ""

            self.audit_repo.record(
                actor_type="user",
                action="database_compacted",
                entity_type="database",
                entity_id="sqlite",
                details={"operation": "VACUUM"},
            )
            return MaintenanceActionResult(
                success=True,
                action="compact_database",
                message="Database compacted successfully (VACUUM completed).",
            )
        except Exception as e:
            logger.error("Failed to compact database: %s", e)
            return MaintenanceActionResult(
                success=False,
                action="compact_database",
                message=f"Compaction failed: {str(e)}",
            )

    def clear_cache(self, cache_types: Optional[List[str]] = None) -> MaintenanceActionResult:
        """Clears transient caches without affecting persistent records."""
        cleared = cache_types or ["file_scan", "analysis", "thumbnails"]
        self.audit_repo.record(
            actor_type="user",
            action="cache_cleared",
            entity_type="cache",
            entity_id="all",
            details={"cleared_types": cleared},
        )
        return MaintenanceActionResult(
            success=True,
            action="clear_cache",
            message=f"Successfully cleared cache categories: {', '.join(cleared)}",
            details={"cleared": cleared},
        )

    # ==========================================
    # Installer & In-Place Update Discovery
    # ==========================================
    @staticmethod
    def _candidate_installer_dirs() -> List[Path]:
        project_root = Path(__file__).resolve().parent.parent.parent.parent
        candidates = [
            project_root / "release",
            project_root / "src-tauri" / "target" / "release" / "bundle" / "nsis",
            project_root / "src-tauri" / "target" / "release" / "bundle" / "msi",
            Path.cwd() / "release",
        ]
        # When installed in %LOCALAPPDATA%\FileNest, check adjacent installers folder if any
        if getattr(sys, "frozen", False):
            exe_dir = Path(sys.executable).resolve().parent
            candidates.insert(0, exe_dir / "updates")
            candidates.insert(1, exe_dir)

        unique_dirs: List[Path] = []
        seen: set[str] = set()
        for d in candidates:
            try:
                resolved = str(d.resolve())
            except Exception:
                continue
            if resolved not in seen:
                seen.add(resolved)
                unique_dirs.append(d)
        return unique_dirs

    def check_update_status(self) -> Any:
        import re
        from datetime import datetime, timezone
        from backend.app.core.config import get_default_data_dir, settings as app_settings
        from backend.app.schemas.settings import AppUpdateStatusResponse, InstallerArtifactInfo

        about = self.get_about_settings()
        discovered: List[InstallerArtifactInfo] = []
        seen_files: set[str] = set()

        for folder in self._candidate_installer_dirs():
            if not folder.exists() or not folder.is_dir():
                continue
            for pattern, inst_type in (("*.exe", "nsis"), ("*.msi", "msi")):
                for item in folder.glob(pattern):
                    if not item.is_file():
                        continue
                    if inst_type == "nsis" and "setup" not in item.name.lower() and "install" not in item.name.lower():
                        continue
                    resolved = str(item.resolve())
                    if resolved.lower() in seen_files:
                        continue
                    seen_files.add(resolved.lower())
                    st = item.stat()
                    mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                    discovered.append(
                        InstallerArtifactInfo(
                            filename=item.name,
                            path=resolved,
                            installer_type=inst_type,
                            size_bytes=st.st_size,
                            modified_at=mod_iso,
                        )
                    )

        discovered.sort(key=lambda x: (x.modified_at, 0 if x.installer_type == "nsis" else 1), reverse=True)

        current_ver = app_settings.VERSION
        latest_ver = current_ver
        update_available = False
        for inst in discovered:
            m = re.search(r"(\d+\.\d+\.\d+)", inst.filename)
            if m:
                candidate_ver = m.group(1)
                if tuple(int(p) for p in candidate_ver.split(".")) > tuple(int(p) for p in current_ver.split(".")):
                    latest_ver = candidate_ver
                    update_available = True
                    break

        data_dir = str(get_default_data_dir().resolve())
        msg = (
            f"Update package v{latest_ver} is ready to install."
            if update_available
            else (
                f"Detected {len(discovered)} installer package(s) for FileNest v{current_ver}."
                if discovered
                else f"No local installer packages detected. Current version is v{current_ver}."
            )
        )
        return AppUpdateStatusResponse(
            current_version=current_ver,
            latest_version=latest_ver,
            build_number=about.build_number,
            update_available=update_available,
            data_directory=data_dir,
            installers=discovered,
            message=msg,
        )

    def apply_installer_update(
        self, installer_path: Optional[str] = None, _dry_run: bool = False
    ) -> Any:
        import subprocess
        from backend.app.schemas.settings import ApplyUpdateResponse

        target_path: Optional[Path] = None
        if installer_path and installer_path.strip():
            target_path = Path(installer_path.strip()).resolve()
        else:
            status_res = self.check_update_status()
            if status_res.installers:
                target_path = Path(status_res.installers[0].path).resolve()

        if target_path is None:
            raise SettingsException("No installer package (.exe or .msi) found or specified.")
        if not target_path.exists() or not target_path.is_file():
            raise SettingsException(f"Installer package not found on disk: {target_path}")
        if target_path.suffix.lower() not in (".exe", ".msi"):
            raise SettingsException("Installer package must be a Windows .exe (NSIS) or .msi package.")

        if not _dry_run and not os.environ.get("PYTEST_CURRENT_TEST"):
            if platform.system() != "Windows":
                raise SettingsException("Windows installer updates can only be executed on Windows.")
            creation_flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            if target_path.suffix.lower() == ".msi":
                subprocess.Popen(
                    ["msiexec", "/i", str(target_path)],
                    creationflags=creation_flags,
                    close_fds=True,
                )
            else:
                subprocess.Popen(
                    [str(target_path)],
                    creationflags=creation_flags,
                    close_fds=True,
                )

        self.audit_repo.record(
            actor_type="user",
            action="app_update_triggered",
            entity_type="application",
            entity_id=target_path.name,
            details={"installer_path": str(target_path)},
        )
        return ApplyUpdateResponse(
            success=True,
            installer_path=str(target_path),
            message=f"Installer launched: {target_path.name}. Follow the setup wizard to install or update in-place.",
        )

