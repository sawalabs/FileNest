from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.monitoring import MonitoringEvent
    from backend.app.db.models.execution import ExecutionJob


class OrganizationRule(Base):
    __tablename__ = "organization_rules"
    __table_args__ = (
        CheckConstraint("rule_type IN ('organize', 'rename')", name="ck_organization_rules_rule_type"),
        CheckConstraint("is_enabled IN (0, 1)", name="ck_organization_rules_is_enabled"),
        CheckConstraint("version >= 1", name="ck_organization_rules_version"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    scope_json: Mapped[str] = mapped_column(String, nullable=False, default="{}")
    conditions_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    actions_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    is_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    approved_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="organization_rules")
    executions: Mapped[List["RuleExecution"]] = relationship(
        "RuleExecution", back_populates="organization_rule", cascade="all, delete-orphan"
    )


class RuleExecution(Base):
    __tablename__ = "rule_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('skipped', 'pending_review', 'executed', 'failed')",
            name="ck_rule_executions_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    organization_rule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization_rules.id", ondelete="CASCADE"), nullable=False
    )
    monitoring_event_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("monitoring_events.id", ondelete="SET NULL"), nullable=True
    )
    execution_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("execution_jobs.id", ondelete="SET NULL"), nullable=True
    )
    rule_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="executed")
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    # Relationships
    organization_rule: Mapped["OrganizationRule"] = relationship("OrganizationRule", back_populates="executions")
    monitoring_event: Mapped[Optional["MonitoringEvent"]] = relationship(
        "MonitoringEvent", back_populates="rule_executions"
    )
    execution_job: Mapped[Optional["ExecutionJob"]] = relationship("ExecutionJob")
