import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings


def _ensure_db_dir_exists(db_url: str) -> None:
    """Ensures parent directory for SQLite database file exists."""
    if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:///:memory:"):
        db_path = db_url.replace("sqlite:///", "")
        parent_dir = Path(db_path).parent
        if parent_dir and not parent_dir.exists():
            parent_dir.mkdir(parents=True, exist_ok=True)


_ensure_db_dir_exists(settings.DATABASE_URL)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Enforces SQLite foreign keys, WAL mode, and busy timeout on every connection."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute("PRAGMA journal_mode = WAL;")
    cursor.execute("PRAGMA busy_timeout = 5000;")
    cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
