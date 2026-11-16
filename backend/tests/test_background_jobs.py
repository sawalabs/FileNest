import time
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.app.db.models.background_job import BackgroundJob
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.main import app
from backend.app.schemas.background_job import BackgroundJobType
from backend.app.services.background_job_service import get_background_job_service


def test_background_job_lifecycle(db_session: Session) -> None:
    service = get_background_job_service()

    # 1. Create job
    job = service.create_job(
        job_type=BackgroundJobType.STORAGE_ANALYSIS,
        title="Test Storage Scan",
        current_step="Inisialisasi...",
        db=db_session,
    )
    assert job.id is not None
    assert job.status == "queued"
    assert job.progress == 0

    # 2. Start job
    started = service.start_job(job.id, db=db_session)
    assert started is not None
    assert started.status == "running"
    assert started.started_at is not None

    # 3. Update progress
    updated = service.update_progress(
        job.id,
        progress=45,
        current_step="Scanning files...",
        items_processed=45,
        items_total=100,
        db=db_session,
    )
    assert updated is not None
    assert updated.progress == 45
    assert updated.current_step == "Scanning files..."
    assert updated.items_processed == 45
    assert updated.items_total == 100

    # 4. Check active jobs
    active = service.get_active_jobs(db=db_session)
    assert any(j.id == job.id for j in active)

    # 5. Complete job
    completed = service.complete_job(job.id, result_payload={"files_found": 100}, db=db_session)
    assert completed is not None
    assert completed.status == "completed"
    assert completed.progress == 100
    assert completed.finished_at is not None

    # Verify not in active jobs anymore
    active_after = service.get_active_jobs(db=db_session)
    assert not any(j.id == job.id for j in active_after)


def test_background_job_cancellation(db_session: Session) -> None:
    service = get_background_job_service()

    job = service.create_job(
        job_type=BackgroundJobType.SMART_RENAME,
        title="Test Cancellation",
        db=db_session,
    )
    service.start_job(job.id, db=db_session)
    assert not service.is_cancelled(job.id, db=db_session)

    # Request cancellation
    res = service.request_cancellation(job.id, db=db_session)
    assert res is True
    assert service.is_cancelled(job.id, db=db_session)

    job_db = service.get_job(job.id, db=db_session)
    assert job_db is not None
    assert job_db.status == "cancelled"
    assert job_db.cancellation_requested is True


def test_job_api_endpoints(db_session: Session) -> None:
    from backend.app.core.security import get_or_create_app_token
    token = get_or_create_app_token()
    client = TestClient(app, headers={"X-App-Token": token})
    service = get_background_job_service()

    job = service.create_job(
        job_type=BackgroundJobType.BATCH_OCR,
        title="API Test Job",
        db=db_session,
    )

    # GET /api/v1/jobs/{job_id}
    res = client.get(f"/api/v1/jobs/{job.id}")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == job.id
    assert data["title"] == "API Test Job"
    assert data["status"] == "queued"

    # GET /api/v1/jobs/active
    res_active = client.get("/api/v1/jobs/active")
    assert res_active.status_code == 200
    active_ids = [j["id"] for j in res_active.json()]
    assert job.id in active_ids

    # POST /api/v1/jobs/{job_id}/cancel
    res_cancel = client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"

    # DELETE /api/v1/jobs/{job_id}
    res_dismiss = client.delete(f"/api/v1/jobs/{job.id}")
    assert res_dismiss.status_code == 204
