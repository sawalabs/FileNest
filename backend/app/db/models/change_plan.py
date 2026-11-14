from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.analysis_run import AnalysisRun
    from backend.app.db.models.execution import ExecutionJob, OperationLog


class ChangePlan(Base):
    __tablename__ = "change_plans"
    __table_args__ = (
        CheckConstraint(
            "plan_type IN ('organize', 'rename', 'manual')",
            name="ck_change_plans_plan_type",
        ),
        CheckConstraint(
            "status IN ('draft', 'pending_review', 'approved', 'rejected', 'executing', 'completed', 'failed', 'cancelled', 'stale')",
            name="ck_change_plans_status",
        ),
        CheckConstraint(
            "created_by IN ('user', 'ai')",
            name="ck_change_plans_created_by",
        ),
        Index("idx_change_plans_status", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    analysis_run_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_type: Mapped[str] = mapped_column(String(32), nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    created_by: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    approved_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="change_plans")
    analysis_run: Mapped[Optional["AnalysisRun"]] = relationship("AnalysisRun", back_populates="change_plans")
    items: Mapped[List["ChangePlanItem"]] = relationship(
        "ChangePlanItem", back_populates="change_plan", cascade="all, delete-orphan", order_by="ChangePlanItem.sequence_no"
    )
    execution_jobs: Mapped[List["ExecutionJob"]] = relationship(
        "ExecutionJob", back_populates="change_plan", cascade="all, delete-orphan"
    )


class ChangePlanItem(Base):
    __tablename__ = "change_plan_items"
    __table_args__ = (
        CheckConstraint(
            "operation IN ('create_directory', 'rename', 'move', 'copy', 'delete_to_recycle_bin')",
            name="ck_change_plan_items_operation",
        ),
        CheckConstraint(
            "status IN ('pending', 'approved', 'executing', 'completed', 'failed', 'skipped', 'conflict')",
            name="ck_change_plan_items_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    change_plan_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("change_plans.id", ondelete="CASCADE"), nullable=False
    )
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    source_relative_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    destination_relative_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    expected_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    expected_modified_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    expected_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    conflict_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    # Relationships
    change_plan: Mapped["ChangePlan"] = relationship("ChangePlan", back_populates="items")
    operation_logs: Mapped[List["OperationLog"]] = relationship("OperationLog", back_populates="change_plan_item")
