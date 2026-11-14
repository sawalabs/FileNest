from typing import Optional
from sqlalchemy import CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base, generate_uuid, utc_now_iso


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user', 'system', 'ai')",
            name="ck_audit_logs_actor_type",
        ),
        Index("idx_audit_logs_entity", "entity_type", "entity_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
