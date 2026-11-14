import json
import os
import stat
import tempfile
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import utc_now_iso
from backend.app.db.models.app_setting import AppSetting
from backend.app.db.models.file import FileRecord
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.organization import OrganizationRule
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.repositories.file import FileRepository
from backend.app.schemas.managed_folder import (
    FolderCapabilities,
    FolderExclusionCreate,
    FolderExclusionItem,
    FolderHealthCheck,
    FolderSummaryCards,
    FolderUsageStats,
    ManagedFolderCreate,
    ManagedFolderResponse,
    ManagedFolderUpdate,
)


class ManagedFolderException(Exception):
    """Custom exception for managed folder validation and scope violations."""
    pass


def is_reparse_point_or_symlink(path: Path) -> bool:
    """Detects if path is a symlink or Windows reparse point (junction/mount point)."""
    if path.is_symlink() or os.path.islink(str(path)):
        return True
    try:
        st = path.lstat()
        file_attrs = getattr(st, "st_file_attributes", 0)
        return bool(file_attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except Exception:
        return False


WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "COM0",
    "COM1",
    "COM2",
    "COM3",
    "COM4",
    "COM5",
    "COM6",
    "COM7",
    "COM8",
    "COM9",
    "COM¹",
    "COM²",
    "COM³",
    "LPT0",
    "LPT1",
    "LPT2",
    "LPT3",
    "LPT4",
    "LPT5",
    "LPT6",
    "LPT7",
    "LPT8",
    "LPT9",
    "LPT¹",
    "LPT²",
    "LPT³",
}


def is_windows_reserved_name(name: str) -> bool:
    """Checks whether a filename or path segment matches a Windows/DOS reserved device name."""
    if not name or not isinstance(name, str):
        return False
    clean = name.strip()
    base = clean.split(".")[0].strip().upper()
    return base in WINDOWS_RESERVED_NAMES


class PathValidator:
    """Validates canonical paths, protected Windows paths, and scope confinement."""

    @staticmethod
    def is_reserved_name(name: str) -> bool:
        return is_windows_reserved_name(name)

    @staticmethod
    def get_protected_paths() -> List[Path]:
        protected: List[Path] = []
        # Windows system directories
        windir = os.environ.get("WINDIR") or os.environ.get("SystemRoot")
        if windir:
            protected.append(Path(windir).resolve())

        prog_files = os.environ.get("ProgramFiles")
        if prog_files:
            protected.append(Path(prog_files).resolve())

        prog_files_x86 = os.environ.get("ProgramFiles(x86)")
        if prog_files_x86:
            protected.append(Path(prog_files_x86).resolve())

        # Common Windows drive roots like C:\Windows
        for common in ["C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)"]:
            p = Path(common)
            if p.exists():
                protected.append(p.resolve())

        # Application self-protection directories
        try:
            # managed_folder.py is at: <project_root>/backend/app/services/managed_folder.py
            project_root = Path(__file__).resolve().parents[3]
            protected.append(project_root)
            protected.append((project_root / "backend").resolve())
            protected.append((project_root / "data").resolve())
        except Exception:
            pass

        # Protect CWD if distinct
        try:
            cwd = Path.cwd().resolve()
            if cwd not in protected:
                protected.append(cwd)
        except Exception:
            pass

        # Protect SQLite database directory if not in a temporary test directory
        try:
            from backend.app.core.config import settings

            if settings.DATABASE_URL.startswith("sqlite:///") and not settings.DATABASE_URL.startswith("sqlite:///:memory:"):
                db_path_str = settings.DATABASE_URL.replace("sqlite:///", "")
                db_parent = Path(db_path_str).resolve().parent
                temp_dir = Path(tempfile.gettempdir()).resolve()
                if db_parent != temp_dir and temp_dir not in db_parent.parents:
                    if db_parent not in protected:
                        protected.append(db_parent)
        except Exception:
            pass

        return protected

    @classmethod
    def validate_new_root_path(cls, raw_path: str, existing_folders: List[ManagedFolder]) -> Path:
        """Validates that a proposed root path is canonical, exists, safe, and non-overlapping."""
        try:
            raw_p = Path(raw_path).expanduser()
            if raw_p.is_symlink() or os.path.islink(raw_path):
                raise ManagedFolderException(f"Symbolic links are not permitted as Managed Folders: {raw_path}")

            path = raw_p.resolve()
        except ManagedFolderException:
            raise
        except Exception as e:
            raise ManagedFolderException(f"Invalid path syntax: {e}")

        # 1. Existence and directory check
        if not path.exists():
            raise ManagedFolderException(f"Path does not exist: {path}")
        if not path.is_dir():
            raise ManagedFolderException(f"Path is not a directory: {path}")

        # 2. Reject symlinks and reparse points
        if path.is_symlink() or os.path.islink(str(path)):
            raise ManagedFolderException(f"Symbolic links are not permitted as Managed Folders: {path}")

        # 3. Reject drive roots directly (e.g. C:\, D:\)
        if len(path.parts) <= 1 or path == path.parent:
            raise ManagedFolderException(f"Registering an entire drive root is not permitted: {path}")

        # Reject Alternate Data Streams (ADS)
        drive = path.drive
        rest = str(path)[len(drive):]
        raw_drive = Path(raw_path).drive if raw_path else ""
        raw_rest = str(raw_path)[len(raw_drive):] if raw_path else ""
        if ":" in rest or ":" in raw_rest:
            raise ManagedFolderException("Alternate Data Streams (':') are not permitted in folder paths")

        # Reject Windows/DOS reserved device names in path segments
        for part in path.parts[1:]:
            if is_windows_reserved_name(part):
                raise ManagedFolderException(f"Windows reserved device name is not permitted in folder path: '{part}'")

        # 4. Reject Windows system and protected directories
        protected_list = cls.get_protected_paths()
        for protected in protected_list:
            if path == protected or protected in path.parents or path in protected.parents:
                raise ManagedFolderException(f"Path is inside or contains a protected system or application directory: {path}")

        # Special folder checks (Recycle bin, system volume)
        path_str_lower = str(path).lower()
        if "$recycle.bin" in path_str_lower or "system volume information" in path_str_lower:
            raise ManagedFolderException("System storage directories cannot be registered as Managed Folders")

        # 5. Check against existing registered folders for duplicates or nesting
        for existing in existing_folders:
            existing_path = Path(existing.root_path).resolve()
            if path == existing_path:
                raise ManagedFolderException(f"Folder is already registered: {path}")
            if existing_path in path.parents:
                raise ManagedFolderException(f"Path is nested inside already registered folder '{existing.name}': {existing_path}")
            if path in existing_path.parents:
                raise ManagedFolderException(f"Path contains already registered folder '{existing.name}': {existing_path}")

        return path

    @staticmethod
    def resolve_and_verify_scope(folder: ManagedFolder, relative_path: str) -> Path:
        """Confines a relative path strictly within the Managed Folder root."""
        if not folder.is_enabled:
            raise ManagedFolderException(f"Managed Folder '{folder.name}' is currently disabled")

        try:
            if not isinstance(relative_path, str):
                raise ManagedFolderException("Path must be a string")

            if "\0" in relative_path:
                raise ManagedFolderException("Null bytes are not permitted in filesystem paths")

            root = Path(folder.root_path).resolve()
            raw_p = Path(relative_path)
            if raw_p.is_absolute() or relative_path.startswith("/") or relative_path.startswith("\\"):
                raise ManagedFolderException(f"Access violation: path '{relative_path}' escapes Managed Folder root '{root}'")

            # Reject Alternate Data Streams (ADS) and drive colons
            if ":" in relative_path:
                raise ManagedFolderException("Alternate Data Streams or drive colons (':') are not permitted in filesystem paths")

            # Validate each segment for Windows reserved device names, trailing space/dot, and symlinks/reparse points
            curr = root
            for part in Path(relative_path).parts:
                if is_windows_reserved_name(part):
                    raise ManagedFolderException(f"Windows reserved device name is not permitted in path: '{part}'")
                if part not in (".", "..") and (part.endswith(".") or part.endswith(" ")):
                    raise ManagedFolderException(f"Trailing spaces and periods are not permitted in path names: '{part}'")
                curr = curr / part
                if is_reparse_point_or_symlink(curr):
                    raise ManagedFolderException(f"Cannot traverse symlink or reparse point: '{relative_path}'")

            target = curr.resolve()
        except ManagedFolderException:
            raise
        except Exception as e:
            raise ManagedFolderException(f"Invalid path syntax: {e}")

        # Check path containment
        if target != root and root not in target.parents:
            raise ManagedFolderException(f"Access violation: path '{relative_path}' escapes Managed Folder root '{root}'")

        return target


class ManagedFolderService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def register_folder(self, payload: ManagedFolderCreate) -> ManagedFolder:
        """Registers a new Managed Folder. Does NOT trigger automatic recursive scan."""
        stmt = select(ManagedFolder)
        existing_folders = list(self.db.execute(stmt).scalars().all())

        # Canonical path validation
        canonical_path = PathValidator.validate_new_root_path(payload.root_path, existing_folders)
        canonical_path_str = str(canonical_path)

        folder = ManagedFolder(
            name=payload.name.strip(),
            root_path=canonical_path_str,
            monitoring_enabled=1 if payload.monitoring_enabled else 0,
            scan_on_startup=1 if payload.scan_on_startup else 0,
            exclude_patterns_json=json.dumps(payload.exclude_patterns or []),
            is_enabled=1,
        )
        self.db.add(folder)
        self.db.commit()
        self.db.refresh(folder)

        # Save initial capabilities if provided
        caps = payload.capabilities or FolderCapabilities(monitoring=bool(payload.monitoring_enabled))
        self.update_folder_capabilities(folder.id, caps)

        # Audit log (Rule 80: no secrets or file contents)
        self.audit_repo.record(
            actor_type="user",
            action="folder_registered",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"name": folder.name, "root_path": folder.root_path},
        )
        logger.info("Successfully registered Managed Folder '%s' at %s", folder.name, folder.root_path)
        return folder

    def list_folders(self, only_enabled: bool = False) -> List[ManagedFolder]:
        stmt = select(ManagedFolder)
        if only_enabled:
            stmt = stmt.where(ManagedFolder.is_enabled == 1)
        return list(self.db.execute(stmt).scalars().all())

    def get_folder(self, folder_id: str) -> Optional[ManagedFolder]:
        return self.db.get(ManagedFolder, folder_id)

    def update_folder(self, folder_id: str, payload: ManagedFolderUpdate) -> ManagedFolder:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder with ID {folder_id} not found")

        changes = {}
        if payload.name is not None:
            folder.name = payload.name.strip()
            changes["name"] = folder.name
        if payload.monitoring_enabled is not None:
            folder.monitoring_enabled = 1 if payload.monitoring_enabled else 0
            changes["monitoring_enabled"] = folder.monitoring_enabled
            # Sync to capabilities
            caps = self.get_folder_capabilities(folder_id)
            caps.monitoring = bool(payload.monitoring_enabled)
            self.update_folder_capabilities(folder_id, caps)
        if payload.scan_on_startup is not None:
            folder.scan_on_startup = 1 if payload.scan_on_startup else 0
            changes["scan_on_startup"] = folder.scan_on_startup
        if payload.exclude_patterns is not None:
            folder.exclude_patterns_json = json.dumps(payload.exclude_patterns)
            changes["exclude_patterns"] = payload.exclude_patterns
        if payload.capabilities is not None:
            self.update_folder_capabilities(folder_id, payload.capabilities)
            changes["capabilities"] = payload.capabilities.model_dump()

        self.db.commit()
        self.db.refresh(folder)

        self.audit_repo.record(
            actor_type="user",
            action="folder_updated",
            entity_type="managed_folder",
            entity_id=folder.id,
            details=changes,
        )
        return folder

    def set_folder_enabled(self, folder_id: str, is_enabled: bool) -> ManagedFolder:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder with ID {folder_id} not found")

        folder.is_enabled = 1 if is_enabled else 0
        self.db.commit()
        self.db.refresh(folder)

        self.audit_repo.record(
            actor_type="user",
            action="folder_enabled" if is_enabled else "folder_disabled",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"is_enabled": folder.is_enabled},
        )
        return folder

    def unregister_folder(self, folder_id: str) -> ManagedFolder:
        """Unregisters folder (soft disable). Physical files are NOT deleted."""
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder with ID {folder_id} not found")

        folder.is_enabled = 0
        self.db.commit()
        self.db.refresh(folder)

        self.audit_repo.record(
            actor_type="user",
            action="folder_unregistered",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"name": folder.name, "root_path": folder.root_path},
        )
        logger.info("Unregistered Managed Folder '%s' (%s) without modifying files on disk", folder.name, folder.id)
        return folder

    def delete_folder(self, folder_id: str) -> ManagedFolder:
        """Permanently deletes the managed folder record and its associations from database. Physical files on disk are NEVER touched."""
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder with ID {folder_id} not found")

        self.audit_repo.record(
            actor_type="user",
            action="folder_deleted_permanently",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"name": folder.name, "root_path": folder.root_path},
        )
        self.db.delete(folder)
        self.db.commit()
        logger.info("Permanently deleted Managed Folder record '%s' (%s) from database. User files on disk untouched.", folder.name, folder.id)
        return folder

    # ==========================================
    # Capabilities Management
    # ==========================================
    def get_folder_capabilities(self, folder_id: str) -> FolderCapabilities:
        key = f"folder_capabilities:{folder_id}"
        setting = self.db.get(AppSetting, key)
        if setting and setting.value_json:
            try:
                return FolderCapabilities(**json.loads(setting.value_json))
            except Exception:
                pass
        # Fallback based on folder itself
        folder = self.get_folder(folder_id)
        mon = bool(folder.monitoring_enabled) if folder else False
        return FolderCapabilities(monitoring=mon)

    def update_folder_capabilities(self, folder_id: str, caps: FolderCapabilities) -> FolderCapabilities:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder {folder_id} not found")

        key = f"folder_capabilities:{folder_id}"
        val_str = json.dumps(caps.model_dump())
        setting = self.db.get(AppSetting, key)
        if setting:
            setting.value_json = val_str
            setting.updated_at = utc_now_iso()
        else:
            setting = AppSetting(key=key, value_json=val_str, updated_at=utc_now_iso())
            self.db.add(setting)

        # Sync monitoring toggle if needed
        folder.monitoring_enabled = 1 if caps.monitoring else 0
        self.db.commit()

        self.audit_repo.record(
            actor_type="user",
            action="folder_capabilities_updated",
            entity_type="managed_folder",
            entity_id=folder_id,
            details=caps.model_dump(),
        )
        return caps

    # ==========================================
    # Structured Exclusions Management
    # ==========================================
    def get_folder_exclusions(self, folder_id: str) -> List[FolderExclusionItem]:
        key = f"folder_exclusions:{folder_id}"
        setting = self.db.get(AppSetting, key)
        if setting and setting.value_json:
            try:
                raw_list = json.loads(setting.value_json)
                return [FolderExclusionItem(**item) for item in raw_list]
            except Exception:
                pass
        return []

    def add_folder_exclusion(self, folder_id: str, payload: FolderExclusionCreate) -> FolderExclusionItem:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder {folder_id} not found")

        items = self.get_folder_exclusions(folder_id)
        new_item = FolderExclusionItem(
            id=str(uuid.uuid4()),
            folder_id=folder_id,
            exclusion_type=payload.exclusion_type,
            value=payload.value.strip(),
            reason=payload.reason,
            is_enabled=True,
            created_at=utc_now_iso(),
        )
        items.append(new_item)

        key = f"folder_exclusions:{folder_id}"
        val_str = json.dumps([i.model_dump() for i in items])
        setting = self.db.get(AppSetting, key)
        if setting:
            setting.value_json = val_str
            setting.updated_at = utc_now_iso()
        else:
            setting = AppSetting(key=key, value_json=val_str, updated_at=utc_now_iso())
            self.db.add(setting)
        self.db.commit()

        self.audit_repo.record(
            actor_type="user",
            action="folder_exclusion_added",
            entity_type="managed_folder",
            entity_id=folder_id,
            details=new_item.model_dump(),
        )
        return new_item

    def delete_folder_exclusion(self, folder_id: str, exclusion_id: str) -> bool:
        items = self.get_folder_exclusions(folder_id)
        filtered = [i for i in items if i.id != exclusion_id]
        if len(filtered) == len(items):
            return False

        key = f"folder_exclusions:{folder_id}"
        val_str = json.dumps([i.model_dump() for i in filtered])
        setting = self.db.get(AppSetting, key)
        if setting:
            setting.value_json = val_str
            setting.updated_at = utc_now_iso()
            self.db.commit()

        self.audit_repo.record(
            actor_type="user",
            action="folder_exclusion_removed",
            entity_type="managed_folder",
            entity_id=folder_id,
            details={"exclusion_id": exclusion_id},
        )
        return True

    # ==========================================
    # Folder Health & Usage Diagnostics
    # ==========================================
    def check_folder_health(self, folder_id: str) -> FolderHealthCheck:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder {folder_id} not found")

        path = Path(folder.root_path)
        exists = path.exists()
        can_read = os.access(path, os.R_OK) if exists else False
        can_write = os.access(path, os.W_OK) if exists else False
        is_symlink = path.is_symlink() if exists else False
        is_reparse = False
        try:
            is_reparse = bool(path.stat().st_file_attributes & 0x400) if hasattr(path.stat(), "st_file_attributes") else False
        except Exception:
            is_reparse = False

        overall_status = "healthy"
        last_error = None
        if not exists:
            overall_status = "inaccessible"
            last_error = "Directory does not exist on disk"
        elif not can_read:
            overall_status = "error"
            last_error = "Read permission denied"
        elif is_symlink or is_reparse:
            overall_status = "warning"
            last_error = "Reparse point or symlink detected"
        elif not can_write:
            overall_status = "warning"
            last_error = "Directory is read-only"

        watcher_status = "active" if folder.monitoring_enabled and folder.is_enabled else ("paused" if folder.monitoring_enabled else "stopped")

        return FolderHealthCheck(
            folder_id=folder.id,
            folder_name=folder.name,
            root_path=folder.root_path,
            is_accessible=exists and can_read,
            exists=exists,
            can_read=can_read,
            can_write=can_write,
            is_symlink=is_symlink,
            is_reparse_point=is_reparse,
            watcher_status=watcher_status,
            last_scanned_at=folder.last_scanned_at,
            last_error=last_error,
            overall_status=overall_status,
        )

    def get_folder_usage(self, folder_id: str) -> FolderUsageStats:
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder {folder_id} not found")

        stmt = select(
            func.coalesce(func.sum(FileRecord.size_bytes), 0),
            func.count(FileRecord.id),
        ).where(
            FileRecord.managed_folder_id == folder_id,
            FileRecord.is_deleted == 0,
            FileRecord.item_type == "file",
        )
        total_size, total_files = self.db.execute(stmt).first() or (0, 0)

        return FolderUsageStats(
            folder_id=folder.id,
            total_size_bytes=int(total_size),
            total_files_count=int(total_files),
            storage_limit_bytes=None,
            usage_percentage=None,
            last_scanned_at=folder.last_scanned_at,
        )

    def get_summary_cards(self) -> FolderSummaryCards:
        folders = self.list_folders()
        total_folders = len(folders)
        active_folders = sum(1 for f in folders if f.is_enabled)
        monitored = sum(1 for f in folders if f.monitoring_enabled and f.is_enabled)

        # Total files and size
        stmt = select(
            func.coalesce(func.sum(FileRecord.size_bytes), 0),
            func.count(FileRecord.id),
        ).where(
            FileRecord.is_deleted == 0,
            FileRecord.item_type == "file",
        )
        total_size, total_files = self.db.execute(stmt).first() or (0, 0)

        # Active rules count
        rule_stmt = select(func.count(OrganizationRule.id)).where(OrganizationRule.is_enabled == 1)
        active_rules = self.db.execute(rule_stmt).scalar() or 0

        # Health rollup
        health_status = "healthy"
        for f in folders:
            if f.is_enabled:
                p = Path(f.root_path)
                if not p.exists() or not os.access(p, os.R_OK):
                    health_status = "warning"
                    break

        return FolderSummaryCards(
            total_folders=total_folders,
            active_folders=active_folders,
            total_size_bytes=int(total_size),
            total_files=int(total_files),
            active_rules_count=int(active_rules),
            monitored_folders_count=monitored,
            health_status=health_status,
        )

    def build_folder_response(self, folder: ManagedFolder) -> ManagedFolderResponse:
        caps = self.get_folder_capabilities(folder.id)
        usage = self.get_folder_usage(folder.id)
        health = self.check_folder_health(folder.id)
        return ManagedFolderResponse.from_orm_model(
            folder,
            capabilities=caps,
            size=usage.total_size_bytes,
            files_count=usage.total_files_count,
            health=health.overall_status,
        )

    def reconcile_folder(self, folder_id: str) -> Dict[str, Any]:
        """
        Reconciles database records against the live filesystem for a Managed Folder.
        Stale/deleted files on disk are marked as deleted (is_deleted=1).
        Restored files are reactivated (is_deleted=0).
        Existing files with modified size/mtime are updated.
        Never touches or mutates any user files on the filesystem.
        """
        folder = self.get_folder(folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder '{folder_id}' not found")
        root = Path(folder.root_path).resolve()
        file_repo = FileRepository(self.db)
        stats = file_repo.reconcile_folder(folder.id, root)

        self.audit_repo.record(
            actor_type="system",
            action="folder_reconciled",
            entity_type="managed_folder",
            entity_id=folder.id,
            details=stats,
        )
        return {
            "managed_folder_id": folder.id,
            "managed_folder_name": folder.name,
            **stats,
        }
