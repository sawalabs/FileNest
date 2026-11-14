from typing import TYPE_CHECKING, Optional
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.db.base import Base, generate_uuid, utc_now_iso

if TYPE_CHECKING:
    from backend.app.db.models.managed_folder import ManagedFolder
    from backend.app.db.models.scan_job import ScanJob


class FileRecord(Base):
    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("managed_folder_id", "relative_path", name="uq_files_folder_relative_path"),
        CheckConstraint("item_type IN ('file', 'directory')", name="ck_files_item_type"),
        CheckConstraint("size_bytes >= 0", name="ck_files_size_bytes"),
        CheckConstraint("is_hidden IN (0, 1)", name="ck_files_is_hidden"),
        CheckConstraint("is_deleted IN (0, 1)", name="ck_files_is_deleted"),
        Index("idx_files_folder_parent", "managed_folder_id", "parent_relative_path"),
        Index("idx_files_folder_type", "managed_folder_id", "item_type"),
        Index("idx_files_folder_size", "managed_folder_id", "size_bytes"),
        Index("idx_files_folder_extension", "managed_folder_id", "extension"),
        Index("idx_files_content_hash", "content_hash", sqlite_where=text("content_hash IS NOT NULL")),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    managed_folder_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("managed_folders.id", ondelete="CASCADE"), nullable=False
    )
    last_seen_scan_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scan_jobs.id", ondelete="SET NULL"), nullable=True
    )
    relative_path: Mapped[str] = mapped_column(String(1024), nullable=False)
    parent_relative_path: Mapped[str] = mapped_column(String(1024), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    extension: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    item_type: Mapped[str] = mapped_column(String(32), nullable=False, default="file")
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    modified_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_fs_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    hash_algorithm: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_hidden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_scanned_at: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False, default=utc_now_iso, onupdate=utc_now_iso)

    # Relationships
    managed_folder: Mapped["ManagedFolder"] = relationship("ManagedFolder", back_populates="files")
    last_seen_scan: Mapped[Optional["ScanJob"]] = relationship("ScanJob", back_populates="files_discovered")
