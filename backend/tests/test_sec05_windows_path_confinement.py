import pytest
from pathlib import Path
from httpx import AsyncClient

from backend.app.services.managed_folder import (
    ManagedFolderException,
    PathValidator,
    is_windows_reserved_name,
)
from backend.app.db.models.managed_folder import ManagedFolder


# =============================================================================
# 1. Windows Reserved Device Names Unit Tests
# =============================================================================

@pytest.mark.parametrize(
    "name,expected",
    [
        ("CON", True),
        ("con", True),
        ("con.txt", True),
        ("CON.TXT", True),
        ("PRN", True),
        ("prn.dat", True),
        ("AUX", True),
        ("aux.json", True),
        ("NUL", True),
        ("nul.log", True),
        ("COM1", True),
        ("com1.txt", True),
        ("COM9", True),
        ("LPT1", True),
        ("lpt1.pdf", True),
        ("LPT9", True),
        ("constant.txt", False),
        ("con2.txt", False),
        ("auxiliary.doc", False),
        ("my_prn_file.txt", False),
        ("normal_file.pdf", False),
        ("", False),
    ],
)
def test_is_windows_reserved_name(name: str, expected: bool):
    assert is_windows_reserved_name(name) is expected


# =============================================================================
# 2. PathValidator Scope Confinement Unit Tests
# =============================================================================

def test_resolve_and_verify_scope_rejects_ads(tmp_path: Path):
    """Verify Alternate Data Streams (':') are strictly blocked in relative paths."""
    folder = ManagedFolder(id="f1", name="TestFolder", root_path=str(tmp_path), is_enabled=1)

    ads_paths = [
        "file.txt:hidden_stream",
        "file.txt:$DATA",
        "::$DATA",
        "sub/file.txt:stream",
        "C:escaped.txt",
        ":colon_start",
    ]
    for p in ads_paths:
        with pytest.raises(ManagedFolderException, match="Alternate Data Streams or drive colons"):
            PathValidator.resolve_and_verify_scope(folder, p)


def test_resolve_and_verify_scope_rejects_reserved_names(tmp_path: Path):
    """Verify Windows reserved device names are blocked across all segments."""
    folder = ManagedFolder(id="f1", name="TestFolder", root_path=str(tmp_path), is_enabled=1)

    reserved_rel_paths = [
        "CON",
        "con.txt",
        "PRN",
        "sub/aux.json",
        "deep/nested/NUL/info.txt",
        "com1.log",
        "lpt5.pdf",
    ]
    for p in reserved_rel_paths:
        with pytest.raises(ManagedFolderException, match="Windows reserved device name"):
            PathValidator.resolve_and_verify_scope(folder, p)


def test_resolve_and_verify_scope_rejects_trailing_space_dot(tmp_path: Path):
    """Verify trailing spaces and periods in path segments are blocked."""
    folder = ManagedFolder(id="f1", name="TestFolder", root_path=str(tmp_path), is_enabled=1)

    with pytest.raises(ManagedFolderException, match="Trailing spaces and periods"):
        PathValidator.resolve_and_verify_scope(folder, "sub/bad.")

    with pytest.raises(ManagedFolderException, match="Trailing spaces and periods"):
        PathValidator.resolve_and_verify_scope(folder, "sub/bad ")


def test_resolve_and_verify_scope_allows_safe_paths(tmp_path: Path):
    """Verify legitimate paths resolve and confine safely."""
    folder = ManagedFolder(id="f1", name="TestFolder", root_path=str(tmp_path), is_enabled=1)

    safe_target = PathValidator.resolve_and_verify_scope(folder, "documents/invoice_2026.pdf")
    expected = (tmp_path / "documents" / "invoice_2026.pdf").resolve()
    assert safe_target == expected

    root_target = PathValidator.resolve_and_verify_scope(folder, "")
    assert root_target == tmp_path.resolve()


# =============================================================================
# 3. Application Self-Protection Unit Tests
# =============================================================================

def test_protected_paths_includes_app_dirs():
    """Verify get_protected_paths() includes the project root, backend, and data directories."""
    protected = PathValidator.get_protected_paths()
    project_root = Path(__file__).resolve().parents[2]  # backend/tests/.. -> project_root

    assert project_root in protected
    assert (project_root / "backend").resolve() in protected
    assert (project_root / "data").resolve() in protected


def test_validate_new_root_path_rejects_app_directories():
    """Verify validate_new_root_path rejects registering project root, backend, data, or ancestors."""
    project_root = Path(__file__).resolve().parents[2]
    backend_dir = project_root / "backend"
    data_dir = project_root / "data"
    parent_dir = project_root.parent

    # 1. Project root itself
    with pytest.raises(ManagedFolderException, match="protected"):
        PathValidator.validate_new_root_path(str(project_root), [])

    # 2. Backend directory
    with pytest.raises(ManagedFolderException, match="protected"):
        PathValidator.validate_new_root_path(str(backend_dir), [])

    # 3. Data directory
    with pytest.raises(ManagedFolderException, match="protected"):
        PathValidator.validate_new_root_path(str(data_dir), [])

    # 4. Project parent (contains the project)
    with pytest.raises(ManagedFolderException, match="protected"):
        PathValidator.validate_new_root_path(str(parent_dir), [])


# =============================================================================
# 4. API Integration Tests (Registration, Browse & Quick Operations)
# =============================================================================

@pytest.mark.asyncio
async def test_api_rejects_app_directory_registration(async_client: AsyncClient):
    """Verify registering the application directory via API returns 400 Bad Request."""
    project_root = Path(__file__).resolve().parents[2]

    res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "App Code", "root_path": str(project_root)},
    )
    assert res.status_code == 400
    assert "protected" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_rejects_ads_and_reserved_names_in_browse(async_client: AsyncClient, tmp_path: Path):
    """Verify browse API returns 400 when ADS or reserved device names are requested."""
    folder_dir = tmp_path / "browse_confinement_test"
    folder_dir.mkdir()

    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Confinement Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    # 1. ADS query
    res_ads = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": "test.txt:stream"},
    )
    assert res_ads.status_code == 400
    assert "alternate data streams" in res_ads.json()["detail"].lower()

    # 2. Windows reserved name query
    res_res = await async_client.get(
        "/api/v1/fs/browse",
        params={"folder_id": folder_id, "relative_path": "CON"},
    )
    assert res_res.status_code == 400
    assert "reserved device name" in res_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_api_quick_create_folder_rejects_reserved_and_ads(async_client: AsyncClient, tmp_path: Path):
    """Verify quick folder creation rejects reserved names and ADS."""
    folder_dir = tmp_path / "quick_confinement_test"
    folder_dir.mkdir()

    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Quick Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    # 1. Reserved device name folder
    res_con = await async_client.post(
        "/api/v1/transactions/quick/create-folder",
        json={
            "managed_folder_id": folder_id,
            "folder_name": "CON",
            "parent_relative_path": "",
        },
    )
    assert res_con.status_code == 400
    assert "reserved device name" in res_con.json()["detail"].lower()

    # 2. ADS folder
    res_ads = await async_client.post(
        "/api/v1/transactions/quick/create-folder",
        json={
            "managed_folder_id": folder_id,
            "folder_name": "Folder:Stream",
            "parent_relative_path": "",
        },
    )
    assert res_ads.status_code == 400
    assert "alternate data streams" in res_ads.json()["detail"].lower()


@pytest.mark.asyncio
async def test_plan_validation_blocks_reserved_device_names(async_client: AsyncClient, tmp_path: Path):
    """Verify change plans with reserved names are marked with issues and blocked from execution."""
    folder_dir = tmp_path / "plan_confinement_test"
    folder_dir.mkdir()

    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Plan Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    # Plan with reserved destination
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Malicious Reserved Plan",
        "items": [
            {
                "operation": "create_directory",
                "destination_relative_path": "NUL",
                "sequence_no": 1,
            }
        ],
    }
    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code in (200, 201)
    plan_id = create_res.json()["id"]

    val_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/validate")
    assert val_res.status_code == 200
    val_data = val_res.json()
    assert val_data["can_execute"] is False
    assert any("reserved device name" in iss["message"].lower() for iss in val_data["issues"])
