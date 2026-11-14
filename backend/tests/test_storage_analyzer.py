import pytest
from pathlib import Path
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_storage_analyzer_full_workflow(async_client: AsyncClient, tmp_path: Path):
    folder_root = tmp_path / "StorageTestFolder"
    folder_root.mkdir()

    # 1. Create directory structure
    docs = folder_root / "docs"
    docs.mkdir()
    empty_sub = folder_root / "empty_dir"
    empty_sub.mkdir()
    deep_empty = folder_root / "docs" / "nested_empty"
    deep_empty.mkdir()

    # 2. Create normal files
    (folder_root / "note.txt").write_text("Hello text file")
    (docs / "manual.pdf").write_bytes(b"%PDF-1.4 sample PDF content" * 100)

    # 3. Create duplicate files (same size and content)
    dup_content = b"IDENTICAL DUPLICATE CONTENT FOR HASH TEST" * 50
    (folder_root / "file_a.bin").write_bytes(dup_content)
    (docs / "file_b.bin").write_bytes(dup_content)

    # 4. Create a large file (e.g. 50 KB for test with 10 KB threshold)
    large_content = b"X" * (50 * 1024)
    (folder_root / "large_archive.zip").write_bytes(large_content)

    # Snapshot modification times before analysis
    initial_mtimes = {
        p: p.stat().st_mtime
        for p in folder_root.rglob("*")
    }

    # Register folder
    reg_res = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Storage Test Folder", "root_path": str(folder_root)},
    )
    assert reg_res.status_code == 201
    folder_id = reg_res.json()["id"]

    # Trigger analysis with 10 KB threshold for large files
    analyze_res = await async_client.post(
        "/api/v1/storage/analyze",
        json={
            "managed_folder_id": folder_id,
            "large_file_threshold_bytes": 10 * 1024,
            "calculate_hashes": True,
        },
    )
    assert analyze_res.status_code == 200
    data = analyze_res.json()

    # Verify summary cards data
    assert data["managed_folder_id"] == folder_id
    assert data["total_files_count"] == 5  # note.txt, manual.pdf, file_a, file_b, large_archive.zip
    assert data["total_folders_count"] == 3  # docs, empty_dir, nested_empty

    # Verify Large files
    assert data["large_files_count"] >= 1
    large_names = [f["name"] for f in data["large_files"]]
    assert "large_archive.zip" in large_names

    # Verify Duplicates
    assert data["duplicate_groups_count"] == 1
    assert data["duplicate_files_count"] == 2
    dup_group = data["duplicate_groups"][0]
    dup_names = [f["name"] for f in dup_group["files"]]
    assert "file_a.bin" in dup_names
    assert "file_b.bin" in dup_names
    assert dup_group["potential_savings_bytes"] == len(dup_content)

    # Verify Empty folders
    empty_names = [d["name"] for d in data["empty_folders"]]
    assert "empty_dir" in empty_names
    assert "nested_empty" in empty_names

    # Verify Category distributions
    categories = [c["category"] for c in data["category_distribution"]]
    assert "document" in categories or "archive" in categories

    # Verify Recommendations generated
    assert len(data["recommendations"]) > 0

    # Verify Retrieve latest stored analysis
    get_res = await async_client.get(
        "/api/v1/storage/analysis",
        params={"folder_id": folder_id},
    )
    assert get_res.status_code == 200
    stored_data = get_res.json()
    assert stored_data["total_files_count"] == data["total_files_count"]
    assert stored_data["duplicate_groups_count"] == data["duplicate_groups_count"]

    # Verify Safety Guarantee: All files and directories remain strictly untouched
    for p, orig_mtime in initial_mtimes.items():
        assert p.exists(), f"File {p} was deleted during analysis!"
        assert p.stat().st_mtime == orig_mtime, f"File {p} was modified during analysis!"
