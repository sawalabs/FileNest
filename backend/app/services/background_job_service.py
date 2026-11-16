import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import generate_uuid, utc_now_iso
from backend.app.db.models.background_job import BackgroundJob
from backend.app.db.session import SessionLocal
from backend.app.schemas.background_job import (
    BackgroundJobCreate,
    BackgroundJobResponse,
    BackgroundJobStatus,
    BackgroundJobType,
    BackgroundJobUpdate,
)


class BackgroundJobService:
    """Unified service for managing persistent long-running background jobs, progress updates,
    and thread-safe cancellation signaling."""

    def __init__(self) -> None:
        self._cancellation_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _get_db(self, db: Optional[Session] = None) -> Session:
        if db is not None:
            return db
        from backend.app.db import session as session_module
        return session_module.SessionLocal()

    def create_job(
        self,
        job_type: Any,
        title: str,
        managed_folder_id: Optional[str] = None,
        managed_folder_name: Optional[str] = None,
        items_total: int = 0,
        current_step: str = "Menyiapkan pekerjaan...",
        db: Optional[Session] = None,
    ) -> BackgroundJob:
        """Creates and persists a new background job in 'queued' status."""
        own_session = db is None
        session = self._get_db(db)
        try:
            now = utc_now_iso()
            type_val = job_type.value if hasattr(job_type, "value") else str(job_type)
            job = BackgroundJob(
                id=generate_uuid(),
                job_type=type_val,
                title=title,
                status="queued",
                progress=0,
                current_step=current_step,
                items_total=items_total,
                items_processed=0,
                managed_folder_id=managed_folder_id,
                managed_folder_name=managed_folder_name,
                cancellation_requested=False,
                created_at=now,
                updated_at=now,
            )
            session.add(job)
            session.commit()
            session.refresh(job)

            with self._lock:
                self._cancellation_events[job.id] = threading.Event()

            logger.info("Created background job %s ('%s', type=%s)", job.id, job.title, job.job_type)
            return job
        finally:
            if own_session:
                session.close()

    def start_job(self, job_id: str, db: Optional[Session] = None) -> Optional[BackgroundJob]:
        """Transitions job status to 'running' and sets started_at."""
        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return None
            job.status = "running"
            job.started_at = utc_now_iso()
            job.updated_at = utc_now_iso()
            session.commit()
            session.refresh(job)
            return job
        finally:
            if own_session:
                session.close()

    def update_progress(
        self,
        job_id: str,
        progress: Optional[int] = None,
        current_step: Optional[str] = None,
        items_processed: Optional[int] = None,
        items_total: Optional[int] = None,
        db: Optional[Session] = None,
    ) -> Optional[BackgroundJob]:
        """Updates live execution progress metrics and current step message."""
        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return None

            if progress is not None:
                job.progress = max(0, min(100, int(progress)))
            if current_step is not None:
                job.current_step = current_step
            if items_processed is not None:
                job.items_processed = items_processed
            if items_total is not None:
                job.items_total = items_total

            job.updated_at = utc_now_iso()
            session.commit()
            session.refresh(job)
            return job
        finally:
            if own_session:
                session.close()

    def complete_job(
        self,
        job_id: str,
        result_payload: Optional[Any] = None,
        db: Optional[Session] = None,
    ) -> Optional[BackgroundJob]:
        """Marks job as completed, records finish timestamp and optional result payload."""
        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return None

            job.status = "completed"
            job.progress = 100
            job.finished_at = utc_now_iso()
            job.updated_at = utc_now_iso()

            if result_payload is not None:
                if isinstance(result_payload, str):
                    job.result_payload = result_payload
                else:
                    try:
                        job.result_payload = json.dumps(result_payload)
                    except Exception:
                        job.result_payload = str(result_payload)

            session.commit()
            session.refresh(job)

            with self._lock:
                self._cancellation_events.pop(job_id, None)

            logger.info("Background job %s completed successfully", job_id)
            return job
        finally:
            if own_session:
                session.close()

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        db: Optional[Session] = None,
    ) -> Optional[BackgroundJob]:
        """Marks job as failed with specific diagnostic message."""
        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return None

            job.status = "failed"
            job.error_message = error_message
            job.finished_at = utc_now_iso()
            job.updated_at = utc_now_iso()
            session.commit()
            session.refresh(job)

            with self._lock:
                self._cancellation_events.pop(job_id, None)

            logger.warning("Background job %s failed: %s", job_id, error_message)
            return job
        finally:
            if own_session:
                session.close()

    def request_cancellation(self, job_id: str, db: Optional[Session] = None) -> bool:
        """Signals cancellation to running job and sets status to cancelled in DB."""
        with self._lock:
            event = self._cancellation_events.get(job_id)
            if event:
                event.set()

        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return False

            job.cancellation_requested = True
            job.status = "cancelled"
            job.current_step = "Dibatalkan oleh pengguna"
            job.finished_at = utc_now_iso()
            job.updated_at = utc_now_iso()
            session.commit()

            with self._lock:
                self._cancellation_events.pop(job_id, None)

            logger.info("Background job %s cancellation processed", job_id)
            return True
        finally:
            if own_session:
                session.close()

    def is_cancelled(self, job_id: str, db: Optional[Session] = None) -> bool:
        """Checks whether cancellation has been requested for this job."""
        with self._lock:
            event = self._cancellation_events.get(job_id)
            if event and event.is_set():
                return True

        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            return bool(job and (job.cancellation_requested or job.status == "cancelled"))
        finally:
            if own_session:
                session.close()

    def get_job(self, job_id: str, db: Optional[Session] = None) -> Optional[BackgroundJob]:
        own_session = db is None
        session = self._get_db(db)
        try:
            return session.get(BackgroundJob, job_id)
        finally:
            if own_session:
                session.close()

    def get_active_jobs(self, db: Optional[Session] = None) -> List[BackgroundJob]:
        own_session = db is None
        session = self._get_db(db)
        try:
            stmt = (
                select(BackgroundJob)
                .where(BackgroundJob.status.in_(["queued", "running"]))
                .order_by(desc(BackgroundJob.created_at))
            )
            return list(session.scalars(stmt).all())
        finally:
            if own_session:
                session.close()

    def get_recent_jobs(self, limit: int = 20, db: Optional[Session] = None) -> List[BackgroundJob]:
        own_session = db is None
        session = self._get_db(db)
        try:
            stmt = select(BackgroundJob).order_by(desc(BackgroundJob.created_at)).limit(limit)
            return list(session.scalars(stmt).all())
        finally:
            if own_session:
                session.close()

    def dismiss_job(self, job_id: str, db: Optional[Session] = None) -> bool:
        """Deletes a finished, cancelled, or failed job record."""
        own_session = db is None
        session = self._get_db(db)
        try:
            job = session.get(BackgroundJob, job_id)
            if not job:
                return False
            session.delete(job)
            session.commit()
            with self._lock:
                self._cancellation_events.pop(job_id, None)
            return True
        finally:
            if own_session:
                session.close()


_global_job_service: Optional[BackgroundJobService] = None
_job_service_lock = threading.Lock()


def get_background_job_service() -> BackgroundJobService:
    global _global_job_service
    if _global_job_service is None:
        with _job_service_lock:
            if _global_job_service is None:
                _global_job_service = BackgroundJobService()
    return _global_job_service
