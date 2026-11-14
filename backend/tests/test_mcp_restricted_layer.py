import json
from pathlib import Path
import pytest
from httpx import AsyncClient

from backend.app.schemas.transaction import PlanStatus


@pytest.mark.asyncio
async def test_list_mcp_tools(async_client: AsyncClient):
    """Verifies that all exposed MCP tools have typed schemas and no forbidden tools are exposed."""
    res = await async_client.get("/api/v1/mcp/tools")
    assert res.status_code == 200
    data = res.json()

    assert data["total_count"] == 7
    tool_names = [t["name"] for t in data["tools"]]
    expected_tools = {
        "fs_list_directory",
        "fs_get_metadata",
        "fs_search_files",
        "storage_get_breakdown",
        "storage_detect_duplicates",
        "plan_create_organization",
        "plan_create_rename",
    }
    assert set(tool_names) == expected_tools

    # Security check: verify no dangerous tools exist in the exposed catalog
    dangerous_keywords = ["shell", "exec", "cmd", "bash", "write", "delete", "unlink", "rmdir"]
    for t_name in tool_names:
        for kw in dangerous_keywords:
            assert kw not in t_name.lower()

    # Verify input schemas are valid objects with properties
    for tool in data["tools"]:
        assert tool["inputSchema"]["type"] == "object"
        assert "properties" in tool["inputSchema"]
        assert len(tool["description"]) > 10


@pytest.mark.asyncio
async def test_forbidden_tools_rejection(async_client: AsyncClient):
    """Verifies that any attempt to invoke shell or mutating tools is strictly blocked."""
    forbidden_tools = ["shell_exec", "exec", "run_command", "delete_file", "write_file", "execute_plan"]

    for tool in forbidden_tools:
        res = await async_client.post(
            "/api/v1/mcp/call",
            json={"tool": tool, "arguments": {}},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_error"] is True
        assert "dilarang demi keamanan sistem" in data["error_message"] or "Akses ditolak" in data["error_message"]


@pytest.mark.asyncio
async def test_path_boundary_enforcement(async_client: AsyncClient, tmp_path: Path):
    """Verifies that MCP tools strictly enforce Managed Folder boundaries and reject traversal."""
    folder_dir = tmp_path / "mcp_safe_folder"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP Safe Folder", "root_path": str(folder_dir)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Traversal attack attempts
    traversal_paths = [
        "../outside.txt",
        "../../Windows/System32",
        "..\\..\\Windows",
        "/etc/passwd",
        "C:\\Windows\\notepad.exe",
    ]

    for bad_path in traversal_paths:
        res = await async_client.post(
            "/api/v1/mcp/call",
            json={
                "tool": "fs_get_metadata",
                "arguments": {
                    "managed_folder_id": folder_id,
                    "relative_path": bad_path,
                },
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["is_error"] is True
        assert "Batasan direktori dilanggar" in data["error_message"] or "Access violation" in data["error_message"]


@pytest.mark.asyncio
async def test_fs_list_and_search_mcp_tools(async_client: AsyncClient, tmp_path: Path):
    """Tests read-only filesystem listing and search MCP tools with structured outputs."""
    folder_dir = tmp_path / "mcp_fs_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    sub = folder_dir / "documents"
    sub.mkdir(parents=True, exist_ok=True)

    (sub / "annual_report_2026.pdf").write_text("dummy pdf content", encoding="utf-8")
    (sub / "meeting_notes.docx").write_text("dummy docx content", encoding="utf-8")
    (folder_dir / "photo.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 50)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP FS Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # 1. fs_list_directory on root
    list_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "fs_list_directory",
            "arguments": {"managed_folder_id": folder_id, "relative_path": ""},
        },
    )
    assert list_res.status_code == 200
    list_data = list_res.json()
    assert list_data["is_error"] is False
    data = list_data["data"]
    assert data["total_entries"] == 2  # documents folder and photo.png
    names = [e["name"] for e in data["entries"]]
    assert "documents" in names
    assert "photo.png" in names

    # 2. fs_search_files by query
    search_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "fs_search_files",
            "arguments": {
                "managed_folder_id": folder_id,
                "query": "annual",
                "extension": "pdf",
            },
        },
    )
    assert search_res.status_code == 200
    search_data = search_res.json()["data"]
    assert search_data["total_matches"] == 1
    assert search_data["matches"][0]["name"] == "annual_report_2026.pdf"
    assert search_data["matches"][0]["category"] == "document"


@pytest.mark.asyncio
async def test_metadata_and_privacy_redaction(async_client: AsyncClient, tmp_path: Path):
    """Verifies metadata inspection and privacy redaction of sensitive files and snippets."""
    folder_dir = tmp_path / "mcp_privacy_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Normal text file and sensitive credential file
    (folder_dir / "summary.txt").write_text("Antigravity MCP System safe text content", encoding="utf-8")
    (folder_dir / "secret.env").write_text("DB_PASSWORD=supersecret", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP Privacy Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # Configure AI privacy settings: consent given, .env is sensitive
    await async_client.patch(
        "/api/v1/settings/ai",
        json={
            "content_extraction_consent": True,
            "metadata_only": False,
            "sensitive_file_extensions": [".env", ".key", ".pem"],
        },
    )

    # 1. Metadata for sensitive file -> snippet must be redacted
    meta_env = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "fs_get_metadata",
            "arguments": {
                "managed_folder_id": folder_id,
                "relative_path": "secret.env",
                "include_snippet": True,
            },
        },
    )
    assert meta_env.status_code == 200
    env_data = meta_env.json()["data"]
    assert env_data["is_sensitive"] is True
    assert env_data["content_snippet"] is None
    assert "file sensitif" in env_data["snippet_redacted_reason"]

    # 2. Metadata for non-sensitive file with consent -> snippet provided
    meta_txt = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "fs_get_metadata",
            "arguments": {
                "managed_folder_id": folder_id,
                "relative_path": "summary.txt",
                "include_snippet": True,
            },
        },
    )
    assert meta_txt.status_code == 200
    txt_data = meta_txt.json()["data"]
    assert txt_data["is_sensitive"] is False
    assert txt_data["content_snippet"] == "Antigravity MCP System safe text content"


@pytest.mark.asyncio
async def test_plan_creation_draft_routing(async_client: AsyncClient, tmp_path: Path):
    """Verifies that plan_create_organization creates draft plans for Review Changes and DOES NOT mutate files."""
    folder_dir = tmp_path / "mcp_plan_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    file_to_move = folder_dir / "invoice_101.pdf"
    file_to_move.write_text("invoice content", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP Plan Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # Call plan_create_organization
    plan_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "plan_create_organization",
            "arguments": {
                "managed_folder_id": folder_id,
                "title": "AI Organization Proposal: Invoices",
                "description": "Group invoices under Invoices/ directory",
                "operations": [
                    {
                        "operation": "create_directory",
                        "destination_relative_path": "Invoices",
                        "reason": "Target directory for invoices",
                    },
                    {
                        "operation": "move",
                        "source_relative_path": "invoice_101.pdf",
                        "destination_relative_path": "Invoices/invoice_101.pdf",
                        "reason": "Move invoice into dedicated folder",
                    },
                ],
            },
        },
    )
    assert plan_res.status_code == 200
    plan_data = plan_res.json()["data"]
    assert plan_data["plan_id"] is not None
    assert plan_data["status"] == "pending_review"
    assert plan_data["requires_approval"] is True
    assert plan_data["items_count"] == 2

    # CRITICAL SECURITY CHECK: The file must still exist in its original place, and destination not created yet!
    assert file_to_move.exists()
    assert not (folder_dir / "Invoices" / "invoice_101.pdf").exists()

    # Verify the plan is visible in Review Changes transactions API
    review_res = await async_client.get(f"/api/v1/transactions/plans/{plan_data['plan_id']}")
    assert review_res.status_code == 200
    plan_in_db = review_res.json()
    assert plan_in_db["created_by"] == "ai"
    assert plan_in_db["status"] == "pending_review"


@pytest.mark.asyncio
async def test_mcp_jsonrpc_endpoint(async_client: AsyncClient, tmp_path: Path):
    """Verifies JSON-RPC 2.0 compliance for external MCP runtimes."""
    folder_dir = tmp_path / "mcp_rpc_test"
    folder_dir.mkdir(parents=True, exist_ok=True)
    (folder_dir / "test.txt").write_text("rpc test", encoding="utf-8")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP RPC Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # 1. ping
    ping_res = await async_client.post(
        "/api/v1/mcp/rpc",
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
    )
    assert ping_res.status_code == 200
    assert ping_res.json()["result"]["status"] == "pong"

    # 2. tools/list
    list_rpc = await async_client.post(
        "/api/v1/mcp/rpc",
        json={"jsonrpc": "2.0", "id": "req-2", "method": "tools/list"},
    )
    assert list_rpc.status_code == 200
    assert len(list_rpc.json()["result"]["tools"]) == 7

    # 3. tools/call
    call_rpc = await async_client.post(
        "/api/v1/mcp/rpc",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "fs_list_directory",
                "arguments": {"managed_folder_id": folder_id, "relative_path": ""},
            },
        },
    )
    assert call_rpc.status_code == 200
    rpc_data = call_rpc.json()
    assert rpc_data["result"]["isError"] is False
    assert rpc_data["result"]["data"]["total_entries"] == 1


@pytest.mark.asyncio
async def test_storage_breakdown_and_smart_rename(async_client: AsyncClient, tmp_path: Path):
    """Verifies storage breakdown, duplicate detection, and smart rename plan MCP tools."""
    folder_dir = tmp_path / "mcp_storage_test"
    folder_dir.mkdir(parents=True, exist_ok=True)

    # Create files including duplicates
    content = "identical content for duplicate test " * 20
    (folder_dir / "doc1.txt").write_text(content, encoding="utf-8")
    (folder_dir / "doc2.txt").write_text(content, encoding="utf-8")
    (folder_dir / "big.bin").write_bytes(b"\x00" * 20000)

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "MCP Storage Test", "root_path": str(folder_dir)},
    )
    folder_id = reg_res.json()["id"]

    # 1. storage_get_breakdown
    breakdown_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "storage_get_breakdown",
            "arguments": {"managed_folder_id": folder_id},
        },
    )
    assert breakdown_res.status_code == 200
    b_data = breakdown_res.json()["data"]
    assert b_data["total_files"] == 3
    assert b_data["total_size_bytes"] > 0
    assert len(b_data["categories"]) > 0

    # 2. storage_detect_duplicates
    dup_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "storage_detect_duplicates",
            "arguments": {"managed_folder_id": folder_id, "min_size_bytes": 10},
        },
    )
    assert dup_res.status_code == 200
    d_data = dup_res.json()["data"]
    assert d_data["total_groups"] >= 1
    assert d_data["total_duplicate_files"] >= 2

    # 3. plan_create_rename
    rename_res = await async_client.post(
        "/api/v1/mcp/call",
        json={
            "tool": "plan_create_rename",
            "arguments": {
                "managed_folder_id": folder_id,
                "title": "Smart Rename Clean Doc",
                "renames": [
                    {
                        "source_relative_path": "doc1.txt",
                        "new_file_name": "clean_doc1.txt",
                        "reason": "Standardize naming",
                    }
                ],
            },
        },
    )
    assert rename_res.status_code == 200
    r_data = rename_res.json()["data"]
    assert r_data["plan_type"] == "rename"
    assert r_data["status"] == "pending_review"
    assert r_data["requires_approval"] is True
    # Ensure source was not renamed directly
    assert (folder_dir / "doc1.txt").exists()
    assert not (folder_dir / "clean_doc1.txt").exists()
