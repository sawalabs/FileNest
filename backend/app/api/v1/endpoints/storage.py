from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_background_job_service, get_db, get_storage_service, get_transaction_service
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.schemas.background_job import BackgroundJobResponse, BackgroundJobType
from backend.app.schemas.storage import (
    StorageAnalysisRequest,
    StorageAnalysisResult,
    StorageCleanupPlanRequest,
    StorageCleanupPlanResponse,
)
from backend.app.services.background_job_service import BackgroundJobService
from backend.app.services.storage import (
    StorageAnalyzerService,
    StorageException,
    run_storage_analysis_background,
)
from backend.app.services.transaction import TransactionException, TransactionManagerService

router = APIRouter()


@router.get("/analysis", response_model=Optional[StorageAnalysisResult])
def get_latest_storage_analysis(
    folder_id: Optional[str] = Query(None, description="Optional Managed Folder ID"),
    service: StorageAnalyzerService = Depends(get_storage_service),
) -> Optional[StorageAnalysisResult]:
    """Retrieves the latest stored storage analysis results from the database."""
    try:
        return service.get_latest_analysis(folder_id=folder_id)
    except StorageException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/analyze", response_model=StorageAnalysisResult)
def trigger_storage_analysis(
    payload: StorageAnalysisRequest,
    service: StorageAnalyzerService = Depends(get_storage_service),
) -> StorageAnalysisResult:
    """Executes a deep read-only storage analysis on the selected Managed Folder or all folders (blocking)."""
    try:
        if payload.managed_folder_id:
            return service.analyze_folder(
                folder_id=payload.managed_folder_id,
                large_file_threshold_bytes=payload.large_file_threshold_bytes,
                calculate_hashes=payload.calculate_hashes,
            )
        else:
            return service.analyze_all_folders(
                large_file_threshold_bytes=payload.large_file_threshold_bytes,
                calculate_hashes=payload.calculate_hashes,
            )
    except StorageException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/analyze-async",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_storage_analysis_async(
    payload: StorageAnalysisRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    job_service: BackgroundJobService = Depends(get_background_job_service),
) -> BackgroundJobResponse:
    """Dispatches a non-blocking background storage analysis job returning 202 Accepted with job metadata."""
    folder_name = "Semua Folder Terkelola"
    if payload.managed_folder_id:
        folder = db.get(ManagedFolder, payload.managed_folder_id)
        if folder:
            folder_name = folder.name

    job = job_service.create_job(
        job_type=BackgroundJobType.STORAGE_ANALYSIS,
        title=f"Analisis Penyimpanan: {folder_name}",
        managed_folder_id=payload.managed_folder_id,
        managed_folder_name=folder_name,
        current_step="Menyiapkan analisis penyimpanan latar belakang...",
        db=db,
    )

    background_tasks.add_task(
        run_storage_analysis_background,
        job_id=job.id,
        folder_id=payload.managed_folder_id,
        large_file_threshold_bytes=payload.large_file_threshold_bytes,
        calculate_hashes=payload.calculate_hashes,
    )

    return BackgroundJobResponse.model_validate(job)



@router.post("/cleanup-plan", response_model=StorageCleanupPlanResponse)
def create_storage_cleanup_plan(
    payload: StorageCleanupPlanRequest,
    service: StorageAnalyzerService = Depends(get_storage_service),
    transaction_service: TransactionManagerService = Depends(get_transaction_service),
) -> StorageCleanupPlanResponse:
    """Queues selected duplicate, large file, or empty folder cleanup items into Review Changes."""
    try:
        return service.create_cleanup_plan(payload, transaction_service)
    except (StorageException, TransactionException) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
