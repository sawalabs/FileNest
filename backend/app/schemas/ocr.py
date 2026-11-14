from typing import List, Optional
from pydantic import BaseModel, Field


class OCRExtractRequest(BaseModel):
    folder_id: str = Field(description="ID folder terkelola tempat file berada")
    relative_path: str = Field(description="Path relatif file di dalam folder terkelola")
    max_pages: Optional[int] = Field(default=10, ge=1, le=50, description="Batas maksimum halaman untuk file PDF")
    engine: Optional[str] = Field(
        default="auto",
        description="OCR Engine to use: 'auto' (Windows Native OCR with PaddleOCR fallback), 'windows_ocr', or 'paddleocr'",
    )


class OCRLineItem(BaseModel):
    text: str
    confidence: float = Field(ge=0.0, le=1.0)
    box: Optional[List[List[float]]] = None


class OCRPageResult(BaseModel):
    page_number: int
    text: str
    lines: List[OCRLineItem] = []
    confidence: float = Field(ge=0.0, le=1.0)


class OCRExtractResponse(BaseModel):
    success: bool
    filename: str
    folder_id: str
    relative_path: str
    full_text: str = ""
    word_count: int = 0
    confidence: float = 0.0
    pages: List[OCRPageResult] = []
    duration_ms: float = 0.0
    engine: str = "PaddleOCR PP-OCRv4"
    error: Optional[str] = None


class OCRStatusResponse(BaseModel):
    available: bool = True
    engine: str = "Windows Native OCR + PaddleOCR PP-OCRv4"
    available_engines: List[str] = [
        "Windows Native OCR (Ultra-Fast ~20ms)",
        "PaddleOCR PP-OCRv4 (Offline ML)",
    ]
    supported_formats: List[str] = [
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/bmp",
        "image/tiff",
        "application/pdf",
    ]
