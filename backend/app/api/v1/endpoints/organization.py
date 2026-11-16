from typing import Dict
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_background_job_service, get_db, get_organization_service
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.schemas.background_job import BackgroundJobResponse, BackgroundJobType
from backend.app.schemas.organization import (
    OrganizationPlanRequest,
    OrganizationPlanResult,
    ProtectedFoldersDetectResponse,
    ProtectedFoldersListResponse,
    ProtectedSubfolderCreate,
    ProtectedSubfolderItem,
    ProtectedSubfolderToggle,
)
from backend.app.services.background_job_service import BackgroundJobService
from backend.app.services.organization import OrganizationService, run_organization_plan_background

router = APIRouter()


@router.post("/plan", response_model=OrganizationPlanResult, status_code=status.HTTP_201_CREATED)
def generate_organization_plan(
    payload: OrganizationPlanRequest,
    service: OrganizationService = Depends(get_organization_service),
) -> OrganizationPlanResult:
    """Analyzes a Managed Folder and generates an organization Change Plan with conflict checks.
    Strictly read-only; does not mutate files on disk."""
    try:
        return service.generate_plan(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate organization plan: {str(e)}",
        )


@router.post(
    "/plan-async",
    response_model=BackgroundJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_organization_plan_async(
    payload: OrganizationPlanRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    job_service: BackgroundJobService = Depends(get_background_job_service),
) -> BackgroundJobResponse:
    """Dispatches a non-blocking background organization plan generation job."""
    folder = db.get(ManagedFolder, payload.managed_folder_id)
    folder_name = folder.name if folder else payload.managed_folder_id

    job = job_service.create_job(
        job_type=BackgroundJobType.ORGANIZATION,
        title=f"Organisasi Folder: {folder_name}",
        managed_folder_id=payload.managed_folder_id,
        managed_folder_name=folder_name,
        current_step="Memulai analisis organisasi folder di latar belakang...",
        db=db,
    )

    background_tasks.add_task(
        run_organization_plan_background,
        job_id=job.id,
        payload_data=payload.model_dump(),
    )

    return BackgroundJobResponse.model_validate(job)



@router.get(
    "/protected-folders/{folder_id}",
    response_model=ProtectedFoldersListResponse,
    summary="List protected project/tool subfolders for a Managed Folder",
)
def list_protected_folders(
    folder_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> ProtectedFoldersListResponse:
    try:
        return service.list_protected_folders(folder_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/protected-folders/{folder_id}/detect",
    response_model=ProtectedFoldersDetectResponse,
    summary="Smart-detect and flag project or DLL/binary tool subfolders",
)
async def detect_protected_folders(
    folder_id: str,
    use_ai: bool = Query(default=True, description="Allow 9Router AI classification when available"),
    service: OrganizationService = Depends(get_organization_service),
) -> ProtectedFoldersDetectResponse:
    try:
        return await service.detect_protected_folders(folder_id, use_ai=use_ai)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/protected-folders/{folder_id}",
    response_model=ProtectedSubfolderItem,
    status_code=status.HTTP_201_CREATED,
    summary="Manually flag a subfolder to prevent internal files from being organized",
)
def add_protected_folder(
    folder_id: str,
    payload: ProtectedSubfolderCreate,
    service: OrganizationService = Depends(get_organization_service),
) -> ProtectedSubfolderItem:
    try:
        return service.add_protected_folder(folder_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/protected-folders/{folder_id}/{item_id}",
    response_model=ProtectedSubfolderItem,
    summary="Enable or pause protection on a flagged subfolder",
)
def toggle_protected_folder(
    folder_id: str,
    item_id: str,
    payload: ProtectedSubfolderToggle,
    service: OrganizationService = Depends(get_organization_service),
) -> ProtectedSubfolderItem:
    try:
        return service.toggle_protected_folder(folder_id, item_id, payload.is_protected)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/protected-folders/{folder_id}/{item_id}",
    response_model=Dict[str, bool],
    summary="Remove a protected subfolder flag",
)
def delete_protected_folder(
    folder_id: str,
    item_id: str,
    service: OrganizationService = Depends(get_organization_service),
) -> Dict[str, bool]:
    deleted = service.delete_protected_folder(folder_id, item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Protected folder entry not found")
    return {"deleted": True}
