import json
import shutil
import uuid
import pytest
from pathlib import Path
from unittest.mock import patch
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.db.models.audit import AuditLog
from backend.app.db.models.change_plan import ChangePlanItem
from backend.app.db.models.execution import ExecutionJob, OperationLog
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.services.transaction import (
    TransactionManagerService,
    send_to_recycle_bin,
)


# =============================================================================
# 1. Unit Tests for send_to_recycle_bin & Quarantine Fallback
# =============================================================================

def test_send_to_recycle_bin_quarantine_fallback(tmp_path: Path):
    """Verify send_to_recycle_bin returns (True, dest_path) when falling back to .trash."""
    test_file = tmp_path / "quarantine_target.txt"
    test_file.write_text("Secret document content", encoding="utf-8")

    # Mock Windows Shell API to return error code 1, triggering quarantine fallback
    with patch("ctypes.windll.shell32.SHFileOperationW", return_value=1):
        success, quarantined_dest = send_to_recycle_bin(test_file)

    assert success is True
    assert quarantined_dest is not None
    assert quarantined_dest.exists()
    assert quarantined_dest.parent.name == ".trash"
    assert "quarantine_target.txt" in quarantined_dest.name
    assert not test_file.exists()


def test_rollback_item_mutation_restores_quarantined_file(tmp_path: Path):
    """Verify _rollback_item_mutation restores a quarantined file and logs audit."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from backend.app.db.base import Base
    import backend.app.db.models  # noqa: F401

    db_file = tmp_path / "test_sec06_unit.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db: Session = TestingSession()
    try:
        service = TransactionManagerService(db)
        folder = ManagedFolder(id="f_test", name="TestFolder", root_path=str(tmp_path), is_enabled=1)

        # Create original file and move it to .trash
        orig_file = tmp_path / "doc_to_restore.txt"
        orig_file.write_text("Vital User Data", encoding="utf-8")

        with patch("ctypes.windll.shell32.SHFileOperationW", return_value=1):
            _, quarantined_dest = send_to_recycle_bin(orig_file)

        assert not orig_file.exists()
        assert quarantined_dest.exists()

        # Simulate rollback context with unique item ID
        unique_item_id = str(uuid.uuid4())
        fake_item = ChangePlanItem(
            id=unique_item_id,
            change_plan_id="plan_fake_1",
            operation="delete_to_recycle_bin",
            source_relative_path="doc_to_restore.txt",
            status="completed",
        )

        revert_context = {
            "operation": "delete_to_recycle_bin",
            "deleted_path": str(orig_file),
            "quarantined_dest": str(quarantined_dest),
        }

        # Perform rollback
        service._rollback_item_mutation(folder, fake_item, revert_context)

        # Verify file is restored to original path
        assert orig_file.exists()
        assert orig_file.read_text(encoding="utf-8") == "Vital User Data"
        assert not quarantined_dest.exists()

        # Verify audit log was recorded
        audit_log = db.execute(
            select(AuditLog).where(
                AuditLog.action == "rollback_restore_from_quarantine",
                AuditLog.entity_id == unique_item_id,
            )
        ).scalar_one_or_none()

        assert audit_log is not None
        details = json.loads(audit_log.details_json)
        assert details["restored_path"] == str(orig_file)
        assert details["quarantined_path"] == str(quarantined_dest)
    finally:
        db.close()
        test_engine.dispose()


# =============================================================================
# 2. End-to-End Multi-Item Transaction Rollback Integration Test
# =============================================================================

@pytest.mark.asyncio
async def test_multi_item_transaction_rolls_back_quarantine_fallback(
    async_client: AsyncClient, tmp_path: Path
):
    """Verify that when a multi-item plan fails during execution, the deleted file is restored from quarantine."""
    # 1. Set up managed folder with two files and destination folder
    folder_dir = tmp_path / "transaction_rollback_test"
    folder_dir.mkdir()
    dest_dir = folder_dir / "target_folder"
    dest_dir.mkdir()

    file_del = folder_dir / "to_be_deleted.txt"
    file_del.write_text("Do not lose this file on rollback!", encoding="utf-8")

    file_move = folder_dir / "to_be_moved.txt"
    file_move.write_text("Moving this file will fail mid-execution", encoding="utf-8")

    res_f = await async_client.post(
        "/api/v1/folders/register",
        json={"name": "Rollback Test Folder", "root_path": str(folder_dir)},
    )
    assert res_f.status_code in (200, 201)
    folder_id = res_f.json()["id"]

    # 2. Create a 2-step plan:
    # Item 1: delete_to_recycle_bin (will fall back to .trash)
    # Item 2: move to_be_moved.txt to target_folder/moved.txt
    plan_payload = {
        "managed_folder_id": folder_id,
        "title": "Delete and Move with Mid-execution Failure",
        "items": [
            {
                "operation": "delete_to_recycle_bin",
                "source_relative_path": "to_be_deleted.txt",
                "sequence_no": 1,
            },
            {
                "operation": "move",
                "source_relative_path": "to_be_moved.txt",
                "destination_relative_path": "target_folder/moved.txt",
                "sequence_no": 2,
            },
        ],
    }

    create_res = await async_client.post("/api/v1/transactions/plans", json=plan_payload)
    assert create_res.status_code in (200, 201)
    plan_id = create_res.json()["id"]

    # Approve the plan while all files and paths are valid
    appr_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/approve")
    assert appr_res.status_code == 200

    # 3. Simulate mid-execution failure on item 2:
    # Item 1 uses quarantine fallback in send_to_recycle_bin.
    # Item 2 raises an unexpected filesystem error during shutil.move.
    real_move = shutil.move
    def mock_move(src, dst):
        if "to_be_moved.txt" in str(src):
            raise OSError("Simulated disk I/O failure on move")
        return real_move(src, dst)

    with patch("ctypes.windll.shell32.SHFileOperationW", return_value=1), \
         patch("shutil.move", side_effect=mock_move):
        exec_res = await async_client.post(f"/api/v1/transactions/plans/{plan_id}/execute")
        assert exec_res.status_code == 200
        exec_data = exec_res.json()

        # Job must be rolled_back
        assert exec_data["status"] == "rolled_back"
        assert "Simulated disk I/O failure" in exec_data["error_message"]

    # 4. VERIFY RESTORATION:
    # The file deleted in Item 1 must have been restored from .trash back to original location!
    assert file_del.exists(), "The file was NOT restored from .trash during rollback!"
    assert file_del.read_text(encoding="utf-8") == "Do not lose this file on rollback!"

    # Verify execution job status via API
    job_res = await async_client.get(f"/api/v1/transactions/jobs/{exec_data['id']}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "rolled_back"

    # Verify plan items via API: item 1 rolled back to pending
    plan_res = await async_client.get(f"/api/v1/transactions/plans/{plan_id}")
    assert plan_res.status_code == 200
    plan_data = plan_res.json()
    assert plan_data["status"] == "failed"
    item1 = next(it for it in plan_data["items"] if it["operation"] == "delete_to_recycle_bin")
    assert item1["status"] == "pending"
