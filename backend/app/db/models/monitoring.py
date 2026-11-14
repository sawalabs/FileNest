from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.organization import RuleExecution


class MonitoringConfig(Base):
    __tablename__ = "monitoring_configs"
    __table_args__ = (
        CheckConstraint("is_enabled IN (0, 1)", name="ck_monitoring_configs_is_enabled"),
        CheckConstraint("recursive IN (0, 1)", name="ck_monitoring_configs_recursive"),
        CheckConstraint("debounce_ms > 0", name="ck_monitoring_configs_debounce_ms"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    is_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recursive: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    debounce_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    ignore_patterns_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="monitoring_config")


class MonitoringEvent(Base):
    __tablename__ = "monitoring_events"
    __table_args__ = (
        CheckConstraint(
            "event_type IN ('created', 'modified', 'deleted', 'moved')",
            name="ck_monitoring_events_event_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'processed', 'ignored', 'failed')",
            name="ck_monitoring_events_status",
        ),
        Index("idx_monitoring_events_status", "status", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    destination_relative_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    event_key: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    occurred_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    processed_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="monitoring_events")
    rule_executions: Mapped[List["RuleExecution"]] = relationship(
        "RuleExecution", back_populates="monitoring_event"
    )
