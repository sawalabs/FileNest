from fastapi import APIRouter, Depends, HTTPException, status

from backend.app.api.deps import get_ocr_service
from backend.app.schemas.ocr import (
    OCRExtractRequest,
    OCRExtractResponse,
    OCRStatusResponse,
)
from backend.app.services.managed_folder import ManagedFolderException
from backend.app.services.ocr_service import PaddleOCRService

router = APIRouter()


@router.get(
    "/status",
    response_model=OCRStatusResponse,
    summary="Get status and supported formats of the PaddleOCR engine",
)
def get_ocr_status(
    service: PaddleOCRService = Depends(get_ocr_service),
) -> OCRStatusResponse:
    """Returns availability and capabilities of the on-device PaddleOCR engine."""
    return service.check_status()


@router.post(
    "/extract",
    response_model=OCRExtractResponse,
    summary="Extract text from an image or PDF document using PaddleOCR PP-OCRv4",
)
def extract_text(
    request: OCRExtractRequest,
    service: PaddleOCRService = Depends(get_ocr_service),
) -> OCRExtractResponse:
    """Extracts optical text from an image or document strictly within a registered Managed Folder."""
    try:
        return service.extract_text(request)
    except ManagedFolderException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OCR text extraction failed: {str(e)}",
        )
