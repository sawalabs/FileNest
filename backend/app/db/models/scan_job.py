from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.file import FileRecord
    from backend.app.db.models.analysis_run import AnalysisRun


class ScanJob(Base):
    __tablename__ = "scan_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'running', 'completed', 'failed', 'cancelled')",
            name="ck_scan_jobs_status",
        ),
        CheckConstraint(
            "scan_type IN ('metadata', 'deep')",
            name="ck_scan_jobs_scan_type",
        ),
        Index("idx_scan_jobs_folder_created", "managed_folder_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    scan_type: Mapped[str] = mapped_column(String(32), nullable=False, default="metadata")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    files_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    folders_seen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bytes_seen: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    started_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    finished_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="scan_jobs")
    files_discovered: Mapped[List["FileRecord"]] = relationship("FileRecord", back_populates="last_seen_scan")
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship("AnalysisRun", back_populates="scan_job")
