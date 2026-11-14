from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_specialist_service
from backend.app.schemas.specialists import (
    DiskAnalystRequest,
    DiskAnalystResult,
    DuplicateAnalystRequest,
    DuplicateAnalystResult,
    FolderArchitectRequest,
    FolderArchitectResult,
    RenameSpecialistRequest,
    RenameSpecialistResult,
    ReviewAgentRequest,
    ReviewAgentResult,
    SpecialistRunRequest,
)
from backend.app.services.specialists import SpecialistException, SpecialistService

router = APIRouter()


@router.post(
    "/disk-analyst",
    response_model=DiskAnalystResult,
    summary="Run Disk Analyst Specialist",
    description="Analyzes storage consumption, identifies waste sources, and produces actionable health recommendations.",
)
async def run_disk_analyst(
    payload: DiskAnalystRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> DiskAnalystResult:
    try:
        return await service.run_disk_analyst(payload)
    except SpecialistException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/folder-architect",
    response_model=FolderArchitectResult,
    summary="Run Folder Architect Specialist",
    description="Proposes structured folder hierarchies and drafts an organization change plan.",
)
async def run_folder_architect(
    payload: FolderArchitectRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> FolderArchitectResult:
    try:
        return await service.run_folder_architect(payload)
    except SpecialistException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/rename-specialist",
    response_model=RenameSpecialistResult,
    summary="Run Rename Specialist",
    description="Generates semantic, standardized naming conventions and drafts a smart rename plan.",
)
async def run_rename_specialist(
    payload: RenameSpecialistRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> RenameSpecialistResult:
    try:
        return await service.run_rename_specialist(payload)
    except SpecialistException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/duplicate-analyst",
    response_model=DuplicateAnalystResult,
    summary="Run Duplicate Analyst Specialist",
    description="Clusters duplicate candidates, decides optimal retention, and optionally drafts a cleanup plan.",
)
async def run_duplicate_analyst(
    payload: DuplicateAnalystRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> DuplicateAnalystResult:
    try:
        return await service.run_duplicate_analyst(payload)
    except SpecialistException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/review-agent",
    response_model=ReviewAgentResult,
    summary="Run Review Agent Specialist",
    description="Performs pre-execution safety audit on proposed Change Plans to detect collisions, stale files, and risks.",
)
async def run_review_agent(
    payload: ReviewAgentRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> ReviewAgentResult:
    try:
        return await service.run_review_agent(payload)
    except (SpecialistException, Exception) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/run",
    summary="General Specialist Dispatcher",
    description="Dispatches execution to any requested AI analysis specialist.",
)
async def run_specialist_dispatcher(
    payload: SpecialistRunRequest,
    service: SpecialistService = Depends(get_specialist_service),
) -> Dict[str, Any]:
    try:
        return await service.run_specialist(payload)
    except SpecialistException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
