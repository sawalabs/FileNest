from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from backend.app.api.deps import get_smart_rename_service
from backend.app.schemas.smart_rename import (
    BatchOCRJobStatus,
    ItemOCRAnalyzeRequest,
    ItemOCRAnalyzeResponse,
    QuickOCRRenameRequest,
    QuickOCRRenameResponse,
    SmartRenamePlanRequest,
    SmartRenamePlanResult,
)
from backend.app.services.smart_rename import SmartRenameService

router = APIRouter()


@router.post("/plan", response_model=SmartRenamePlanResult, status_code=status.HTTP_201_CREATED)
async def generate_smart_rename_plan(
    payload: SmartRenamePlanRequest,
    background_tasks: BackgroundTasks,
    service: SmartRenameService = Depends(get_smart_rename_service),
) -> SmartRenamePlanResult:
    """Analyzes files and generates a smart rename Change Plan with collision detection.
    Strictly read-only; does not mutate files on disk."""
    try:
        result = await service.generate_plan(payload)
        if payload.run_ocr_background:
            background_tasks.add_task(service.run_batch_ocr_background, result.change_plan_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate smart rename plan: {str(e)}",
        )


@router.post("/items/{item_id}/analyze-ocr", response_model=ItemOCRAnalyzeResponse)
async def analyze_smart_rename_item_ocr(
    item_id: str,
    payload: ItemOCRAnalyzeRequest,
    service: SmartRenameService = Depends(get_smart_rename_service),
) -> ItemOCRAnalyzeResponse:
    """Runs PaddleOCR and AI naming on a single plan item on-demand."""
    try:
        return await service.analyze_item_with_ocr(payload.plan_id, item_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyze item with OCR: {str(e)}",
        )


@router.post("/plans/{plan_id}/batch-ocr", response_model=BatchOCRJobStatus)
async def trigger_batch_ocr_background(
    plan_id: str,
    background_tasks: BackgroundTasks,
    service: SmartRenameService = Depends(get_smart_rename_service),
) -> BatchOCRJobStatus:
    """Initiates non-blocking background OCR processing on all eligible items in the plan."""
    background_tasks.add_task(service.run_batch_ocr_background, plan_id)
    return service.get_batch_ocr_status(plan_id)


@router.get("/plans/{plan_id}/batch-ocr/status", response_model=BatchOCRJobStatus)
def get_batch_ocr_status(
    plan_id: str,
    service: SmartRenameService = Depends(get_smart_rename_service),
) -> BatchOCRJobStatus:
    """Returns the live status and progress of the background OCR batch job."""
    return service.get_batch_ocr_status(plan_id)


@router.post("/quick-ocr-suggest", response_model=QuickOCRRenameResponse)
async def quick_suggest_ocr_rename(
    payload: QuickOCRRenameRequest,
    service: SmartRenameService = Depends(get_smart_rename_service),
) -> QuickOCRRenameResponse:
    """Extracts OCR text from a single file on disk and suggests a descriptive name with AI."""
    try:
        return await service.quick_suggest_ocr_rename(payload.folder_id, payload.relative_path)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal menyarankan nama OCR + AI: {str(e)}",
        )

