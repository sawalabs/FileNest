from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_organization_service
from backend.app.schemas.organization import (
    OrganizationPlanRequest,
    OrganizationPlanResult,
    ProtectedFoldersDetectResponse,
    ProtectedFoldersListResponse,
    ProtectedSubfolderCreate,
    ProtectedSubfolderItem,
    ProtectedSubfolderToggle,
)
from backend.app.services.organization import OrganizationService

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
