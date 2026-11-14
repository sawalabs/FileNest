from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy.orm import Session

from backend.app.api.v1.router import api_v1_router
from backend.app.core.config import settings
from backend.app.core.logging import logger, setup_logging
from backend.app.core.security import AppTokenAuthMiddleware


def run_startup_monitoring_check(db: Session, monitoring_service: Any) -> bool:
    """Checks General and Monitoring settings before auto-starting enabled watchers on launch."""
    from backend.app.services.settings_service import SettingsService

    settings_service = SettingsService(db)
    general = settings_service.get_general_settings()
    monitoring = settings_service.get_monitoring_settings()

    should_start = bool(
        general.start_monitoring_on_launch
        and monitoring.enable_monitoring
        and monitoring.start_monitoring_on_launch
    )
    if should_start:
        monitoring_service.start_all_enabled(db=db)
        return True

    logger.info(
        "Skipping automatic monitoring watcher startup per user settings "
        "(general.start_monitoring_on_launch=%s, monitoring.enable_monitoring=%s, monitoring.start_monitoring_on_launch=%s)",
        general.start_monitoring_on_launch,
        monitoring.enable_monitoring,
        monitoring.start_monitoring_on_launch,
    )
    return False


def ensure_sqlite_schema_migrations(target_engine: Any) -> List[str]:
    """Automatically adds new model columns to existing SQLite tables during in-place app updates."""
    from sqlalchemy import inspect as sa_inspect, text
    from backend.app.db.base import Base

    added_columns: List[str] = []
    inspector = sa_inspect(target_engine)
    existing_tables = set(inspector.get_table_names())

    with target_engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(dialect=target_engine.dialect)
                stmt = f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'
                if col.default is not None and isinstance(col.default.arg, (str, int, float, bool)):
                    default_val = col.default.arg
                    if isinstance(default_val, str):
                        stmt += f" DEFAULT '{default_val}'"
                    elif isinstance(default_val, bool):
                        stmt += f" DEFAULT {1 if default_val else 0}"
                    else:
                        stmt += f" DEFAULT {default_val}"
                conn.execute(text(stmt))
                added_columns.append(f"{table.name}.{col.name}")
                logger.info("Applied additive SQLite schema upgrade: %s.%s", table.name, col.name)

    return added_columns


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    setup_logging()
    logger.info("Starting %s v%s in %s environment", settings.PROJECT_NAME, settings.VERSION, settings.ENVIRONMENT)

    # Ensure SQLite tables and schema exist and upgrade additive columns automatically on startup
    try:
        from backend.app.db.base import Base
        from backend.app.db.session import engine
        import backend.app.db.models  # register all models in SQLAlchemy registry
        Base.metadata.create_all(bind=engine)
        ensure_sqlite_schema_migrations(engine)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.warning("Could not auto-verify database schema: %s", e)

    try:
        from backend.app.db.session import SessionLocal
        from backend.app.services.monitoring import get_monitoring_service

        monitoring_service = get_monitoring_service()
        db = SessionLocal()
        try:
            run_startup_monitoring_check(db, monitoring_service)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Could not auto-start monitoring watchers on startup: {e}")
    yield
    try:
        from backend.app.services.monitoring import get_monitoring_service
        get_monitoring_service().stop_all()
    except Exception as e:
        logger.warning(f"Error stopping monitoring watchers on shutdown: {e}")
    logger.info("Shutting down %s", settings.PROJECT_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        lifespan=lifespan,
    )

    # Authentication middleware for local API session protection
    app.add_middleware(AppTokenAuthMiddleware)

    # CORS middleware for local Tauri desktop client
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trusted Host middleware to prevent DNS Rebinding attacks
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["127.0.0.1", "localhost", "test", "testserver", "*.localhost"],
    )

    app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    @app.get("/", include_in_schema=False)
    async def root_redirect():
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "status": "running",
            "docs": f"{settings.API_V1_PREFIX}/docs",
        }

    return app


app = create_app()
