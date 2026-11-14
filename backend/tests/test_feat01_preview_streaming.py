import pytest
from pathlib import Path
from httpx import AsyncClient

TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00"
    b"\x02\x00\x01Haf\xa0\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture
async def setup_folder(async_client: AsyncClient, tmp_path: Path):
    root = tmp_path / "managed_test_folder"
    root.mkdir(parents=True, exist_ok=True)

    resp = await async_client.post(
        "/api/v1/folders/register",
        json={
            "name": "Test Managed Folder",
            "root_path": str(root.resolve()),
            "monitoring_enabled": False,
            "scan_on_startup": False,
            "exclude_patterns": [],
        },
    )
    assert resp.status_code == 201
    folder_data = resp.json()
    return folder_data["id"], root


@pytest.mark.asyncio
async def test_image_preview_stream(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    # Create a small valid test PNG image
    img_path = root / "sample.png"
    img_path.write_bytes(TINY_PNG)

    # Full preview
    resp = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "sample.png", "thumbnail": False},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["cache-control"] == "private, max-age=3600"
    assert len(resp.content) == len(TINY_PNG)

    # Thumbnail preview (falls back to FileResponse if PIL is not installed, or generates thumbnail)
    thumb_resp = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "sample.png", "thumbnail": True},
    )
    assert thumb_resp.status_code == 200
    assert "image/" in thumb_resp.headers["content-type"]
    assert thumb_resp.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_svg_preview_csp_header(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    svg_content = '<svg xmlns="http://www.w3.org/2000/svg" width="50" height="50"><circle cx="25" cy="25" r="20" fill="red"/></svg>'
    svg_path = root / "icon.svg"
    svg_path.write_text(svg_content, encoding="utf-8")

    resp = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "icon.svg"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/svg+xml"
    assert "Content-Security-Policy" in resp.headers
    assert "default-src 'none'" in resp.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_text_preview_success(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    text_file = root / "notes.txt"
    lines = ["Line 1: Hello World", "Line 2: Desktop Storage Manager", "Line 3: Fast and Secure"]
    text_file.write_text("\n".join(lines), encoding="utf-8")

    resp = await async_client.get(
        "/api/v1/fs/preview/text",
        params={"folder_id": folder_id, "relative_path": "notes.txt", "max_bytes": 1024},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "notes.txt"
    assert data["lines_count"] == 3
    assert data["truncated"] is False
    assert "Line 1: Hello World" in data["content"]


@pytest.mark.asyncio
async def test_text_preview_truncation(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    large_text_file = root / "large.log"
    # Create ~5KB text
    large_text_file.write_text("A" * 5000, encoding="utf-8")

    resp = await async_client.get(
        "/api/v1/fs/preview/text",
        params={"folder_id": folder_id, "relative_path": "large.log", "max_bytes": 1024},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["truncated"] is True
    assert data["preview_bytes"] == 1024
    assert len(data["content"]) == 1024


@pytest.mark.asyncio
async def test_text_preview_rejects_binary_file(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    # File with text extension but contains binary null bytes
    bin_file = root / "binary.txt"
    bin_file.write_bytes(b"\x00\x01\x02\x03\x04\xff")

    resp = await async_client.get(
        "/api/v1/fs/preview/text",
        params={"folder_id": folder_id, "relative_path": "binary.txt"},
    )
    assert resp.status_code == 400
    assert "Cannot preview binary file as text" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_preview_path_traversal_rejection(async_client: AsyncClient, setup_folder):
    folder_id, _ = setup_folder

    # Try path traversal outside managed folder
    resp = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "../../secret.txt"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_preview_directory_rejection(async_client: AsyncClient, setup_folder):
    folder_id, root = setup_folder

    subdir = root / "subdir"
    subdir.mkdir()

    resp = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "subdir"},
    )
    assert resp.status_code == 400
    assert "not a regular file" in resp.json()["detail"]
