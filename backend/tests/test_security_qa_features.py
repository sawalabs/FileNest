from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient
from PIL import Image

from backend.app.core.security import validate_probe_url
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.services.managed_folder import ManagedFolderException
from backend.app.services.ocr_service import PaddleOCRService


# =============================================================================
# SEC-07: CSV Formula Injection Sanitization
# =============================================================================


@pytest.mark.asyncio
async def test_sec07_csv_export_neutralizes_formula_injection(
    async_client: AsyncClient,
):
    """Verify CSV history export prefixes leading formula trigger chars with an apostrophe."""
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        repo = AuditLogRepository(db)
        repo.record(
            actor_type="user",
            action="=cmd|'/C calc'!A0",
            entity_type="file",
            entity_id="+SUM(1,2)-@HACK",
            details={"note": "-formula"},
        )
        repo.record(
            actor_type="user",
            action="@evil_macro",
            entity_type="file",
            entity_id="-1+1",
            details={"note": "normal"},
        )
    finally:
        db_gen.close()

    export_res = await async_client.get("/api/v1/history/export?format=csv")
    assert export_res.status_code == 200
    body = export_res.text

    assert "'=cmd|'/C calc'!A0" in body
    assert "'+SUM(1,2)-@HACK" in body
    assert "'@evil_macro" in body
    assert "'-1+1" in body


# =============================================================================
# SEC-08: OpenRouter SSRF & IPv4-Mapped IPv6 Bypass Prevention
# =============================================================================


def test_sec08_validate_probe_url_blocks_ipv4_mapped_and_multicast():
    """Verify IPv4-mapped IPv6 addresses, unspecified, and multicast targets are rejected."""
    with pytest.raises(ValueError, match="diblokir"):
        validate_probe_url("http://[::ffff:169.254.169.254]/latest/meta-data")

    with pytest.raises(ValueError, match="diblokir"):
        validate_probe_url("http://[::ffff:0.0.0.0]:11434/v1")

    with pytest.raises(ValueError, match="diblokir"):
        validate_probe_url("http://0.0.0.0:11434/v1")

    with pytest.raises(ValueError, match="diblokir"):
        validate_probe_url("http://224.0.0.1/v1")


@pytest.mark.asyncio
async def test_sec08_openrouter_endpoint_ssrf_rejected_in_settings(async_client: AsyncClient):
    """Verify updating openrouter_endpoint to metadata/unspecified IPs is rejected by Settings API."""
    res = await async_client.put(
        "/api/v1/settings/ai",
        json={"openrouter_endpoint": "http://169.254.169.254/latest"},
    )
    assert res.status_code == 400
    assert "diblokir" in res.json()["detail"].lower() or "tidak valid" in res.json()["detail"].lower()


# =============================================================================
# SEC-09: /api/v1/auth/session Cross-Origin & Cache Hardening
# =============================================================================


@pytest.mark.asyncio
async def test_sec09_auth_session_blocks_cross_site_and_disallowed_origins(
    async_client: AsyncClient,
):
    """Verify /api/v1/auth/session blocks cross-site browser requests and disallowed origins."""
    # Cross-site fetch metadata header
    res_cross = await async_client.get(
        "/api/v1/auth/session",
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert res_cross.status_code == 403

    # Disallowed Origin header
    res_origin = await async_client.get(
        "/api/v1/auth/session",
        headers={"Origin": "https://evil-attacker.example"},
    )
    assert res_origin.status_code == 403

    # Allowed same-origin / desktop Origin returns token with no-store cache headers
    res_ok = await async_client.get(
        "/api/v1/auth/session",
        headers={"Origin": "http://localhost:1420", "Sec-Fetch-Site": "same-origin"},
    )
    assert res_ok.status_code == 200
    assert "token" in res_ok.json()
    assert "no-store" in res_ok.headers.get("cache-control", "").lower()


# =============================================================================
# SEC-10: Decompression Bomb Protection in Image Preview & OCR
# =============================================================================


@pytest.mark.asyncio
async def test_sec10_preview_rejects_oversized_pixel_dimensions(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify image preview rejects images exceeding MAX_SAFE_IMAGE_PIXELS with HTTP 413."""
    folder_root = tmp_path / "sec10_bomb"
    folder_root.mkdir()

    # Create a tiny-on-disk but large-dimension monochrome PNG (9000 x 6000 = 54 MP > 50 MP)
    bomb_img_path = folder_root / "oversized_dim.png"
    old_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        img = Image.new("1", (9000, 6000), 1)
        img.save(bomb_img_path, format="PNG")
    finally:
        Image.MAX_IMAGE_PIXELS = old_max

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Sec10 Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.get(
        "/api/v1/fs/preview",
        params={"folder_id": folder_id, "relative_path": "oversized_dim.png"},
    )
    assert res.status_code == 413


def test_sec10_ocr_rejects_oversized_pixel_dimensions(tmp_path: Path):
    """Verify OCR image extractor catches excessive pixel dimensions cleanly without crashing."""
    bomb_img_path = tmp_path / "ocr_oversized.png"
    old_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = None
    try:
        img = Image.new("1", (9000, 6000), 1)
        img.save(bomb_img_path, format="PNG")
    finally:
        Image.MAX_IMAGE_PIXELS = old_max

    ocr = PaddleOCRService(db=MagicMock())
    with pytest.raises(ManagedFolderException, match="exceed|Decompression Bomb|pixel"):
        ocr._process_image_file(str(bomb_img_path))


# =============================================================================
# SEC-11: Immediate Path Validation on Plan Item Edits
# =============================================================================


@pytest.mark.asyncio
async def test_sec11_update_plan_item_rejects_path_traversal_immediately(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify PATCH on plan item immediately blocks path traversal outside Managed Folder."""
    folder_root = tmp_path / "sec11_scope"
    folder_root.mkdir()
    (folder_root / "note.txt").write_text("hello", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Sec11 Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Edit Validation Plan",
            "plan_type": "organize",
            "items": [
                {
                    "operation": "move",
                    "source_relative_path": "note.txt",
                    "destination_relative_path": "sorted/note.txt",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_res.status_code == 201
    plan = plan_res.json()
    item_id = plan["items"][0]["id"]

    patch_res = await async_client.put(
        f"/api/v1/transactions/plans/{plan['id']}/items/{item_id}",
        json={"new_destination_relative_path": "../../outside_escape.txt"},
    )
    assert patch_res.status_code == 400
    detail = patch_res.json()["detail"].lower()
    assert "traversal" in detail or "escapes" in detail or "invalid" in detail or "mengeluarkan" in detail or "diblokir" in detail or "root" in detail


# =============================================================================
# QA-01: Server-Side Directory-First Sorting in /api/v1/fs/browse
# =============================================================================


@pytest.mark.asyncio
async def test_qa01_browse_server_side_sorting_dirs_first(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify /api/v1/fs/browse keeps directories first and sorts files by size desc."""
    folder_root = tmp_path / "qa01_sort"
    folder_root.mkdir()
    (folder_root / "z_folder").mkdir()
    (folder_root / "a_folder").mkdir()
    (folder_root / "small.txt").write_bytes(b"a" * 10)
    (folder_root / "large.bin").write_bytes(b"b" * 5000)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "QA01 Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "sort_by": "size", "sort_order": "desc"},
    )
    assert res.status_code == 200
    entries = res.json()["entries"]
    assert [e["name"] for e in entries[:2]] in (
        ["a_folder", "z_folder"],
        ["z_folder", "a_folder"],
    )
    assert entries[2]["name"] == "large.bin"
    assert entries[3]["name"] == "small.txt"


# =============================================================================
# QA-02: Dynamic SQLite Database Size Resolution
# =============================================================================


@pytest.mark.asyncio
async def test_qa02_storage_settings_resolves_actual_db_size(async_client: AsyncClient):
    """Verify GET /api/v1/settings/storage succeeds and reports non-negative database.size_bytes."""
    res = await async_client.get("/api/v1/settings/storage")
    assert res.status_code == 200
    data = res.json()
    assert "database" in data
    assert isinstance(data["database"]["size_bytes"], int)
    assert data["database"]["size_bytes"] >= 0


# =============================================================================
# QA-03 & FEAT-02: Storage Multi-Folder IDs + Cleanup Plan Generator
# =============================================================================


@pytest.mark.asyncio
async def test_qa03_and_feat02_multifolder_storage_and_cleanup_plan(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify multi-folder storage analysis populates managed_folder_id and cleanup-plan queues safe drafts."""
    folder_a = tmp_path / "qa03_folder_a"
    folder_b = tmp_path / "qa03_folder_b"
    folder_a.mkdir()
    folder_b.mkdir()
    (folder_a / "empty_sub").mkdir()
    dup_payload = b"duplicate_content_" * 200
    (folder_a / "dup1.bin").write_bytes(dup_payload)
    (folder_a / "dup2.bin").write_bytes(dup_payload)
    (folder_b / "big_b.bin").write_bytes(dup_payload)

    res_a = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Folder A", "root_path": str(folder_a)},
    )
    res_b = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Folder B", "root_path": str(folder_b)},
    )
    assert res_a.status_code == 201 and res_b.status_code == 201
    id_a = res_a.json()["id"]
    id_b = res_b.json()["id"]

    # Run multi-folder analysis (managed_folder_id = None)
    analyze_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": None, "large_file_threshold_bytes": 1000, "calculate_hashes": True},
    )
    assert analyze_res.status_code == 200
    analysis = analyze_res.json()
    assert analysis["managed_folder_id"] is None
    assert len(analysis["large_files"]) >= 3
    assert all(f["managed_folder_id"] in (id_a, id_b) for f in analysis["large_files"])
    assert any(f["managed_folder_id"] == id_b for f in analysis["large_files"])
    assert len(analysis["duplicate_groups"]) >= 1
    assert all(
        f["managed_folder_id"] == id_a
        for g in analysis["duplicate_groups"]
        for f in g["files"]
    )
    assert len(analysis["empty_folders"]) >= 1
    assert any(ef["managed_folder_id"] == id_a for ef in analysis["empty_folders"])

    # Create cleanup plan via FEAT-02 endpoint
    cleanup_res = await async_client.post(
        "/api/v1/storage/cleanup-plan",
        json={
            "cleanup_type": "duplicates",
            "items": [
                {
                    "managed_folder_id": id_a,
                    "relative_path": "dup2.bin",
                    "reason": "Duplicate cleanup test",
                }
            ],
        },
    )
    assert cleanup_res.status_code in (200, 201)
    cleanup_data = cleanup_res.json()
    assert cleanup_data["total_items_queued"] == 1
    assert len(cleanup_data["created_plan_ids"]) == 1

    # Verify original file was NOT deleted automatically and plan is queued in pending_review
    assert (folder_a / "dup2.bin").exists()
    plan_res = await async_client.get(
        f"/api/v1/transactions/plans/{cleanup_data['created_plan_ids'][0]}"
    )
    assert plan_res.status_code == 200
    assert plan_res.json()["status"] == "pending_review"
    assert plan_res.json()["items"][0]["operation"] == "delete_to_recycle_bin"


# =============================================================================
# QA-04: SQL LIKE Wildcard Escaping in History & Monitoring Search
# =============================================================================


@pytest.mark.asyncio
async def test_qa04_search_escapes_sql_like_wildcards(async_client: AsyncClient):
    """Verify literal '%' and '_' characters in search filters do not act as SQL wildcards."""
    hist_res = await async_client.get(
        "/api/v1/history/audit-logs",
        params={"search": "___100%_unmatched___"},
    )
    assert hist_res.status_code == 200
    assert hist_res.json()["total"] == 0

    mon_res = await async_client.get(
        "/api/v1/monitoring/events",
        params={"search": "___100%_unmatched___"},
    )
    assert mon_res.status_code == 200
    assert mon_res.json()["total"] == 0


# =============================================================================
# FEAT-03: Safe Manual Undo / Revert of Completed Execution Jobs
# =============================================================================


@pytest.mark.asyncio
async def test_feat03_manual_undo_reverts_completed_execution_job(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify completed move & rename operations can be safely undone via TransactionManager."""
    folder_root = tmp_path / "feat03_undo"
    folder_root.mkdir()
    src_file = folder_root / "report.txt"
    src_file.write_text("Quarterly Financial Report", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Feat03 Undo Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Move & Rename to Undo",
            "plan_type": "organize",
            "items": [
                {
                    "operation": "create_directory",
                    "source_relative_path": "Archive",
                    "destination_relative_path": "Archive",
                    "sequence_no": 1,
                },
                {
                    "operation": "move",
                    "source_relative_path": "report.txt",
                    "destination_relative_path": "Archive/report_2026.txt",
                    "sequence_no": 2,
                },
            ],
        },
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    assert (await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")).status_code == 200
    exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
    assert exec_res.status_code == 200
    job_id = exec_res.json()["id"]
    assert exec_res.json()["status"] == "completed"
    assert not src_file.exists()
    assert (folder_root / "Archive" / "report_2026.txt").exists()

    # Trigger manual undo
    undo_res = await async_client.post(f"/api/v1/transactions/jobs/{job_id}/undo")
    assert undo_res.status_code == 200
    undo_data = undo_res.json()
    assert undo_data["reverted_count"] == 2
    assert undo_data["failed_count"] == 0
    assert undo_data["status"] == "rolled_back"

    # Original file restored, moved file & Archive directory cleaned up
    assert src_file.exists()
    assert src_file.read_text(encoding="utf-8") == "Quarterly Financial Report"
    assert not (folder_root / "Archive" / "report_2026.txt").exists()
    assert not (folder_root / "Archive").exists()

    # Re-undoing an already rolled_back job must be rejected cleanly
    second_undo = await async_client.post(f"/api/v1/transactions/jobs/{job_id}/undo")
    assert second_undo.status_code == 400


# =============================================================================
# FEAT-05: Cross-Folder Global File Search Endpoint
# =============================================================================


@pytest.mark.asyncio
async def test_feat05_global_search_across_managed_folders(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify GET /api/v1/fs/search locates files across multiple Managed Folders safely."""
    dir_1 = tmp_path / "feat05_one"
    dir_2 = tmp_path / "feat05_two"
    dir_1.mkdir()
    dir_2.mkdir()
    (dir_1 / "sub").mkdir()
    (dir_1 / "sub" / "tax_invoice_2026.pdf").write_text("pdf", encoding="utf-8")
    (dir_2 / "invoice_march.txt").write_text("txt", encoding="utf-8")
    (dir_2 / "unrelated.txt").write_text("noop", encoding="utf-8")

    r1 = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Taxes", "root_path": str(dir_1)},
    )
    r2 = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Receipts", "root_path": str(dir_2)},
    )
    assert r1.status_code == 201 and r2.status_code == 201

    search_res = await async_client.get(
        "/api/v1/fs/search",
        params={"q": "invoice", "limit": 20},
    )
    assert search_res.status_code == 200
    hits = search_res.json()["hits"]
    names = {h["name"] for h in hits}
    assert "tax_invoice_2026.pdf" in names
    assert "invoice_march.txt" in names
    assert "unrelated.txt" not in names
