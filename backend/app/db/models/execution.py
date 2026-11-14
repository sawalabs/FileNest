from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.change_plan import ChangePlan, ChangePlanItem


class ExecutionJob(Base):
    __tablename__ = "execution_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'partial', 'rolled_back', 'cancelled')",
            name="ck_execution_jobs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    change_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("change_plans.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    # Relationships
    change_plan: Mapped["ChangePlan"] = relationship("ChangePlan", back_populates="execution_jobs")
    operation_logs: Mapped[List["OperationLog"]] = relationship(
        "OperationLog", back_populates="execution_job", cascade="all, delete-orphan"
    )


class OperationLog(Base):
    __tablename__ = "operation_logs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('started', 'completed', 'failed', 'rollback_completed', 'rollback_failed')",
            name="ck_operation_logs_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    execution_job_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("execution_jobs.id", ondelete="CASCADE"), nullable=False
    )
    change_plan_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("change_plan_items.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    source_path_snapshot: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    destination_path_snapshot: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="started")
    backup_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # Relationships
    execution_job: Mapped["ExecutionJob"] = relationship("ExecutionJob", back_populates="operation_logs")
    change_plan_item: Mapped["ChangePlanItem"] = relationship("ChangePlanItem", back_populates="operation_logs")
