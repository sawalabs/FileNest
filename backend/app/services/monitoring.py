import fnmatch
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

from backend.app.core.logging import logger
from backend.app.db.base import utc_now_iso
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.monitoring import MonitoringConfig, MonitoringEvent
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.session import SessionLocal
from backend.app.schemas.monitoring import (
    ActivityChartPoint,
    ActivityChartResponse,
    DistributionItem,
    DistributionResponse,
    MonitoringConfigResponse,
    MonitoringConfigUpdate,
    MonitoringEventResponse,
    MonitoringSummaryStats,
    WatcherItemResponse,
)

DEFAULT_IGNORE_PATTERNS = [
    "*.tmp",
    "*~",
    "~$*",
    ".git*",
    "node_modules*",
    "__pycache__*",
    ".trash*",
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
]


class MonitoringException(Exception):
    pass


class FolderChangeEventHandler(FileSystemEventHandler):
    """Normalized, debounced Watchdog event handler confined to a specific Managed Folder."""

    def __init__(self, folder_id: str, root_path: str, service: "MonitoringManagerService") -> None:
        super().__init__()
        self.folder_id = folder_id
        self.root_path = Path(root_path).resolve()
        self.service = service

    def _process_event(
        self,
        event_type: str,
        src_path_str: str,
        dst_path_str: Optional[str] = None,
        is_directory: bool = False,
    ) -> None:
        try:
            # Check if watcher is currently paused
            if self.service.is_watcher_paused(self.folder_id):
                return

            src_path = Path(src_path_str).resolve()

            # Boundary confinement verification
            try:
                rel_path = src_path.relative_to(self.root_path).as_posix()
            except ValueError:
                # Event outside the managed folder boundary; ignore for safety
                return

            if rel_path in (".", ""):
                return

            # Check ignore patterns
            if self.service.should_ignore(self.folder_id, rel_path, src_path.name):
                return

            dst_rel: Optional[str] = None
            if dst_path_str:
                dst_path = Path(dst_path_str).resolve()
                try:
                    dst_rel = dst_path.relative_to(self.root_path).as_posix()
                except ValueError:
                    dst_rel = None

            # Debounce and deduplication check
            event_key = f"{self.folder_id}:{event_type}:{rel_path}"
            if not self.service.record_debounce(self.folder_id, event_key):
                return

            # Capture file size if file exists on disk
            file_size: Optional[int] = None
            if event_type in ("created", "modified") and src_path.exists() and not is_directory:
                try:
                    file_size = src_path.stat().st_size
                except Exception:
                    file_size = None

            # Persist event into database
            self.service.persist_event(
                folder_id=self.folder_id,
                event_type=event_type,
                relative_path=rel_path,
                destination_relative_path=dst_rel,
                event_key=event_key,
                size_bytes=file_size,
            )
        except Exception as e:
            logger.error(f"Error handling monitoring event for folder {self.folder_id}: {e}")

    def on_created(self, event: FileSystemEvent) -> None:
        if isinstance(event, (FileCreatedEvent, DirCreatedEvent)):
            self._process_event("created", event.src_path, is_directory=event.is_directory)

    def on_modified(self, event: FileSystemEvent) -> None:
        # Ignore directory modification timestamps on Windows to prevent noise
        if isinstance(event, FileModifiedEvent):
            self._process_event("modified", event.src_path, is_directory=False)

    def on_deleted(self, event: FileSystemEvent) -> None:
        if isinstance(event, (FileDeletedEvent, DirDeletedEvent)):
            self._process_event("deleted", event.src_path, is_directory=event.is_directory)

    def on_moved(self, event: FileSystemEvent) -> None:
        if isinstance(event, (FileMovedEvent, DirMovedEvent)):
            dest = getattr(event, "dest_path", None)
            self._process_event("moved", event.src_path, dst_path_str=dest, is_directory=event.is_directory)


class MonitoringManagerService:
    _instance: Optional["MonitoringManagerService"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "MonitoringManagerService":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return

        self._watchers: Dict[str, Dict[str, Any]] = {}
        self._debounce_records: Dict[str, float] = {}
        self._debounce_lock = threading.Lock()
        self._session_factory = SessionLocal
        self._initialized = True
        logger.info("MonitoringManagerService initialized")

    def set_session_factory(self, factory) -> None:
        self._session_factory = factory

    def get_session(self) -> Session:
        return self._session_factory()

    def _resolve_session(self, db: Optional[Session] = None) -> Tuple[Session, bool]:
        if db is not None:
            return db, False
        return self.get_session(), True

    # -------------------------------------------------------------------------
    # Debounce and Filter Helpers
    # -------------------------------------------------------------------------

    def record_debounce(self, folder_id: str, event_key: str) -> bool:
        """Sliding window debounce and deduplication. Returns True if event should be recorded."""
        now = time.time()
        debounce_ms = 1000
        watcher_info = self._watchers.get(folder_id)
        if watcher_info:
            if not watcher_info.get("deduplication_enabled", True):
                return True
            if "debounce_ms" in watcher_info:
                debounce_ms = watcher_info["debounce_ms"]

        debounce_sec = max(0.1, debounce_ms / 1000.0)

        with self._debounce_lock:
            # Clean expired records periodically
            if len(self._debounce_records) > 2000:
                cutoff = now - 60.0
                self._debounce_records = {
                    k: v for k, v in self._debounce_records.items() if v > cutoff
                }

            last_time = self._debounce_records.get(event_key)
            if last_time and (now - last_time) < debounce_sec:
                # Suppressed by debounce
                self._debounce_records[event_key] = now
                return False

            self._debounce_records[event_key] = now
            return True

    def should_ignore(self, folder_id: str, relative_path: str, filename: str) -> bool:
        """Determines whether a path or file matches default, global, or custom ignore patterns."""
        watcher_info = self._watchers.get(folder_id, {})
        global_patterns: List[str] = watcher_info.get("global_ignore_patterns", [])
        custom_patterns: List[str] = watcher_info.get("ignore_patterns", [])

        all_patterns = list(dict.fromkeys(DEFAULT_IGNORE_PATTERNS + global_patterns + custom_patterns))

        # Check against relative path parts and filename
        path_parts = relative_path.split("/")
        for pattern in all_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True
        return False

    def is_watcher_paused(self, folder_id: str) -> bool:
        watcher_info = self._watchers.get(folder_id)
        if watcher_info:
            return watcher_info.get("status") == "paused"
        return False

    # -------------------------------------------------------------------------
    # Database Persistence
    # -------------------------------------------------------------------------

    def persist_event(
        self,
        folder_id: str,
        event_type: str,
        relative_path: str,
        destination_relative_path: Optional[str] = None,
        event_key: str = "",
        size_bytes: Optional[int] = None,
    ) -> None:
        """Saves a normalized filesystem event to the database and records notable audit events."""
        db: Session = self.get_session()
        try:
            event = MonitoringEvent(
                managed_folder_id=folder_id,
                event_type=event_type,
                relative_path=relative_path,
                destination_relative_path=destination_relative_path,
                event_key=event_key,
                status="processed",
                occurred_at=utc_now_iso(),
                processed_at=utc_now_iso(),
            )
            db.add(event)
            db.commit()

            # Record audit log for monitoring activity tracking
            audit_repo = AuditLogRepository(db)
            audit_repo.record(
                actor_type="system",
                action=f"file_{event_type}" if event_type in ("created", "modified", "deleted") else "file_moved",
                entity_type="file",
                entity_id=None,
                details={
                    "folder_id": folder_id,
                    "event_type": event_type,
                    "relative_path": relative_path,
                    "destination": destination_relative_path,
                    "size_bytes": size_bytes,
                },
            )

            # Trigger automated evaluation of approved rules
            if event_type in ("created", "modified"):
                try:
                    from backend.app.services.rules_automation import RulesAutomationService
                    rules_svc = RulesAutomationService(db)
                    rules_svc.evaluate_event(event)
                except Exception as re_err:
                    logger.warning(f"Error evaluating rules on monitoring event: {re_err}")
        except Exception as e:
            logger.error(f"Failed to persist monitoring event: {e}")
            db.rollback()
        finally:
            db.close()

    # -------------------------------------------------------------------------
    # Watcher Lifecycle Management
    # -------------------------------------------------------------------------

    def start_all_enabled(self, db: Optional[Session] = None) -> None:
        """Auto-starts watchers for all registered Managed Folders that have monitoring enabled."""
        session, should_close = self._resolve_session(db)
        try:
            folders = (
                session.execute(
                    select(ManagedFolder).where(
                        ManagedFolder.is_enabled == 1,
                        ManagedFolder.monitoring_enabled == 1,
                    )
                )
                .scalars()
                .all()
            )
            logger.info(f"Auto-starting filesystem watchers for {len(folders)} enabled folder(s)")
            for folder in folders:
                try:
                    self.start_watcher(folder.id, persist=False, db=session)
                except Exception as e:
                    logger.warning(f"Could not auto-start watcher for folder '{folder.name}': {e}")
        finally:
            if should_close:
                session.close()

    def sync_global_settings(self, mon_settings: Any) -> None:
        """Applies updated MonitoringGlobalSettings to active watchers immediately."""
        if not getattr(mon_settings, "enable_monitoring", True):
            self.stop_all()
            return

        global_patterns = list(getattr(mon_settings, "global_ignore_patterns", []) or [])
        debounce_ms = int(getattr(mon_settings, "debounce_interval_ms", 1000))
        dedup_enabled = bool(getattr(mon_settings, "deduplication_enabled", True))

        for watcher_info in self._watchers.values():
            watcher_info["global_ignore_patterns"] = global_patterns
            watcher_info["debounce_ms"] = debounce_ms
            watcher_info["deduplication_enabled"] = dedup_enabled

    def start_watcher(
        self, folder_id: str, persist: bool = True, db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Starts watchdog observer for a specific registered Managed Folder."""
        session, should_close = self._resolve_session(db)
        try:
            from backend.app.services.settings_service import SettingsService

            mon_settings = SettingsService(session).get_monitoring_settings()
            if not mon_settings.enable_monitoring:
                raise MonitoringException("Global file monitoring is currently disabled in Settings")

            folder = session.get(ManagedFolder, folder_id)
            if not folder:
                raise MonitoringException(f"Managed Folder '{folder_id}' not found")
            if not folder.is_enabled:
                raise MonitoringException(f"Managed Folder '{folder.name}' is disabled")

            root_path = Path(folder.root_path).resolve()
            if not root_path.exists() or not root_path.is_dir():
                raise MonitoringException(f"Folder root path does not exist on disk: {root_path}")

            # Get or create MonitoringConfig initialized with global preferences
            config = folder.monitoring_config
            if not config:
                config = MonitoringConfig(
                    managed_folder_id=folder.id,
                    is_enabled=1,
                    recursive=1 if mon_settings.recursive_monitoring_default else 0,
                    debounce_ms=mon_settings.debounce_interval_ms,
                    ignore_patterns_json=json.dumps(mon_settings.global_ignore_patterns),
                )
                session.add(config)
                session.commit()
                session.refresh(config)

            ignore_patterns: List[str] = []
            if config.ignore_patterns_json:
                try:
                    ignore_patterns = json.loads(config.ignore_patterns_json)
                except Exception:
                    ignore_patterns = []

            # If existing watcher is running, stop it first
            if folder_id in self._watchers:
                existing = self._watchers[folder_id]
                try:
                    if existing.get("observer"):
                        existing["observer"].stop()
                        existing["observer"].join(timeout=2)
                except Exception:
                    pass

            observer = Observer()
            handler = FolderChangeEventHandler(folder_id, str(root_path), self)
            observer.schedule(handler, str(root_path), recursive=bool(config.recursive))
            observer.start()

            self._watchers[folder_id] = {
                "observer": observer,
                "handler": handler,
                "status": "watching",
                "error_message": None,
                "root_path": str(root_path),
                "recursive": bool(config.recursive),
                "debounce_ms": config.debounce_ms,
                "deduplication_enabled": mon_settings.deduplication_enabled,
                "global_ignore_patterns": list(mon_settings.global_ignore_patterns),
                "ignore_patterns": ignore_patterns,
                "started_at": utc_now_iso(),
            }

            if persist:
                folder.monitoring_enabled = 1
                config.is_enabled = 1
                session.commit()

                audit_repo = AuditLogRepository(session)
                audit_repo.record(
                    actor_type="user",
                    action="monitoring_started",
                    entity_type="managed_folder",
                    entity_id=folder_id,
                    details={"folder_name": folder.name, "root_path": str(root_path)},
                )

            logger.info(f"Watcher started for folder '{folder.name}' ({root_path})")
            return self._watchers[folder_id]
        finally:
            if should_close:
                session.close()

    def stop_watcher(
        self, folder_id: str, persist: bool = True, db: Optional[Session] = None
    ) -> bool:
        """Stops watchdog observer for a specific Managed Folder."""
        session, should_close = self._resolve_session(db)
        try:
            folder = session.get(ManagedFolder, folder_id)
            if folder and persist:
                folder.monitoring_enabled = 0
                if folder.monitoring_config:
                    folder.monitoring_config.is_enabled = 0
                session.commit()

                audit_repo = AuditLogRepository(session)
                audit_repo.record(
                    actor_type="user",
                    action="monitoring_stopped",
                    entity_type="managed_folder",
                    entity_id=folder_id,
                    details={"folder_name": folder.name},
                )

            if folder_id in self._watchers:
                watcher = self._watchers[folder_id]
                try:
                    obs = watcher.get("observer")
                    if obs and obs.is_alive():
                        obs.stop()
                        obs.join(timeout=2)
                except Exception as e:
                    logger.warning(f"Error stopping observer for {folder_id}: {e}")
                self._watchers[folder_id]["status"] = "stopped"
                self._watchers[folder_id]["observer"] = None
                return True
            return False
        finally:
            if should_close:
                session.close()

    def pause_watcher(self, folder_id: str, db: Optional[Session] = None) -> bool:
        """Temporarily pauses event collection for a monitored folder."""
        if folder_id not in self._watchers or self._watchers[folder_id]["status"] != "watching":
            raise MonitoringException(f"No active watcher running for folder '{folder_id}'")

        self._watchers[folder_id]["status"] = "paused"

        session, should_close = self._resolve_session(db)
        try:
            audit_repo = AuditLogRepository(session)
            audit_repo.record(
                actor_type="user",
                action="monitoring_paused",
                entity_type="managed_folder",
                entity_id=folder_id,
            )
        finally:
            if should_close:
                session.close()
        return True

    def resume_watcher(self, folder_id: str, db: Optional[Session] = None) -> bool:
        """Resumes event collection for a paused folder watcher."""
        if folder_id not in self._watchers:
            return bool(self.start_watcher(folder_id, db=db))

        if self._watchers[folder_id]["status"] == "paused":
            self._watchers[folder_id]["status"] = "watching"
            session, should_close = self._resolve_session(db)
            try:
                audit_repo = AuditLogRepository(session)
                audit_repo.record(
                    actor_type="user",
                    action="monitoring_resumed",
                    entity_type="managed_folder",
                    entity_id=folder_id,
                )
            finally:
                if should_close:
                    session.close()
            return True
        elif self._watchers[folder_id]["status"] == "stopped":
            return bool(self.start_watcher(folder_id, db=db))
        return True

    def stop_all(self) -> None:
        """Gracefully stops all active watchdog observers (e.g. during application shutdown)."""
        logger.info(f"Stopping all {len(self._watchers)} filesystem watchers...")
        for folder_id, watcher in list(self._watchers.items()):
            try:
                obs = watcher.get("observer")
                if obs and obs.is_alive():
                    obs.stop()
                    obs.join(timeout=2)
            except Exception as e:
                logger.warning(f"Error shutting down watcher {folder_id}: {e}")
        self._watchers.clear()

    # -------------------------------------------------------------------------
    # Status & Information Queries
    # -------------------------------------------------------------------------

    def get_watchers_list(self, db: Optional[Session] = None) -> List[WatcherItemResponse]:
        """Returns the status and metrics for all registered Managed Folders."""
        session, should_close = self._resolve_session(db)
        try:
            folders = session.execute(select(ManagedFolder)).scalars().all()
            one_day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

            items: List[WatcherItemResponse] = []
            for f in folders:
                watcher = self._watchers.get(f.id)
                status = "stopped"
                error_msg = None
                if watcher:
                    status = watcher.get("status", "stopped")
                    error_msg = watcher.get("error_message")
                elif f.monitoring_enabled and f.is_enabled:
                    status = "stopped"

                config = f.monitoring_config
                recursive = bool(config.recursive) if config else True
                debounce_ms = config.debounce_ms if config else 1000
                ignore_patterns: List[str] = []
                if config and config.ignore_patterns_json:
                    try:
                        ignore_patterns = json.loads(config.ignore_patterns_json)
                    except Exception:
                        ignore_patterns = []

                # Count events in last 24h
                count_24h = (
                    session.execute(
                        select(func.count(MonitoringEvent.id)).where(
                            MonitoringEvent.managed_folder_id == f.id,
                            MonitoringEvent.occurred_at >= one_day_ago,
                        )
                    ).scalar()
                    or 0
                )

                # Latest event timestamp
                last_event = session.execute(
                    select(MonitoringEvent.occurred_at)
                    .where(MonitoringEvent.managed_folder_id == f.id)
                    .order_by(desc(MonitoringEvent.occurred_at))
                    .limit(1)
                ).scalar_one_or_none()

                items.append(
                    WatcherItemResponse(
                        folder_id=f.id,
                        folder_name=f.name,
                        root_path=f.root_path,
                        status=status,
                        is_enabled=bool(f.monitoring_enabled and f.is_enabled),
                        recursive=recursive,
                        debounce_ms=debounce_ms,
                        ignore_patterns=ignore_patterns,
                        events_count_24h=count_24h,
                        last_event_at=last_event,
                        error_message=error_msg,
                    )
                )
            return items
        finally:
            if should_close:
                session.close()

    def update_config(
        self, folder_id: str, payload: MonitoringConfigUpdate, db: Optional[Session] = None
    ) -> MonitoringConfigResponse:
        """Updates watcher configuration (debounce_ms, recursive, ignore_patterns)."""
        session, should_close = self._resolve_session(db)
        try:
            folder = session.get(ManagedFolder, folder_id)
            if not folder:
                raise MonitoringException(f"Managed Folder '{folder_id}' not found")

            config = folder.monitoring_config
            if not config:
                config = MonitoringConfig(
                    managed_folder_id=folder.id,
                    is_enabled=1 if folder.monitoring_enabled else 0,
                    recursive=1,
                    debounce_ms=1000,
                    ignore_patterns_json="[]",
                )
                session.add(config)

            if payload.is_enabled is not None:
                config.is_enabled = 1 if payload.is_enabled else 0
                folder.monitoring_enabled = config.is_enabled
            if payload.recursive is not None:
                config.recursive = 1 if payload.recursive else 0
            if payload.debounce_ms is not None:
                config.debounce_ms = payload.debounce_ms
            if payload.ignore_patterns is not None:
                config.ignore_patterns_json = json.dumps(payload.ignore_patterns)

            config.updated_at = utc_now_iso()
            session.commit()
            session.refresh(config)

            # If watcher is active, restart observer to apply settings
            if folder.monitoring_enabled and folder.is_enabled:
                self.start_watcher(folder.id, persist=False, db=session)
            elif not folder.monitoring_enabled:
                self.stop_watcher(folder.id, persist=False, db=session)

            patterns: List[str] = []
            try:
                patterns = json.loads(config.ignore_patterns_json)
            except Exception:
                patterns = []

            return MonitoringConfigResponse(
                id=config.id,
                managed_folder_id=config.managed_folder_id,
                is_enabled=bool(config.is_enabled),
                recursive=bool(config.recursive),
                debounce_ms=config.debounce_ms,
                ignore_patterns=patterns,
                created_at=config.created_at,
                updated_at=config.updated_at,
            )
        finally:
            if should_close:
                session.close()

    def get_summary_stats(self, db: Optional[Session] = None) -> MonitoringSummaryStats:
        """Computes summary metrics for Monitoring dashboard cards."""
        session, should_close = self._resolve_session(db)
        try:
            one_day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

            monitored_folders_count = (
                session.execute(
                    select(func.count(ManagedFolder.id)).where(
                        ManagedFolder.is_enabled == 1,
                        ManagedFolder.monitoring_enabled == 1,
                    )
                ).scalar()
                or 0
            )

            active_watchers_count = sum(
                1 for w in self._watchers.values() if w.get("status") == "watching"
            )

            total_events_24h = (
                session.execute(
                    select(func.count(MonitoringEvent.id)).where(
                        MonitoringEvent.occurred_at >= one_day_ago
                    )
                ).scalar()
                or 0
            )

            created_count = (
                session.execute(
                    select(func.count(MonitoringEvent.id)).where(
                        MonitoringEvent.event_type == "created",
                        MonitoringEvent.occurred_at >= one_day_ago,
                    )
                ).scalar()
                or 0
            )

            modified_count = (
                session.execute(
                    select(func.count(MonitoringEvent.id)).where(
                        MonitoringEvent.event_type == "modified",
                        MonitoringEvent.occurred_at >= one_day_ago,
                    )
                ).scalar()
                or 0
            )

            deleted_count = (
                session.execute(
                    select(func.count(MonitoringEvent.id)).where(
                        MonitoringEvent.event_type == "deleted",
                        MonitoringEvent.occurred_at >= one_day_ago,
                    )
                ).scalar()
                or 0
            )

            return MonitoringSummaryStats(
                monitored_folders_count=monitored_folders_count,
                active_watchers_count=active_watchers_count,
                total_events_24h=total_events_24h,
                files_created_count=created_count,
                files_modified_count=modified_count,
                files_deleted_count=deleted_count,
                total_change_size_bytes=0,
            )
        finally:
            if should_close:
                session.close()

    def get_events(
        self,
        folder_id: Optional[str] = None,
        event_type: Optional[str] = None,
        time_range: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        db: Optional[Session] = None,
    ) -> Tuple[List[MonitoringEventResponse], int]:
        """Queries historical monitoring events with filtering and pagination."""
        session, should_close = self._resolve_session(db)
        try:
            stmt = select(MonitoringEvent).order_by(desc(MonitoringEvent.occurred_at))
            count_stmt = select(func.count(MonitoringEvent.id))

            if folder_id and folder_id != "all":
                stmt = stmt.where(MonitoringEvent.managed_folder_id == folder_id)
                count_stmt = count_stmt.where(MonitoringEvent.managed_folder_id == folder_id)

            if event_type and event_type != "all":
                stmt = stmt.where(MonitoringEvent.event_type == event_type)
                count_stmt = count_stmt.where(MonitoringEvent.event_type == event_type)

            if time_range:
                now = datetime.now(timezone.utc)
                cutoff: Optional[str] = None
                if time_range == "last_hour":
                    cutoff = (now - timedelta(hours=1)).isoformat()
                elif time_range == "last_24h":
                    cutoff = (now - timedelta(hours=24)).isoformat()
                elif time_range == "last_7d":
                    cutoff = (now - timedelta(days=7)).isoformat()
                elif time_range == "last_30d":
                    cutoff = (now - timedelta(days=30)).isoformat()

                if cutoff:
                    stmt = stmt.where(MonitoringEvent.occurred_at >= cutoff)
                    count_stmt = count_stmt.where(MonitoringEvent.occurred_at >= cutoff)

            if search:
                escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
                pattern = f"%{escaped}%"
                stmt = stmt.where(
                    or_(
                        MonitoringEvent.relative_path.ilike(pattern, escape="\\"),
                        MonitoringEvent.destination_relative_path.ilike(pattern, escape="\\"),
                    )
                )
                count_stmt = count_stmt.where(
                    or_(
                        MonitoringEvent.relative_path.ilike(pattern, escape="\\"),
                        MonitoringEvent.destination_relative_path.ilike(pattern, escape="\\"),
                    )
                )

            total = session.execute(count_stmt).scalar() or 0
            stmt = stmt.limit(limit).offset(offset)
            events = list(session.execute(stmt).scalars().all())

            # Map folder names
            folder_map = {f.id: f.name for f in session.execute(select(ManagedFolder)).scalars().all()}

            results: List[MonitoringEventResponse] = []
            for ev in events:
                results.append(
                    MonitoringEventResponse(
                        id=ev.id,
                        managed_folder_id=ev.managed_folder_id,
                        managed_folder_name=folder_map.get(ev.managed_folder_id, "Unknown"),
                        event_type=ev.event_type,
                        relative_path=ev.relative_path,
                        destination_relative_path=ev.destination_relative_path,
                        status=ev.status,
                        occurred_at=ev.occurred_at,
                    )
                )
            return results, total
        finally:
            if should_close:
                session.close()

    def get_activity_chart(
        self, time_range: str = "last_24h", db: Optional[Session] = None
    ) -> ActivityChartResponse:
        """Returns time-bucketed event counts for the stacked bar chart."""
        session, should_close = self._resolve_session(db)
        try:
            now = datetime.now(timezone.utc)
            buckets_count = 12
            if time_range == "last_hour":
                delta = timedelta(minutes=5)
                start_time = now - timedelta(hours=1)
                buckets_count = 12
                format_label = lambda dt: dt.strftime("%H:%M")
            elif time_range == "last_7d":
                delta = timedelta(days=1)
                start_time = now - timedelta(days=7)
                buckets_count = 7
                format_label = lambda dt: dt.strftime("%a %d")
            elif time_range == "last_30d":
                delta = timedelta(days=3)
                start_time = now - timedelta(days=30)
                buckets_count = 10
                format_label = lambda dt: dt.strftime("%b %d")
            else:  # last_24h
                delta = timedelta(hours=2)
                start_time = now - timedelta(hours=24)
                buckets_count = 12
                format_label = lambda dt: dt.strftime("%H:00")

            points: List[ActivityChartPoint] = []
            current = start_time

            for _ in range(buckets_count):
                next_t = current + delta
                c_iso = current.isoformat()
                n_iso = next_t.isoformat()

                c_count = (
                    session.execute(
                        select(func.count(MonitoringEvent.id)).where(
                            MonitoringEvent.event_type == "created",
                            MonitoringEvent.occurred_at >= c_iso,
                            MonitoringEvent.occurred_at < n_iso,
                        )
                    ).scalar()
                    or 0
                )

                m_count = (
                    session.execute(
                        select(func.count(MonitoringEvent.id)).where(
                            MonitoringEvent.event_type == "modified",
                            MonitoringEvent.occurred_at >= c_iso,
                            MonitoringEvent.occurred_at < n_iso,
                        )
                    ).scalar()
                    or 0
                )

                d_count = (
                    session.execute(
                        select(func.count(MonitoringEvent.id)).where(
                            MonitoringEvent.event_type == "deleted",
                            MonitoringEvent.occurred_at >= c_iso,
                            MonitoringEvent.occurred_at < n_iso,
                        )
                    ).scalar()
                    or 0
                )

                points.append(
                    ActivityChartPoint(
                        timestamp=format_label(current),
                        created=c_count,
                        modified=m_count,
                        deleted=d_count,
                    )
                )
                current = next_t

            return ActivityChartResponse(time_range=time_range, data_points=points)
        finally:
            if should_close:
                session.close()

    def get_distribution(self, db: Optional[Session] = None) -> DistributionResponse:
        """Returns event type breakdown and percentages for the donut chart."""
        session, should_close = self._resolve_session(db)
        try:
            one_day_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            stmt = (
                select(MonitoringEvent.event_type, func.count(MonitoringEvent.id))
                .where(MonitoringEvent.occurred_at >= one_day_ago)
                .group_by(MonitoringEvent.event_type)
            )
            rows = session.execute(stmt).all()
            counts = {row[0]: row[1] for row in rows}
            total = sum(counts.values())

            items: List[DistributionItem] = []
            for ev_type in ("created", "modified", "deleted", "moved"):
                cnt = counts.get(ev_type, 0)
                pct = round((cnt / total * 100), 1) if total > 0 else 0.0
                items.append(DistributionItem(event_type=ev_type, count=cnt, percentage=pct))

            return DistributionResponse(total_events=total, distribution=items)
        finally:
            if should_close:
                session.close()


def get_monitoring_service() -> MonitoringManagerService:
    return MonitoringManagerService()
