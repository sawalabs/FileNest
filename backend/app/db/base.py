import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String


def generate_uuid() -> str:
    """Generates a UUID4 string."""
    return str(uuid.uuid4())


def utc_now_iso() -> str:
    """Returns current UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).isoformat()


class Base(DeclarativeBase):
    """Base declarative class for all SQLAlchemy ORM models."""
    pass
