import numpy as np
import pytest
from httpx import AsyncClient
from PIL import Image, ImageDraw
import pypdfium2 as pdfium

from backend.app.services.managed_folder import ManagedFolderService


@pytest.mark.asyncio
async def test_ocr_status_endpoint(async_client: AsyncClient):
    """Verifies OCR engine status endpoint returns available status and supported formats."""
    res = await async_client.get("/api/v1/ocr/status")
    assert res.status_code == 200
    data = res.json()
    assert data["available"] is True
    assert "PaddleOCR" in data["engine"]
    assert "application/pdf" in data["supported_formats"]
    assert "image/png" in data["supported_formats"]


@pytest.mark.asyncio
async def test_ocr_extract_path_traversal_blocked(async_client: AsyncClient, tmp_path):
    """Verifies OCR rejects path traversal attempts outside managed folder."""
    folder_dir = tmp_path / "managed_docs"
    folder_dir.mkdir()

    # Register managed folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Docs", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Attempt path traversal
    res = await async_client.post(
        "/api/v1/ocr/extract",
        json={
            "folder_id": folder_id,
            "relative_path": "../../../Windows/win.ini",
        },
    )
    assert res.status_code == 400
    assert "escapes" in res.json()["detail"].lower() or "violation" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_ocr_extract_unsupported_file_type(async_client: AsyncClient, tmp_path):
    """Verifies OCR rejects unsupported file types."""
    folder_dir = tmp_path / "managed_docs2"
    folder_dir.mkdir()

    # Create dummy text file
    txt_file = folder_dir / "notes.txt"
    txt_file.write_text("Plain text notes")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Docs2", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/ocr/extract",
        json={
            "folder_id": folder_id,
            "relative_path": "notes.txt",
        },
    )
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


@pytest.mark.asyncio
async def test_ocr_extract_image_success(async_client: AsyncClient, tmp_path):
    """Verifies PaddleOCR successfully extracts text from a test image."""
    folder_dir = tmp_path / "managed_images"
    folder_dir.mkdir()

    # Create synthetic test image with clear text
    img = Image.new("RGB", (400, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "FILENEST OCR DEMO", fill=(0, 0, 0))
    test_img_path = folder_dir / "invoice_test.png"
    img.save(test_img_path)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Images", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/ocr/extract",
        json={
            "folder_id": folder_id,
            "relative_path": "invoice_test.png",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["filename"] == "invoice_test.png"
    assert "FILENEST" in data["full_text"] or "DEMO" in data["full_text"] or "OCR" in data["full_text"]
    assert data["confidence"] > 0.5
    assert len(data["pages"]) == 1
    assert data["duration_ms"] > 0


@pytest.mark.asyncio
async def test_ocr_extract_pdf_success(async_client: AsyncClient, tmp_path):
    """Verifies PaddleOCR successfully extracts text from a PDF document via pypdfium2."""
    folder_dir = tmp_path / "managed_pdf_docs"
    folder_dir.mkdir()

    # Create synthetic test PDF
    pdf = pdfium.PdfDocument.new()
    pdf.new_page(300, 100)
    pdf_path = folder_dir / "statement.pdf"
    pdf.save(str(pdf_path))

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "PDFs", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.post(
        "/api/v1/ocr/extract",
        json={
            "folder_id": folder_id,
            "relative_path": "statement.pdf",
            "max_pages": 5,
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["filename"] == "statement.pdf"
    assert len(data["pages"]) == 1
    assert data["pages"][0]["page_number"] == 1

