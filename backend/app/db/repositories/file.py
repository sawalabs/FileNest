import stat
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.base import utc_now_iso
from backend.app.db.models.file import FileRecord


class FileRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(
        self,
        managed_folder_id: str,
        relative_path: str,
        name: str,
        item_type: str = "file",
        parent_relative_path: str = "",
        extension: Optional[str] = None,
        size_bytes: int = 0,
        content_hash: Optional[str] = None,
        scan_job_id: Optional[str] = None,
    ) -> FileRecord:
        record = self.get_by_path(managed_folder_id, relative_path)
        if record:
            record.name = name
            record.item_type = item_type
            record.parent_relative_path = parent_relative_path
            record.extension = extension
            record.size_bytes = size_bytes
            record.content_hash = content_hash
            record.is_deleted = 0
            if scan_job_id:
                record.last_seen_scan_id = scan_job_id
        else:
            record = FileRecord(
                managed_folder_id=managed_folder_id,
                relative_path=relative_path,
                parent_relative_path=parent_relative_path,
                name=name,
                item_type=item_type,
                extension=extension,
                size_bytes=size_bytes,
                content_hash=content_hash,
                is_deleted=0,
                last_seen_scan_id=scan_job_id,
            )
            self.db.add(record)

        self.db.commit()
        self.db.refresh(record)
        return record

    def bulk_sync_scan_results(
        self,
        managed_folder_id: str,
        scan_job_id: str,
        discovered_entries: List[Dict[str, Any]],
    ) -> Tuple[int, int]:
        """
        Synchronizes discovered filesystem entries into FileRecord and reconciles stale records.
        Returns (upserted_count, stale_marked_count).
        Does NOT touch or mutate any files on disk.
        """
        now = utc_now_iso()
        existing_stmt = select(FileRecord).where(FileRecord.managed_folder_id == managed_folder_id)
        existing_records = list(self.db.execute(existing_stmt).scalars().all())
        existing_map: Dict[str, FileRecord] = {r.relative_path: r for r in existing_records}

        seen_paths: Set[str] = set()
        upserted_count = 0

        for entry in discovered_entries:
            rel_path = entry["relative_path"]
            seen_paths.add(rel_path)

            parent_rel = Path(rel_path).parent.as_posix() if "/" in rel_path else ""
            if parent_rel == ".":
                parent_rel = ""

            record = existing_map.get(rel_path)
            if record:
                record.name = entry["name"]
                record.item_type = entry.get("item_type", "file")
                record.parent_relative_path = parent_rel
                record.extension = entry.get("extension")
                record.size_bytes = entry.get("size_bytes", 0)
                record.modified_at = entry.get("modified_at")
                record.is_hidden = 1 if entry.get("is_hidden") else 0
                record.is_deleted = 0
                record.last_seen_scan_id = scan_job_id
                record.last_scanned_at = now
                if entry.get("content_hash"):
                    record.content_hash = entry["content_hash"]
                    record.hash_algorithm = "sha256"
                if entry.get("mime_type"):
                    record.mime_type = entry["mime_type"]
            else:
                record = FileRecord(
                    managed_folder_id=managed_folder_id,
                    relative_path=rel_path,
                    parent_relative_path=parent_rel,
                    name=entry["name"],
                    item_type=entry.get("item_type", "file"),
                    extension=entry.get("extension"),
                    size_bytes=entry.get("size_bytes", 0),
                    modified_at=entry.get("modified_at"),
                    created_fs_at=entry.get("created_fs_at"),
                    mime_type=entry.get("mime_type"),
                    content_hash=entry.get("content_hash"),
                    hash_algorithm="sha256" if entry.get("content_hash") else None,
                    is_hidden=1 if entry.get("is_hidden") else 0,
                    is_deleted=0,
                    last_seen_scan_id=scan_job_id,
                    last_scanned_at=now,
                )
                self.db.add(record)
                existing_map[rel_path] = record
            upserted_count += 1

        # Reconcile stale records: any record in existing_map that was NOT seen in this scan
        stale_count = 0
        for rel_path, record in existing_map.items():
            if rel_path not in seen_paths and record.is_deleted == 0:
                record.is_deleted = 1
                record.last_scanned_at = now
                stale_count += 1

        self.db.commit()
        return (upserted_count, stale_count)

    def reconcile_folder(self, managed_folder_id: str, root_path: Path) -> Dict[str, int]:
        """
        Reconciles database records against the live filesystem for a Managed Folder.
        Stale/deleted files on disk are marked as deleted (is_deleted=1).
        Restored files are reactivated (is_deleted=0).
        Existing files with modified size/mtime are updated.
        Never touches or mutates any user files on the filesystem.
        """
        now = utc_now_iso()
        existing_stmt = select(FileRecord).where(FileRecord.managed_folder_id == managed_folder_id)
        records = list(self.db.execute(existing_stmt).scalars().all())

        checked = len(records)
        active_count = 0
        stale_marked = 0
        restored = 0
        updated = 0

        from backend.app.services.filesystem import format_timestamp, is_reparse_point_or_symlink

        for r in records:
            target_path = (root_path / r.relative_path).resolve()

            # Scope containment check
            try:
                target_path.relative_to(root_path)
            except ValueError:
                if r.is_deleted == 0:
                    r.is_deleted = 1
                    r.last_scanned_at = now
                    stale_marked += 1
                continue

            exists = target_path.exists()
            is_sym = is_reparse_point_or_symlink(target_path) if exists else False

            if not exists or is_sym:
                if r.is_deleted == 0:
                    r.is_deleted = 1
                    r.last_scanned_at = now
                    stale_marked += 1
            else:
                try:
                    st = target_path.stat(follow_symlinks=False)
                    is_dir = stat.S_ISDIR(st.st_mode)
                    current_size = st.st_size if not is_dir else 0
                    current_mtime = format_timestamp(st.st_mtime)

                    if r.is_deleted == 1:
                        r.is_deleted = 0
                        r.size_bytes = current_size
                        r.modified_at = current_mtime
                        r.last_scanned_at = now
                        restored += 1
                    elif r.size_bytes != current_size or r.modified_at != current_mtime:
                        r.size_bytes = current_size
                        r.modified_at = current_mtime
                        r.last_scanned_at = now
                        updated += 1
                    else:
                        r.last_scanned_at = now

                    active_count += 1
                except (PermissionError, OSError):
                    pass

        self.db.commit()
        return {
            "checked": checked,
            "active": active_count,
            "stale_marked": stale_marked,
            "restored": restored,
            "updated": updated,
        }

    def get_by_path(self, managed_folder_id: str, relative_path: str) -> Optional[FileRecord]:
        stmt = select(FileRecord).where(
            FileRecord.managed_folder_id == managed_folder_id,
            FileRecord.relative_path == relative_path,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_folder(self, managed_folder_id: str, item_type: Optional[str] = None) -> List[FileRecord]:
        stmt = select(FileRecord).where(FileRecord.managed_folder_id == managed_folder_id)
        if item_type:
            stmt = stmt.where(FileRecord.item_type == item_type)
        return list(self.db.execute(stmt).scalars().all())

    def find_by_content_hash(self, content_hash: str) -> List[FileRecord]:
        stmt = select(FileRecord).where(
            FileRecord.content_hash == content_hash,
            FileRecord.is_deleted == 0,
        )
        return list(self.db.execute(stmt).scalars().all())
