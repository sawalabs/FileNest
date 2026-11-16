from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db
from backend.app.schemas.background_job import (
    BackgroundJobCancelResponse,
    BackgroundJobListResponse,
    BackgroundJobResponse,
)
from backend.app.services.background_job_service import (
    BackgroundJobService,
    get_background_job_service,
)

router = APIRouter()


@router.get("/active", response_model=List[BackgroundJobResponse])
def get_active_jobs(
    service: BackgroundJobService = Depends(get_background_job_service),
    db: Session = Depends(get_db),
) -> List[BackgroundJobResponse]:
    """Retrieves all currently queued or running background jobs."""
    jobs = service.get_active_jobs(db=db)
    return [BackgroundJobResponse.model_validate(j) for j in jobs]


@router.get("/recent", response_model=List[BackgroundJobResponse])
def get_recent_jobs(
    limit: int = Query(20, ge=1, le=100),
    service: BackgroundJobService = Depends(get_background_job_service),
    db: Session = Depends(get_db),
) -> List[BackgroundJobResponse]:
    """Retrieves recent background jobs including completed, failed, and cancelled."""
    jobs = service.get_recent_jobs(limit=limit, db=db)
    return [BackgroundJobResponse.model_validate(j) for j in jobs]


@router.get("/{job_id}", response_model=BackgroundJobResponse)
def get_job_by_id(
    job_id: str,
    service: BackgroundJobService = Depends(get_background_job_service),
    db: Session = Depends(get_db),
) -> BackgroundJobResponse:
    """Retrieves detailed status and optional result payload for a specific job."""
    job = service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background job '{job_id}' not found.",
        )
    return BackgroundJobResponse.model_validate(job)


@router.post("/{job_id}/cancel", response_model=BackgroundJobCancelResponse)
def cancel_job(
    job_id: str,
    service: BackgroundJobService = Depends(get_background_job_service),
    db: Session = Depends(get_db),
) -> BackgroundJobCancelResponse:
    """Requests safe cancellation of a running background job."""
    job = service.get_job(job_id=job_id, db=db)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background job '{job_id}' not found.",
        )
    if job.status in ["completed", "failed", "cancelled"]:
        return BackgroundJobCancelResponse(
            id=job_id,
            status=job.status,
            message=f"Pekerjaan sudah dalam status '{job.status}'.",
        )

    success = service.request_cancellation(job_id=job_id, db=db)
    return BackgroundJobCancelResponse(
        id=job_id,
        status="cancelled",
        message="Permintaan pembatalan berhasil diproses.",
    )


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def dismiss_job(
    job_id: str,
    service: BackgroundJobService = Depends(get_background_job_service),
    db: Session = Depends(get_db),
) -> None:
    """Dismisses or removes a finished/cancelled/failed background job from the registry."""
    success = service.dismiss_job(job_id=job_id, db=db)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Background job '{job_id}' not found.",
        )
