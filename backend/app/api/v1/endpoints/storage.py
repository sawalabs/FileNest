from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_storage_service, get_transaction_service
from backend.app.schemas.storage import (
    StorageAnalysisRequest,
    StorageAnalysisResult,
    StorageCleanupPlanRequest,
    StorageCleanupPlanResponse,
)
from backend.app.services.storage import StorageAnalyzerService, StorageException
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
    """Executes a deep read-only storage analysis on the selected Managed Folder or all folders."""
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
