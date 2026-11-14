import pytest
import os
from pathlib import Path
from httpx import AsyncClient

from backend.app.services.managed_folder import (
    PathValidator,
    ProtectedPathRegistry,
    ManagedFolderException,
    ManagedFolderService,
)
from backend.app.services.drive_service import DriveService
from backend.app.db.models.managed_folder import ManagedFolder


@pytest.mark.asyncio
async def test_drive_service_discovery():
    """FNE-5: Verify drive discovery service detects local logical drives with metadata."""
    drives = DriveService.list_available_drives()
    assert len(drives) > 0

    # Ensure C:\ exists on Windows
    c_drive = next((d for d in drives if d.root_path.upper().startswith("C:")), None)
    assert c_drive is not None
    assert c_drive.is_available is True
    assert c_drive.total_bytes > 0
    assert c_drive.free_bytes >= 0
    assert c_drive.filesystem != ""


@pytest.mark.asyncio
async def test_api_list_drives(async_client: AsyncClient):
    """FNE-5: Verify GET /api/v1/folders/drives returns available drive roots."""
    response = await async_client.get("/api/v1/folders/drives")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    c_drive = next((d for d in data if d["root_path"].upper().startswith("C:")), None)
    assert c_drive is not None
    assert "total_bytes" in c_drive
    assert "volume_label" in c_drive
    assert "is_available" in c_drive



@pytest.mark.asyncio
async def test_protected_path_registry():
    """FNE-7: Verify ProtectedPathRegistry identifies critical OS and system paths."""
    # System root directories
    assert ProtectedPathRegistry.is_protected("C:\\Windows")
    assert ProtectedPathRegistry.is_protected("C:\\Windows\\System32")
    assert ProtectedPathRegistry.is_protected("C:\\Program Files")
    assert ProtectedPathRegistry.is_protected("C:\\Program Files (x86)")
    assert ProtectedPathRegistry.is_protected("C:\\ProgramData")

    # Volume root special items
    assert ProtectedPathRegistry.is_protected("C:\\System Volume Information")
    assert ProtectedPathRegistry.is_protected("C:\\$Recycle.Bin")
    assert ProtectedPathRegistry.is_protected("C:\\Recovery")
    assert ProtectedPathRegistry.is_protected("C:\\pagefile.sys")
    assert ProtectedPathRegistry.is_protected("C:\\hiberfil.sys")
    assert ProtectedPathRegistry.is_protected("C:\\dumpstack.log.tmp")

    # Safe user paths should NOT be protected
    assert not ProtectedPathRegistry.is_protected("C:\\Users\\Public\\Documents")
    assert not ProtectedPathRegistry.is_protected("C:\\Data\\Projects")


@pytest.mark.asyncio
async def test_path_validator_drive_root():
    """FNE-7: Verify PathValidator handles drive roots appropriately."""
    # Pure drive root without trailing backslash or with it
    assert PathValidator.is_drive_root("C:\\")
    assert PathValidator.is_drive_root("c:/")
    assert PathValidator.is_drive_root("D:\\")
    assert not PathValidator.is_drive_root("C:\\Windows")
    assert not PathValidator.is_drive_root("C:\\Users\\Documents")


@pytest.mark.asyncio
async def test_register_drive_root_success_and_metadata(async_client: AsyncClient, monkeypatch):
    """FNE-6: Register a drive root, verify root_type='drive', volume label/serial, and non-destructive removal."""
    # Find an available drive
    drives = DriveService.list_available_drives()
    target_drive = drives[0]

    # Register target drive
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={
            "name": f"Drive {target_drive.drive_letter}",
            "root_path": target_drive.root_path,
            "root_type": "drive",
            "monitoring_enabled": False,
        },
    )
    assert reg_res.status_code == 201
    folder_data = reg_res.json()
    folder_id = folder_data["id"]

    assert folder_data["root_type"] == "drive"
    assert folder_data["volume_serial"] == target_drive.volume_serial
    assert folder_data["volume_label"] == target_drive.volume_label
    assert folder_data["is_available"] is True
    assert folder_data["volume_total_bytes"] is not None
    assert folder_data["volume_free_bytes"] is not None

    # Verify unregistering folder does NOT delete the drive
    del_res = await async_client.delete(f"/api/v1/folders/{folder_id}")
    assert del_res.status_code == 200
    assert Path(target_drive.root_path).exists()


@pytest.mark.asyncio
async def test_register_protected_system_folder_rejected(async_client: AsyncClient):
    """FNE-7: Registering C:\\Windows, C:\\Program Files, etc., must be strictly rejected."""
    for sys_path in ["C:\\Windows", "C:\\Program Files", "C:\\System Volume Information"]:
        res = await async_client.post(
            "/api/v1/folders/register",
            json={
                "name": "System Folder Attempt",
                "root_path": sys_path,
            },
        )
        assert res.status_code == 400
        assert "protected" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_overlap_detection_between_drive_and_subfolder(async_client: AsyncClient, tmp_path: Path):
    """FNE-11: Detect and prevent nesting/overlap between drive root and subfolders."""
    # Use real drive path
    drives = DriveService.list_available_drives()
    drive = drives[0]
    drive_path = drive.root_path

    # 1. Register drive root
    reg_drive = await async_client.post(
        "/api/v1/folders/register",
        json={
            "name": f"Drive {drive.drive_letter}",
            "root_path": drive_path,
            "root_type": "drive",
        },
    )
    assert reg_drive.status_code == 201
    drive_folder_id = reg_drive.json()["id"]

    try:
        # 2. Try to register a subfolder on this drive
        subfolder = tmp_path / "SubProject"
        subfolder.mkdir(exist_ok=True)

        # If tmp_path is on the same drive:
        if Path(drive_path).drive.upper() == subfolder.drive.upper():
            res_sub = await async_client.post(
                "/api/v1/folders/register",
                json={
                    "name": "Subfolder Under Drive",
                    "root_path": str(subfolder),
                },
            )
            assert res_sub.status_code == 400
            assert "overlap" in res_sub.json()["detail"].lower() or "nested" in res_sub.json()["detail"].lower()
    finally:
        # Clean up registered drive folder
        await async_client.delete(f"/api/v1/folders/{drive_folder_id}")


@pytest.mark.asyncio
async def test_scope_enforcement_rejects_protected_targets(tmp_path: Path):
    """FNE-7: PathValidator.resolve_and_verify_scope must reject targets resolving to protected OS paths."""
    # Create a mock drive folder
    drive_folder = ManagedFolder(
        id="drive-root-id",
        name="Drive C",
        root_path="C:\\",
        root_type="drive",
        is_enabled=1,
    )

    # Valid non-protected path
    safe_rel = "Users"
    if (Path("C:\\") / safe_rel).exists():
        resolved = PathValidator.resolve_and_verify_scope(drive_folder, safe_rel)
        assert resolved is not None

    # Protected paths MUST be rejected
    protected_targets = [
        "Windows",
        "Windows\\System32",
        "Program Files",
        "System Volume Information",
        "$Recycle.Bin",
        "pagefile.sys",
    ]

    for p in protected_targets:
        with pytest.raises(ManagedFolderException) as exc:
            PathValidator.resolve_and_verify_scope(drive_folder, p)
        assert "protected" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_storage_analyzer_skips_protected_files(async_client: AsyncClient, tmp_path: Path):
    """FNE-8: Storage analysis correctly identifies and skips protected paths."""
    test_root = tmp_path / "MockDrive"
    test_root.mkdir()

    # Create normal files
    (test_root / "normal1.txt").write_text("Hello Normal File 1")
    (test_root / "normal2.txt").write_text("Hello Normal File 2")

    # Create fake system folders
    fake_sys = test_root / "System Volume Information"
    fake_sys.mkdir()
    (fake_sys / "sysinfo.dat").write_bytes(b"Secret System Data" * 50)

    fake_recycle = test_root / "$Recycle.Bin"
    fake_recycle.mkdir()
    (fake_recycle / "deleted.tmp").write_bytes(b"Trash" * 50)

    # Register as folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Mock Drive Storage", "root_path": str(test_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Analyze
    analyze_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": folder_id},
    )
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    # The normal files must be counted
    assert data["total_files_count"] == 2
    # The protected system files/folders must be skipped
    assert data["skipped_protected_count"] >= 2


@pytest.mark.asyncio
async def test_drive_health_and_serial_revalidation(async_client: AsyncClient):
    """FNE-12: Drive availability and serial number verification."""
    # Register real drive
    drives = DriveService.list_available_drives()
    target_drive = drives[0]

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={
            "name": f"Drive Health {target_drive.drive_letter}",
            "root_path": target_drive.root_path,
            "root_type": "drive",
        },
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    try:
        # Check health of online drive
        health_res = await async_client.get(f"/api/v1/folders/{folder_id}/health")
        assert health_res.status_code == 200
        health_data = health_res.json()
        assert health_data["is_accessible"] is True
        assert health_data["exists"] is True
        assert health_data["overall_status"] == "healthy"

        # Check get_folder response has is_available True
        get_res = await async_client.get(f"/api/v1/folders/{folder_id}")
        assert get_res.status_code == 200
        assert get_res.json()["is_available"] is True
    finally:
        await async_client.delete(f"/api/v1/folders/{folder_id}")

