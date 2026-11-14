import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.ocr import (
    OCRExtractRequest,
    OCRExtractResponse,
    OCRLineItem,
    OCRPageResult,
    OCRStatusResponse,
)
from backend.app.services.managed_folder import ManagedFolderException, PathValidator

# Fix paddle static engine runner on CPU Windows to prevent oneDNN PIR NotImplementedError
try:
    import paddlex.inference.models.runners.paddle_static.runner as runner
    orig_resolver = runner.resolve_paddle_static_engine_config

    def _safe_resolve_engine_config(model_name: str, config: Dict[str, Any]):
        resolved = orig_resolver(model_name, config)
        resolved["run_mode"] = "paddle"
        resolved["enable_new_ir"] = False
        return resolved

    runner.resolve_paddle_static_engine_config = _safe_resolve_engine_config
except Exception as e:
    logger.warning("Could not patch paddle static engine runner: %s", e)


class PaddleOCRService:
    """Service for optical character recognition using PaddleOCR PP-OCRv4."""

    _engine = None
    _lock = threading.Lock()

    SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff"}
    SUPPORTED_DOC_EXTS = {".pdf"}
    MAX_SAFE_OCR_IMAGE_PIXELS = 50_000_000  # 50 MP decompression bomb limit
    MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB limit

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    @classmethod
    def get_engine(cls):
        """Lazy loads and caches the PaddleOCR PP-OCRv4 pipeline with fast inference settings."""
        with cls._lock:
            if cls._engine is None:
                from paddleocr import PaddleOCR
                cls._engine = PaddleOCR(
                    ocr_version="PP-OCRv4",
                    lang="en",
                    use_doc_orientation_classify=False,
                    use_doc_unwarping=False,
                    use_textline_orientation=False,
                )
            return cls._engine

    def check_status(self) -> OCRStatusResponse:
        """Returns OCR engine status and supported file formats."""
        return OCRStatusResponse(
            available=True,
            engine="Windows Native OCR + PaddleOCR PP-OCRv4",
            available_engines=[
                "Windows Native OCR (Ultra-Fast ~20ms)",
                "PaddleOCR PP-OCRv4 (Offline ML)",
            ],
            supported_formats=[
                "image/png",
                "image/jpeg",
                "image/webp",
                "image/bmp",
                "image/tiff",
                "application/pdf",
            ],
        )

    def _process_with_windows_ocr(self, pil_img: Image.Image, page_num: int = 1) -> Optional[OCRPageResult]:
        """Runs Windows Native OCR (Windows.Media.Ocr) for ultra-fast (10-30ms) hardware-accelerated text extraction."""
        try:
            import winocr
            import asyncio
            import concurrent.futures

            def _call():
                return winocr.recognize_pil_sync(pil_img)

            res = None
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    fut = pool.submit(_call)
                    res = fut.result(timeout=10)
            else:
                res = _call()

            if not res or not res.get("lines"):
                return None

            lines: List[OCRLineItem] = []
            for line_data in res["lines"]:
                line_txt = line_data.get("text", "").strip()
                if not line_txt:
                    continue

                words = line_data.get("words", [])
                box = None
                if words and "bounding_rect" in words[0]:
                    try:
                        min_x = min(w["bounding_rect"]["x"] for w in words)
                        min_y = min(w["bounding_rect"]["y"] for w in words)
                        max_x = max(w["bounding_rect"]["x"] + w["bounding_rect"]["width"] for w in words)
                        max_y = max(w["bounding_rect"]["y"] + w["bounding_rect"]["height"] for w in words)
                        box = [[min_x, min_y], [max_x, min_y], [max_x, max_y], [min_x, max_y]]
                    except Exception:
                        box = None

                lines.append(OCRLineItem(text=line_txt, confidence=0.98, box=box))

            page_text = "\n".join(l.text for l in lines)
            if not page_text.strip():
                return None

            return OCRPageResult(page_number=page_num, text=page_text, lines=lines, confidence=0.98)
        except Exception as e:
            logger.debug("Windows Native OCR not available or failed: %s", e)
            return None

    def extract_text(self, request: OCRExtractRequest) -> OCRExtractResponse:
        """Extracts text from an image or PDF strictly within a registered Managed Folder."""
        start_time = time.perf_counter()

        folder = self.db.query(ManagedFolder).filter(ManagedFolder.id == request.folder_id).first()
        if not folder:
            raise ManagedFolderException(f"Managed Folder with ID '{request.folder_id}' not found.")

        # Confinement check: path cannot escape folder root, traverse symlinks, or access reserved names
        abs_path = PathValidator.resolve_and_verify_scope(folder, request.relative_path)
        if not abs_path.is_file():
            raise ManagedFolderException(f"Target path does not exist or is not a file: {request.relative_path}")

        file_size = abs_path.stat().st_size
        if file_size > self.MAX_FILE_SIZE_BYTES:
            raise ManagedFolderException(
                f"File size ({file_size / (1024 * 1024):.1f} MB) exceeds maximum OCR limit of 50 MB."
            )

        suffix = abs_path.suffix.lower()
        if suffix not in self.SUPPORTED_IMAGE_EXTS and suffix not in self.SUPPORTED_DOC_EXTS:
            raise ManagedFolderException(
                f"Unsupported file format '{suffix}'. Supported: PNG, JPG, JPEG, WEBP, BMP, TIFF, PDF."
            )

        engine_mode = getattr(request, "engine", "auto") or "auto"
        pages: List[OCRPageResult] = []
        engine_used = "PaddleOCR PP-OCRv4"

        if suffix in self.SUPPORTED_IMAGE_EXTS:
            page_res, engine_used = self._process_image_file(str(abs_path), engine_mode=engine_mode, page_num=1)
            pages.append(page_res)
        elif suffix in self.SUPPORTED_DOC_EXTS:
            pages, engine_used = self._process_pdf_file(str(abs_path), engine_mode=engine_mode, max_pages=request.max_pages or 10)

        duration = round((time.perf_counter() - start_time) * 1000, 2)

        # Assemble full text and compute aggregate statistics
        full_text_parts = [p.text for p in pages if p.text]
        full_text = "\n\n--- Page Break ---\n\n".join(full_text_parts) if len(pages) > 1 else ("\n".join(full_text_parts))
        word_count = len(full_text.split()) if full_text else 0

        avg_confidence = 0.0
        if pages:
            valid_confs = [p.confidence for p in pages if p.confidence > 0]
            avg_confidence = round(sum(valid_confs) / len(valid_confs), 4) if valid_confs else 0.0

        try:
            self.audit_repo.record(
                actor_type="user",
                action="ocr_text_extraction",
                entity_type="file",
                entity_id=request.relative_path,
                details={
                    "folder_id": request.folder_id,
                    "filename": abs_path.name,
                    "engine_used": engine_used,
                    "pages_processed": len(pages),
                    "word_count": word_count,
                    "duration_ms": duration,
                },
            )
        except Exception:
            pass

        return OCRExtractResponse(
            success=True,
            filename=abs_path.name,
            folder_id=request.folder_id,
            relative_path=request.relative_path,
            full_text=full_text,
            word_count=word_count,
            confidence=avg_confidence,
            pages=pages,
            duration_ms=duration,
            engine=engine_used,
        )

    def _process_image_file(
        self,
        file_path: str,
        engine_mode: str = "auto",
        page_num: int = 1,
    ) -> Tuple[OCRPageResult, str]:
        """Processes an image file using Windows Native OCR or PaddleOCR with smart downscaling."""
        import warnings
        prev_max = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = self.MAX_SAFE_OCR_IMAGE_PIXELS
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(file_path) as im:
                    w, h = im.size
                    if w * h > self.MAX_SAFE_OCR_IMAGE_PIXELS:
                        raise ManagedFolderException(
                            f"Image dimensions ({w}x{h}) exceed safe OCR pixel limit ({self.MAX_SAFE_OCR_IMAGE_PIXELS} pixels)."
                        )
                    if im.mode not in ("RGB", "L"):
                        im = im.convert("RGB")
                    if max(w, h) > 1600:
                        scale = 1600 / max(w, h)
                        im = im.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
                    pil_img = im.copy()

            # 1. Try Windows Native OCR first if mode is 'auto' or 'windows_ocr'
            if engine_mode in ("auto", "windows_ocr"):
                win_res = self._process_with_windows_ocr(pil_img, page_num=page_num)
                if win_res and win_res.text.strip():
                    return win_res, "Windows Native OCR (Ultra-Fast)"

            # 2. Fall back to PaddleOCR
            engine = self.get_engine()
            np_img = np.array(pil_img.convert("RGB"))
            results = list(engine.predict(np_img))
            return self._parse_ocr_result(results, page_num), "PaddleOCR PP-OCRv4 (Fast Mode)"
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ManagedFolderException(
                "Gambar ditolak karena resolusi piksel melebihi batas aman (Decompression Bomb protection)."
            )
        except ManagedFolderException:
            raise
        except Exception as e:
            logger.error("Error running OCR on image %s: %s", file_path, e)
            return OCRPageResult(page_number=page_num, text="", lines=[], confidence=0.0), "PaddleOCR PP-OCRv4"
        finally:
            Image.MAX_IMAGE_PIXELS = prev_max

    def _process_pdf_file(
        self,
        file_path: str,
        engine_mode: str = "auto",
        max_pages: int = 10,
    ) -> Tuple[List[OCRPageResult], str]:
        """Renders PDF pages and runs OCR sequentially."""
        import pypdfium2 as pdfium

        pages: List[OCRPageResult] = []
        engine_used = "Windows Native OCR (Ultra-Fast)"
        try:
            pdf = pdfium.PdfDocument(file_path)
            total_pages = len(pdf)
            pages_to_process = min(total_pages, max_pages)

            for idx in range(pages_to_process):
                page = pdf[idx]
                pil_img = page.render(scale=2.0).to_pil().convert("RGB")

                page_res = None
                if engine_mode in ("auto", "windows_ocr"):
                    page_res = self._process_with_windows_ocr(pil_img, page_num=idx + 1)

                if page_res is None or not page_res.text.strip():
                    engine = self.get_engine()
                    np_img = np.array(pil_img)
                    results = list(engine.predict(np_img))
                    page_res = self._parse_ocr_result(results, page_num=idx + 1)
                    engine_used = "PaddleOCR PP-OCRv4 (Fast Mode)"

                pages.append(page_res)
        except Exception as e:
            logger.error("Error reading or rendering PDF %s: %s", file_path, e)
            if not pages:
                pages.append(OCRPageResult(page_number=1, text="", lines=[], confidence=0.0))

        return pages, engine_used

    def _parse_ocr_result(self, raw_results: List[Dict[str, Any]], page_num: int) -> OCRPageResult:
        """Parses output dictionary from PaddleOCR PP-OCRv4 predict call."""
        if not raw_results:
            return OCRPageResult(page_number=page_num, text="", lines=[], confidence=0.0)

        first_res = raw_results[0] if isinstance(raw_results, list) else raw_results
        rec_texts: List[str] = first_res.get("rec_texts", [])
        rec_scores: List[float] = first_res.get("rec_scores", [])
        rec_boxes = first_res.get("rec_boxes")

        lines: List[OCRLineItem] = []
        for i, text in enumerate(rec_texts):
            clean_text = str(text).strip()
            if not clean_text:
                continue

            score = float(rec_scores[i]) if i < len(rec_scores) else 0.0
            box_data = None
            if rec_boxes is not None and i < len(rec_boxes):
                try:
                    box_data = [[float(v) for v in pt] for pt in rec_boxes[i]]
                except Exception:
                    box_data = None

            lines.append(OCRLineItem(text=clean_text, confidence=round(score, 4), box=box_data))

        page_text = "\n".join(l.text for l in lines)
        avg_conf = (
            round(sum(l.confidence for l in lines) / len(lines), 4)
            if lines
            else 0.0
        )

        return OCRPageResult(
            page_number=page_num,
            text=page_text,
            lines=lines,
            confidence=avg_conf,
        )
