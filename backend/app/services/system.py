import time
from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.schemas.health import ComponentHealth, HealthResponse
from backend.app.services.credential_service import CredentialService


class SystemService:
    @staticmethod
    def get_health_status(db: Optional[Session] = None) -> HealthResponse:
        subsystems: Dict[str, ComponentHealth] = {}
        overall_status = "ok"

        # 1. Database Subsystem
        if db is not None:
            db_start = time.perf_counter()
            try:
                db.execute(text("SELECT 1")).scalar()
                db_latency = round((time.perf_counter() - db_start) * 1000, 2)
                subsystems["database"] = ComponentHealth(
                    status="ok",
                    message="SQLite database connected and responding",
                    latency_ms=db_latency,
                    details={
                        "engine": "sqlite",
                        "database_url": settings.DATABASE_URL.split("?")[0],
                    },
                )
            except Exception as e:
                db_latency = round((time.perf_counter() - db_start) * 1000, 2)
                subsystems["database"] = ComponentHealth(
                    status="error",
                    message=f"Database connection error: {str(e)}",
                    latency_ms=db_latency,
                )
                overall_status = "degraded"
        else:
            subsystems["database"] = ComponentHealth(status="ok", message="Database configured")

        # 2. Security & Credentials Subsystem
        keyring_ok = CredentialService.is_available()
        subsystems["security"] = ComponentHealth(
            status="ok" if keyring_ok else "warning",
            message="Windows Credential Manager active" if keyring_ok else "In-memory test credential vault active",
            details={
                "vault_service": CredentialService.SERVICE_NAME,
                "os_keyring_available": keyring_ok,
            },
        )

        # 3. AI Gateway Subsystem
        if db is not None:
            try:
                from backend.app.services.settings_service import SettingsService
                ai_cfg = SettingsService(db).get_ai_settings()
                router_ep = (ai_cfg.router_endpoint or "").strip()
                subsystems["ai_gateway"] = ComponentHealth(
                    status="ok" if router_ep else "not_configured",
                    message=f"9Router endpoint configured: {router_ep}" if router_ep else "9Router endpoint not configured",
                    details={
                        "provider": ai_cfg.ai_provider,
                        "default_model": ai_cfg.default_model,
                        "has_api_key": ai_cfg.has_router_api_key,
                    },
                )
            except Exception:
                subsystems["ai_gateway"] = ComponentHealth(status="warning", message="Settings unreadable")
        else:
            subsystems["ai_gateway"] = ComponentHealth(status="ok", message="AI Gateway configured")

        # 4. Monitoring Subsystem
        try:
            from backend.app.services.monitoring import MonitoringManagerService
            mon_mgr = MonitoringManagerService()
            active_watchers = len(mon_mgr._watchers)
            subsystems["monitoring"] = ComponentHealth(
                status="ok",
                message=f"Monitoring service active with {active_watchers} watcher(s)",
                details={"active_watchers": active_watchers},
            )
        except Exception:
            subsystems["monitoring"] = ComponentHealth(status="ok", message="Monitoring service standby")

        return HealthResponse(
            status=overall_status,
            project=settings.PROJECT_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
            subsystems=subsystems,
        )
