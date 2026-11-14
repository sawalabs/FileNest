from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import CheckConstraint, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.scan_job import ScanJob
    from backend.app.db.models.change_plan import ChangePlan


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "engine IN ('local', 'ai')",
            name="ck_analysis_runs_engine",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_analysis_runs_status",
        ),
        Index("idx_analysis_runs_folder_created", "managed_folder_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    scan_job_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scan_jobs.id", ondelete="SET NULL"), nullable=True
    )
    analysis_type: Mapped[str] = mapped_column(String(64), nullable=False)
    engine: Mapped[str] = mapped_column(String(32), nullable=False, default="local")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    result_json: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="analysis_runs")
    scan_job: Mapped[Optional["ScanJob"]] = relationship("ScanJob", back_populates="analysis_runs")
    change_plans: Mapped[List["ChangePlan"]] = relationship("ChangePlan", back_populates="analysis_run")
