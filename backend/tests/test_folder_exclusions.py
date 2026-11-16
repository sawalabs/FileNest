import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_folder_exclusion_toggle_api(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "ExclusionToggleTest"
    folder_root.mkdir()
    (folder_root / "subfolder").mkdir()
    (folder_root / "subfolder" / "file.txt").write_text("sample")

    # 1. Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Exclusion Toggle Test", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # 2. Toggle exclusion: Add
    toggle_res = await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions/toggle",
        json={"relative_path": "subfolder", "exclusion_type": "directory", "reason": "Test exclusion"},
    )
    assert toggle_res.status_code == 200
    data = toggle_res.json()
    assert data["action"] == "added"
    assert data["item"]["value"] == "subfolder"
    assert data["item"]["exclusion_type"] == "directory"

    # 3. Verify get exclusions
    get_res = await async_client.get(f"/api/v1/folders/{folder_id}/exclusions")
    assert get_res.status_code == 200
    exclusions = get_res.json()
    assert len(exclusions) == 1
    assert exclusions[0]["value"] == "subfolder"

    # 4. Toggle exclusion again: Remove
    toggle_res2 = await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions/toggle",
        json={"relative_path": "subfolder", "exclusion_type": "directory"},
    )
    assert toggle_res2.status_code == 200
    data2 = toggle_res2.json()
    assert data2["action"] == "removed"

    # 5. Verify exclusion is gone
    get_res2 = await async_client.get(f"/api/v1/folders/{folder_id}/exclusions")
    assert get_res2.status_code == 200
    assert len(get_res2.json()) == 0


@pytest.mark.asyncio
async def test_storage_analyzer_omits_excluded_folders(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "StorageExclusionTest"
    folder_root.mkdir()

    active_dir = folder_root / "active_dir"
    active_dir.mkdir()
    (active_dir / "active_file.txt").write_text("Hello active")

    excluded_dir = folder_root / "excluded_dir"
    excluded_dir.mkdir()
    (excluded_dir / "secret_file.txt").write_text("Confidential data")
    (excluded_dir / "nested_excluded").mkdir()
    (excluded_dir / "nested_excluded" / "deep.txt").write_text("Deep data")

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Storage Exclusion Test", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Exclude "excluded_dir"
    ex_res = await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions/toggle",
        json={"relative_path": "excluded_dir", "exclusion_type": "directory"},
    )
    assert ex_res.status_code == 200
    assert ex_res.json()["action"] == "added"

    # Run Storage Analysis
    analyze_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={"managed_folder_id": folder_id, "calculate_hashes": True},
    )
    assert analyze_res.status_code == 200
    result = analyze_res.json()

    # The active file should be counted, but the excluded directory and its contents omitted
    assert result["total_files_count"] == 1
    assert result["skipped_excluded_count"] >= 1
    assert any("excluded_dir" in p for p in result["skipped_excluded_paths"])


@pytest.mark.asyncio
async def test_smart_rename_skips_excluded_folders(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "RenameExclusionTest"
    folder_root.mkdir()

    (folder_root / "file1.txt").write_text("File 1")
    ex_dir = folder_root / "vendor"
    ex_dir.mkdir()
    (ex_dir / "library.js").write_text("console.log('library')")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rename Exclusion Test", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Exclude "vendor"
    await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions/toggle",
        json={"relative_path": "vendor", "exclusion_type": "directory"},
    )

    # Generate Smart Rename plan
    plan_res = await async_client.post(
        "/api/v1/smart-rename/plan",
        json={
            "managed_folder_id": folder_id,
            "strategy": "clean",
        },
    )
    assert plan_res.status_code == 201
    plan_data = plan_res.json()

    # Library inside vendor should NOT be in proposed items
    proposed_targets = [it["source_relative_path"] for it in plan_data["items"]]
    assert not any("vendor" in p for p in proposed_targets)
    # vendor should be tracked in protected_folders_skipped
    assert "vendor" in plan_data["protected_folders_skipped"]
    assert plan_data["protected_folders_skipped_count"] >= 1


@pytest.mark.asyncio
async def test_organization_skips_excluded_folders(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "OrgExclusionTest"
    folder_root.mkdir()

    (folder_root / "data.csv").write_text("col1,col2\n1,2")
    build_dir = folder_root / "build_output"
    build_dir.mkdir()
    (build_dir / "bundle.js").write_text("compiled code")

    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Org Exclusion Test", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Exclude "build_output"
    await async_client.post(
        f"/api/v1/folders/{folder_id}/exclusions/toggle",
        json={"relative_path": "build_output", "exclusion_type": "directory"},
    )

    # Generate Organization plan
    plan_res = await async_client.post(
        "/api/v1/organization/plan",
        json={
            "managed_folder_id": folder_id,
            "goal": "by_type",
        },
    )
    assert plan_res.status_code == 201
    plan_data = plan_res.json()

    # Items inside build_output should NOT be moved
    for item in plan_data["items"]:
        if item.get("source_relative_path"):
            assert not item["source_relative_path"].startswith("build_output")
    # build_output should be reported in protected_folders_skipped
    assert "build_output" in plan_data["protected_folders_skipped"]
    assert plan_data["protected_folders_skipped_count"] >= 1
