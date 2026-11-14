from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.deps import get_managed_folder_service
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
from backend.app.services.managed_folder import (
    ManagedFolderException,
    ManagedFolderService,
)

router = APIRouter()


@router.post(
    "/register",
    response_model=ManagedFolderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new Managed Folder",
)
def register_managed_folder(
    payload: ManagedFolderCreate,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    """Registers a folder explicitly selected by the user.
    Validates canonical paths, rejects protected Windows and duplicate paths.
    Does NOT trigger an automatic recursive scan.
    """
    try:
        folder = service.register_folder(payload)
        return service.build_folder_response(folder)
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/register-multiple",
    response_model=List[ManagedFolderResponse],
    summary="Register multiple Managed Folders in batch",
)
def register_multiple_folders(
    paths: List[str],
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> List[ManagedFolderResponse]:
    results = []
    errors = []
    for p in paths:
        try:
            name = p.replace("\\", "/").rstrip("/").split("/")[-1] or "Managed Folder"
            folder = service.register_folder(ManagedFolderCreate(name=name, root_path=p))
            results.append(service.build_folder_response(folder))
        except Exception as e:
            errors.append(f"{p}: {str(e)}")

    if not results and errors:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="; ".join(errors))

    return results


@router.get(
    "/summary",
    response_model=FolderSummaryCards,
    summary="Get summary metrics across all Managed Folders",
)
def get_folder_summary_cards(
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderSummaryCards:
    return service.get_summary_cards()


@router.get(
    "",
    response_model=List[ManagedFolderResponse],
    summary="List all registered Managed Folders",
)
def list_managed_folders(
    only_enabled: bool = Query(default=False, description="Filter for only active folders"),
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> List[ManagedFolderResponse]:
    folders = service.list_folders(only_enabled=only_enabled)
    return [service.build_folder_response(f) for f in folders]


@router.get(
    "/{folder_id}",
    response_model=ManagedFolderResponse,
    summary="Get details of a specific Managed Folder",
)
def get_managed_folder(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    folder = service.get_folder(folder_id)
    if not folder:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Managed Folder '{folder_id}' not found",
        )
    return service.build_folder_response(folder)


@router.patch(
    "/{folder_id}",
    response_model=ManagedFolderResponse,
    summary="Update Managed Folder configuration",
)
def update_managed_folder(
    folder_id: str,
    payload: ManagedFolderUpdate,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    try:
        folder = service.update_folder(folder_id, payload)
        return service.build_folder_response(folder)
    except ManagedFolderException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post(
    "/{folder_id}/enable",
    response_model=ManagedFolderResponse,
    summary="Enable a disabled Managed Folder",
)
def enable_managed_folder(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    try:
        folder = service.set_folder_enabled(folder_id, True)
        return service.build_folder_response(folder)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{folder_id}/disable",
    response_model=ManagedFolderResponse,
    summary="Disable an active Managed Folder",
)
def disable_managed_folder(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    try:
        folder = service.set_folder_enabled(folder_id, False)
        return service.build_folder_response(folder)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete(
    "/{folder_id}",
    response_model=ManagedFolderResponse,
    summary="Unregister a Managed Folder without deleting files",
)
def unregister_managed_folder(
    folder_id: str,
    permanent: bool = Query(default=False, description="Whether to permanently remove database record"),
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> ManagedFolderResponse:
    try:
        if permanent:
            folder = service.get_folder(folder_id)
            if not folder:
                raise ManagedFolderException(f"Managed Folder with ID {folder_id} not found")
            resp = service.build_folder_response(folder)
            service.delete_folder(folder_id)
            return resp
        folder = service.unregister_folder(folder_id)
        return service.build_folder_response(folder)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# Capabilities
# ==========================================
@router.get(
    "/{folder_id}/capabilities",
    response_model=FolderCapabilities,
    summary="Get feature capabilities permitted for a Managed Folder",
)
def get_folder_capabilities(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderCapabilities:
    return service.get_folder_capabilities(folder_id)


@router.put(
    "/{folder_id}/capabilities",
    response_model=FolderCapabilities,
    summary="Update feature capabilities for a Managed Folder",
)
def update_folder_capabilities(
    folder_id: str,
    payload: FolderCapabilities,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderCapabilities:
    try:
        return service.update_folder_capabilities(folder_id, payload)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ==========================================
# Structured Exclusions
# ==========================================
@router.get(
    "/{folder_id}/exclusions",
    response_model=List[FolderExclusionItem],
    summary="Get structured exclusions for a Managed Folder",
)
def get_folder_exclusions(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> List[FolderExclusionItem]:
    return service.get_folder_exclusions(folder_id)


@router.post(
    "/{folder_id}/exclusions",
    response_model=FolderExclusionItem,
    status_code=status.HTTP_201_CREATED,
    summary="Add an exclusion rule for a Managed Folder",
)
def add_folder_exclusion(
    folder_id: str,
    payload: FolderExclusionCreate,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderExclusionItem:
    try:
        return service.add_folder_exclusion(folder_id, payload)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/{folder_id}/exclusions/{exclusion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a structured exclusion rule",
)
def delete_folder_exclusion(
    folder_id: str,
    exclusion_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
):
    removed = service.delete_folder_exclusion(folder_id, exclusion_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exclusion not found")


# ==========================================
# Health & Usage
# ==========================================
@router.get(
    "/{folder_id}/health",
    response_model=FolderHealthCheck,
    summary="Run health and permission checks on a Managed Folder",
)
def get_folder_health(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderHealthCheck:
    try:
        return service.check_folder_health(folder_id)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/{folder_id}/usage",
    response_model=FolderUsageStats,
    summary="Get latest storage and file counts for a Managed Folder",
)
def get_folder_usage(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> FolderUsageStats:
    try:
        return service.get_folder_usage(folder_id)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post(
    "/{folder_id}/reconcile",
    summary="Reconcile database records against live filesystem without modifying user files",
)
def reconcile_managed_folder(
    folder_id: str,
    service: ManagedFolderService = Depends(get_managed_folder_service),
) -> Dict[str, Any]:
    try:
        return service.reconcile_folder(folder_id)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
