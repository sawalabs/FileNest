import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_explain_file_within_scope(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_test_folder"
    folder_dir.mkdir(parents=True, exist_ok=True)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Assistant Storage", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    sample_file = folder_dir / "invoice_march_2026.pdf"
    sample_file.write_text("Invoice details for customer A", encoding="utf-8")

    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_id,
            "target_type": "file",
            "relative_path": "invoice_march_2026.pdf",
        },
    )
    assert explain_res.status_code == 200
    data = explain_res.json()
    assert data["target_type"] == "file"
    assert data["target_name"] == "invoice_march_2026.pdf"
    assert "invoice_march_2026.pdf" in data["title"]
    assert "document" in data["summary"].lower()
    assert data["metadata"]["size_bytes"] == sample_file.stat().st_size
    assert len(data["key_insights"]) >= 2
    assert "Transaction Manager" in data["safety_assessment"]
    assert len(data["suggested_actions"]) >= 1


@pytest.mark.asyncio
async def test_explain_file_outside_scope_rejected(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_test_folder_b"
    folder_dir.mkdir(parents=True, exist_ok=True)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Assistant Storage B", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Traversal attempt outside folder
    outside_file = tmp_path / "secret_system_file.txt"
    outside_file.write_text("Confidential", encoding="utf-8")

    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_id,
            "target_type": "file",
            "relative_path": "../secret_system_file.txt",
        },
    )
    # Must fail with 400 or 404
    assert explain_res.status_code in (400, 404)


@pytest.mark.asyncio
async def test_explain_folder_within_scope(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_test_folder_c"
    docs_dir = folder_dir / "Reports"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for i in range(4):
        (docs_dir / f"report_{i}.txt").write_text(f"Report {i}", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Assistant Storage C", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_id,
            "target_type": "folder",
            "relative_path": "Reports",
        },
    )
    assert explain_res.status_code == 200
    data = explain_res.json()
    assert data["target_type"] == "folder"
    assert data["target_name"] == "Reports"
    assert data["metadata"]["file_count"] == 4
    assert len(data["suggested_actions"]) >= 1
    assert "Aman untuk ditata" in data["safety_assessment"]


@pytest.mark.asyncio
async def test_explain_plan_within_scope(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_test_folder_d"
    folder_dir.mkdir(parents=True, exist_ok=True)
    f = folder_dir / "unorganized_doc.docx"
    f.write_text("Content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Assistant Storage D", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Create plan
    plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_id,
            "title": "Pindahkan Dokumen ke Folder Arsip",
            "plan_type": "organize",
            "items": [
                {
                    "operation": "move",
                    "source_relative_path": "unorganized_doc.docx",
                    "destination_relative_path": "Archive/unorganized_doc.docx",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_id,
            "target_type": "plan",
            "entity_id": plan_id,
        },
    )
    assert explain_res.status_code == 200
    data = explain_res.json()
    assert data["target_type"] == "plan"
    assert data["metadata"]["plan_id"] == plan_id
    assert data["metadata"]["items_count"] == 1
    assert "Transaction Manager" in data["safety_assessment"]


@pytest.mark.asyncio
async def test_explain_plan_wrong_managed_folder_rejected(async_client: AsyncClient, tmp_path: Path):
    folder_a = tmp_path / "assistant_folder_1"
    folder_b = tmp_path / "assistant_folder_2"
    folder_a.mkdir(parents=True, exist_ok=True)
    folder_b.mkdir(parents=True, exist_ok=True)

    reg_a = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Folder 1", "root_path": str(folder_a)},
    )
    reg_b = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Folder 2", "root_path": str(folder_b)},
    )
    folder_a_id = reg_a.json()["id"]
    folder_b_id = reg_b.json()["id"]

    # Create plan in folder B
    plan_res = await async_client.post(
        "/api/v1/transactions/plans",
        json={
            "managed_folder_id": folder_b_id,
            "title": "Plan for Folder B",
            "plan_type": "organize",
            "items": [
                {
                    "operation": "create_directory",
                    "destination_relative_path": "TestSub",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert plan_res.status_code == 201
    plan_id = plan_res.json()["id"]

    # Try explaining plan from folder A context
    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_a_id,
            "target_type": "plan",
            "entity_id": plan_id,
        },
    )
    assert explain_res.status_code == 400
    assert "does not belong" in explain_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_suggest_plan_creates_draft_plan_in_review_changes(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_test_folder_e"
    folder_dir.mkdir(parents=True, exist_ok=True)
    file_a = folder_dir / "raw_data.csv"
    file_a.write_text("col1,col2\n1,2\n", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Assistant Storage E", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    suggest_res = await async_client.post(
        "/api/v1/assistant/suggest-plan",
        json={
            "managed_folder_id": folder_id,
            "title": "Usulan Asisten: Tata Data CSV ke Spreadsheet",
            "plan_type": "organize",
            "items": [
                {
                    "operation": "move",
                    "source_relative_path": "raw_data.csv",
                    "destination_relative_path": "Data/raw_data.csv",
                    "sequence_no": 1,
                }
            ],
        },
    )
    assert suggest_res.status_code == 200
    res_data = suggest_res.json()
    assert res_data["status"] == "pending_review"
    assert res_data["items_count"] == 1
    assert "Review Changes" in res_data["message"]
    plan_id = res_data["plan_id"]

    # Retrieve plan via transactions endpoint
    get_plan_res = await async_client.get(f"/api/v1/transactions/plans/{plan_id}")
    assert get_plan_res.status_code == 200
    plan = get_plan_res.json()
    assert plan["status"] == "pending_review"
    assert plan["created_by"] == "ai"

    # Verify NO direct mutation occurred on filesystem: source file is untouched!
    assert file_a.exists()
    assert not (folder_dir / "Data/raw_data.csv").exists()


@pytest.mark.asyncio
async def test_quick_prompts_endpoint(async_client: AsyncClient):
    file_res = await async_client.get("/api/v1/assistant/quick-prompts?target_type=file")
    assert file_res.status_code == 200
    assert len(file_res.json()) >= 2
    assert any(p["target_type"] == "file" for p in file_res.json())

    folder_res = await async_client.get("/api/v1/assistant/quick-prompts?target_type=folder")
    assert folder_res.status_code == 200
    assert len(folder_res.json()) >= 2

    plan_res = await async_client.get("/api/v1/assistant/quick-prompts?target_type=plan")
    assert plan_res.status_code == 200
    assert len(plan_res.json()) >= 2


@pytest.mark.asyncio
async def test_explain_general_with_user_query_and_suggestions(async_client: AsyncClient, tmp_path: Path):
    folder_dir = tmp_path / "assistant_general_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "invoice.pdf").write_text("invoice content", encoding="utf-8")
    (folder_dir / "photo.jpg").write_text("photo data", encoding="utf-8")
    (folder_dir / "archive.zip").write_text("zip data", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "General Test Folder", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Test user query for organizing
    explain_res = await async_client.post(
        "/api/v1/assistant/explain",
        json={
            "managed_folder_id": folder_id,
            "target_type": "general",
            "user_query": "Tolong rapikan file di folder saya",
        },
    )
    assert explain_res.status_code == 200
    data = explain_res.json()
    assert data["target_type"] == "general"
    assert "General Test Folder" in data["title"]
    assert len(data["key_insights"]) >= 2
    assert len(data["suggested_actions"]) >= 1
    assert data["suggested_actions"][0]["plan_type"] == "organize"
    assert len(data["suggested_actions"][0]["items"]) == 3

