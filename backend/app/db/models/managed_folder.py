from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Integer, String, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.scan_job import ScanJob
    from backend.app.db.models.file import FileRecord
    from backend.app.db.models.analysis_run import AnalysisRun
    from backend.app.db.models.change_plan import ChangePlan
    from backend.app.db.models.monitoring import MonitoringConfig, MonitoringEvent
    from backend.app.db.models.organization import OrganizationRule


class ManagedFolder(Base):
    __tablename__ = "managed_folders"
    __table_args__ = (
        CheckConstraint("is_enabled IN (0, 1)", name="ck_managed_folders_is_enabled"),
        CheckConstraint("monitoring_enabled IN (0, 1)", name="ck_managed_folders_monitoring_enabled"),
        CheckConstraint("scan_on_startup IN (0, 1)", name="ck_managed_folders_scan_on_startup"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    root_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    is_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    monitoring_enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scan_on_startup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exclude_patterns_json: Mapped[str] = mapped_column(String, nullable=False, default="[]")
    last_scanned_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    # Relationships
    scan_jobs: Mapped[List["ScanJob"]] = relationship("ScanJob", back_populates="managed_folder", cascade="all, delete-orphan")
    files: Mapped[List["FileRecord"]] = relationship("FileRecord", back_populates="managed_folder", cascade="all, delete-orphan")
    analysis_runs: Mapped[List["AnalysisRun"]] = relationship("AnalysisRun", back_populates="managed_folder", cascade="all, delete-orphan")
    change_plans: Mapped[List["ChangePlan"]] = relationship("ChangePlan", back_populates="managed_folder", cascade="all, delete-orphan")
    monitoring_config: Mapped[Optional["MonitoringConfig"]] = relationship("MonitoringConfig", back_populates="managed_folder", uselist=False, cascade="all, delete-orphan")
    monitoring_events: Mapped[List["MonitoringEvent"]] = relationship("MonitoringEvent", back_populates="managed_folder", cascade="all, delete-orphan")
    organization_rules: Mapped[List["OrganizationRule"]] = relationship("OrganizationRule", back_populates="managed_folder", cascade="all, delete-orphan")
