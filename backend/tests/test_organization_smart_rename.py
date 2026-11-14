import os
from pathlib import Path
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_organization_plan_by_category(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "OrgTestFolder"
    folder_root.mkdir()

    # 1. Register sample managed folder
    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Org Test Folder", "root_path": str(folder_root)},
    )
    assert reg_resp.status_code == 201
    folder_id = reg_resp.json()["id"]

    # 2. Add an unorganized file in root
    unorganized_txt = folder_root / "test_notes.txt"
    unorganized_txt.write_text("Meeting notes")
    orig_mtime = unorganized_txt.stat().st_mtime

    # 3. Generate organization plan by category
    resp = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_category",
            "move_unorganized_only": True,
            "include_subfolders": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["managed_folder_id"] == folder_id
    assert data["strategy"] == "by_category"
    assert data["status"] == "draft"
    assert data["files_analyzed_count"] > 0
    assert len(data["current_structure"]) > 0
    assert len(data["proposed_structure"]) > 0
    assert data["change_plan_id"] is not None

    # Check proposed items
    items = data["items"]
    move_items = [it for it in items if it["operation"] == "move"]
    test_note_op = next((it for it in move_items if it["source_relative_path"] == "test_notes.txt"), None)
    assert test_note_op is not None
    assert test_note_op["destination_relative_path"] == "Documents/test_notes.txt"
    assert test_note_op["category"] == "document"

    # Verify strictly read-only: test_notes.txt must still exist in root, not yet moved!
    assert unorganized_txt.exists()
    assert unorganized_txt.stat().st_mtime == orig_mtime


@pytest.mark.asyncio
async def test_organization_plan_by_date(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "DateOrgFolder"
    folder_root.mkdir()
    (folder_root / "file1.txt").write_text("1")

    # Register folder
    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Date Org Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_resp.json()["id"]

    resp = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "by_date",
            "include_subfolders": False,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["strategy"] == "by_date"


@pytest.mark.asyncio
async def test_smart_rename_plan_consistent(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "RenameTestFolder"
    folder_root.mkdir()

    # Register folder
    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rename Test Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_resp.json()["id"]

    # Create messy filename
    messy_file = folder_root / "My Messy   File--Name__2025.txt"
    messy_file.write_text("content")

    resp = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "make_consistent",
            "case_transform": "lower",
            "space_replacement": "_",
            "keep_extension": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()

    assert data["managed_folder_id"] == folder_id
    assert data["strategy"] == "make_consistent"
    assert data["status"] == "draft"

    # Verify messy file was renamed to clean snake_case
    item = next((it for it in data["items"] if it["original_name"] == "My Messy   File--Name__2025.txt"), None)
    assert item is not None
    assert item["status"] == "ready"
    assert item["proposed_name"] == "my_messy_file_name_2025.txt"

    # Strictly read-only verification
    assert messy_file.exists()


@pytest.mark.asyncio
async def test_smart_rename_collision_resolution(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "CollisionFolder"
    folder_root.mkdir()

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Collision Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_resp.json()["id"]

    f1 = folder_root / "Report Final.txt"
    f2 = folder_root / "report--final.txt"
    f1.write_text("1")
    f2.write_text("2")

    resp = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "make_consistent",
            "add_sequence_on_collision": True,
            "target_relative_paths": ["Report Final.txt", "report--final.txt"],
        },
    )
    assert resp.status_code == 201
    data = resp.json()

    items = data["items"]
    assert len(items) == 2
    # One of them should have sequence number added to resolve intra-batch collision
    names = [it["proposed_name"] for it in items]
    assert len(set(names)) == 2  # No duplicate proposed names!


@pytest.mark.asyncio
async def test_plan_item_edit_and_submit(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "EditPlanFolder"
    folder_root.mkdir()

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Edit Plan Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_resp.json()["id"]

    f = folder_root / "draft_file.txt"
    f.write_text("test")

    # Generate rename plan
    plan_resp = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "make_consistent",
            "target_relative_paths": ["draft_file.txt"],
            "skip_compliant_files": False,
        },
    )
    assert plan_resp.status_code == 201
    plan_id = plan_resp.json()["change_plan_id"]
    item_id = plan_resp.json()["items"][0]["item_id"]

    # 1. Edit the plan item destination
    edit_resp = await async_client.put(
        f"/api/v1/transactions/plans/{plan_id}/items/{item_id}",
        json={"new_destination_relative_path": "custom_name.txt"},
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["destination_relative_path"] == "custom_name.txt"

    # 2. Submit the plan for review
    submit_resp = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/submit")
    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == "pending_review"


@pytest.mark.asyncio
async def test_smart_rename_describe_content_with_ocr(async_client: AsyncClient, tmp_path: Path):
    """Verifies Smart Rename uses PaddleOCR on images to propose meaningful names based on image text."""
    from PIL import Image, ImageDraw

    folder_root = tmp_path / "OCRSmartRenameFolder"
    folder_root.mkdir()

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "OCR Rename Folder", "root_path": str(folder_root)},
    )
    assert reg_resp.status_code == 201
    folder_id = reg_resp.json()["id"]

    # Create image with text: INVOICE TELKOM
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "INVOICE TELKOM", fill=(0, 0, 0))
    img_path = folder_root / "IMG_9999.png"
    img.save(img_path)

    plan_resp = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "describe_content",
            "use_ai_content": True,
            "target_relative_paths": ["IMG_9999.png"],
            "skip_compliant_files": False,
        },
    )
    assert plan_resp.status_code == 201
    data = plan_resp.json()
    assert len(data["items"]) == 1
    proposed_name = data["items"][0]["proposed_name"].lower()

    # The proposed name should contain keywords from the OCR text (invoice or telkom)
    assert "invoice" in proposed_name or "telkom" in proposed_name
    assert proposed_name.endswith(".png")


@pytest.mark.asyncio
async def test_smart_rename_single_item_ocr_and_batch_endpoints(async_client: AsyncClient, tmp_path: Path):
    """Verifies single-item OCR on-demand and batch background endpoints."""
    from PIL import Image, ImageDraw

    folder_root = tmp_path / "SingleItemOCRFolder"
    folder_root.mkdir()

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Single OCR Folder", "root_path": str(folder_root)},
    )
    folder_id = reg_resp.json()["id"]

    # Create image with text: STRUK KOPI KENANGAN
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((20, 30), "STRUK KOPI KENANGAN", fill=(0, 0, 0))
    img_path = folder_root / "photo_123.jpg"
    img.save(img_path)

    # 1. Create plan without sync OCR (clean fast generation)
    plan_resp = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "describe_content",
            "use_ai_content": False,
            "skip_compliant_files": False,
        },
    )
    assert plan_resp.status_code == 201
    plan_data = plan_resp.json()
    plan_id = plan_data["change_plan_id"]
    item_id = plan_data["items"][0]["item_id"]

    # 2. Trigger on-demand OCR for this single item
    ocr_item_resp = await async_client.post(
        f"/api/v1/smart-rename/items/{item_id}/analyze-ocr",
        json={"plan_id": plan_id, "item_id": item_id},
    )
    print("STATUS:", ocr_item_resp.status_code, "BODY:", ocr_item_resp.text)
    assert ocr_item_resp.status_code == 200
    res_data = ocr_item_resp.json()
    assert res_data["success"] is True
    assert res_data["item_id"] == item_id
    proposed = res_data["proposed_name"].lower()
    assert any(k in proposed for k in ("struk", "strijk", "kopi", "kenangan"))

    # 3. Check batch OCR endpoints
    batch_resp = await async_client.post(f"/api/v1/smart-rename/plans/{plan_id}/batch-ocr")
    assert batch_resp.status_code == 200

    status_resp = await async_client.get(f"/api/v1/smart-rename/plans/{plan_id}/batch-ocr/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["plan_id"] == plan_id


@pytest.mark.asyncio
async def test_quick_ocr_suggest_endpoint(async_client: AsyncClient, tmp_path: Path):
    """Verifies that POST /api/v1/smart-rename/quick-ocr-suggest performs direct OCR extraction
    and generates a descriptive AI filename suggestion for a single file on disk."""
    folder_root = tmp_path / "quick_ocr_test"
    folder_root.mkdir()

    from PIL import Image, ImageDraw
    img = Image.new("RGB", (300, 100), color=(255, 255, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 10), "INVOICE TELKOM", fill=(0, 0, 0))
    receipt_file = folder_root / "scan_unknown_001.png"
    img.save(receipt_file)

    reg_resp = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Quick OCR Test Folder", "root_path": str(folder_root)},
    )
    assert reg_resp.status_code == 201
    folder_id = reg_resp.json()["id"]

    suggest_resp = await async_client.post(
        "/api/v1/smart-rename/quick-ocr-suggest",
        json={"folder_id": folder_id, "relative_path": "scan_unknown_001.png"},
    )
    assert suggest_resp.status_code == 200
    data = suggest_resp.json()
    assert data["success"] is True
    assert data["original_name"] == "scan_unknown_001.png"
    assert len(data["proposed_name"]) > 0
    assert data["proposed_name"].endswith(".png")


