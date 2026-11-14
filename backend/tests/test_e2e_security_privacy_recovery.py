import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Generator

import pytest
from httpx import AsyncClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.app.core.config import settings
from backend.app.core.logging import SensitiveDataFilter
from backend.app.db.base import Base
from backend.app.db.models.app_setting import AppSetting
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.change_plan import ChangePlan, ChangePlanItem
from backend.app.db.models.execution import ExecutionJob, OperationLog
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.transaction import (
    ChangePlanCreate,
    ChangePlanItemCreate,
    OperationType,
    PlanType,
)
from backend.app.services.credential_service import CredentialService
from backend.app.services.managed_folder import ManagedFolderException, PathValidator
from backend.app.services.mcp_service import MCPService
from backend.app.services.transaction import (
    TransactionException,
    TransactionManagerService,
)


@pytest.fixture
def db(tmp_path: Path) -> Generator[Session, None, None]:
    """Provides a fresh SQLite test database with foreign keys enabled."""
    db_file = tmp_path / "test_e2e_sec.db"
    engine = create_engine(f"sqlite:///{db_file}")

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def secure_folder(tmp_path: Path, db: Session) -> ManagedFolder:
    folder_dir = (tmp_path / "secure_managed_dir").resolve()
    folder_dir.mkdir(parents=True, exist_ok=True)
    folder = ManagedFolder(
        name="Secure E2E Folder",
        root_path=str(folder_dir),
        is_enabled=1,
        monitoring_enabled=0,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


# ==============================================================================
# Checklist Item 1: Path Traversal, Reparse Points, Collisions, and TOCTOU
# ==============================================================================
def test_path_traversal_and_reparse_point_rejection(db: Session, secure_folder: ManagedFolder):
    """Validates that traversal attempts and reparse points are strictly rejected."""
    # 1. Traversal escapes
    for bad in ["../outside.txt", "..\\outside.txt", "/etc/shadow", "C:\\Windows\\cmd.exe"]:
        with pytest.raises(ManagedFolderException, match="(escapes Managed Folder root|cannot be an absolute path)"):
            PathValidator.resolve_and_verify_scope(secure_folder, bad)

    # 2. Collision detection prevents silent overwrites
    root = Path(secure_folder.root_path)
    (root / "source.txt").write_text("Source Data")
    (root / "existing_dest.txt").write_text("Dest Data (Must not be overwritten)")

    tx_service = TransactionManagerService(db)
    plan_payload = ChangePlanCreate(
        managed_folder_id=secure_folder.id,
        title="Collision Prevention Plan",
        plan_type=PlanType.MANUAL,
        items=[
            ChangePlanItemCreate(
                operation=OperationType.RENAME,
                source_relative_path="source.txt",
                destination_relative_path="existing_dest.txt",
                sequence_no=1,
            )
        ],
    )
    plan = tx_service.create_plan(plan_payload, created_by="user")
    val = tx_service.validate_plan(plan.id)
    assert val.can_execute is False
    assert any("already exists" in iss.message for iss in val.issues)

    # Destination data is completely intact
    assert (root / "existing_dest.txt").read_text() == "Dest Data (Must not be overwritten)"


def test_toctou_premutation_validation_halts_execution(db: Session, secure_folder: ManagedFolder):
    """Verifies TOCTOU protection: if a file is deleted or modified externally after plan
    approval, execution is immediately halted before mutations occur."""
    root = Path(secure_folder.root_path)
    src_file = root / "toctou_source.txt"
    src_file.write_text("Original valid content")

    tx_service = TransactionManagerService(db)
    plan_payload = ChangePlanCreate(
        managed_folder_id=secure_folder.id,
        title="TOCTOU Verification Plan",
        plan_type=PlanType.MANUAL,
        items=[
            ChangePlanItemCreate(
                operation=OperationType.RENAME,
                source_relative_path="toctou_source.txt",
                destination_relative_path="toctou_target.txt",
                sequence_no=1,
            )
        ],
    )
    plan = tx_service.create_plan(plan_payload, created_by="user")
    tx_service.approve_plan(plan.id, approved_by="user")

    # Simulate external deletion before execution (TOCTOU change)
    src_file.unlink()
    assert not src_file.exists()

    # Execution must fail and raise TransactionException
    with pytest.raises(TransactionException, match="(failed pre-execution validation|does not exist)"):
        tx_service.execute_plan(plan.id)

    # Target was never created
    assert not (root / "toctou_target.txt").exists()


# ==============================================================================
# Checklist Item 2: Permissions, Failure Handling, and Best-Effort Rollback
# ==============================================================================
def test_partial_failure_initiates_rollback_and_preserves_data(db: Session, secure_folder: ManagedFolder):
    """Verifies that a failure during a multi-operation plan rolls back previously completed
    operations and restores original files on disk."""
    root = Path(secure_folder.root_path)
    src1 = root / "step1_src.txt"
    src2 = root / "step2_src.txt"
    src1.write_text("Step 1 Original Content")
    src2.write_text("Step 2 Original Content")

    tx_service = TransactionManagerService(db)
    plan_payload = ChangePlanCreate(
        managed_folder_id=secure_folder.id,
        title="Multi-step Rollback Test Plan",
        plan_type=PlanType.MANUAL,
        items=[
            ChangePlanItemCreate(
                operation=OperationType.RENAME,
                source_relative_path="step1_src.txt",
                destination_relative_path="step1_dest.txt",
                sequence_no=1,
            ),
            ChangePlanItemCreate(
                operation=OperationType.RENAME,
                source_relative_path="step2_src.txt",
                destination_relative_path="step2_dest.txt",
                sequence_no=2,
            ),
        ],
    )
    plan = tx_service.create_plan(plan_payload, created_by="user")
    tx_service.approve_plan(plan.id, approved_by="user")

    # Mock step 2 failure during actual execution loop (e.g. unexpected I/O or permission error)
    original_execute_mutation = tx_service._execute_item_mutation

    def mock_mutation(folder, item, op_log):
        if item.source_relative_path == "step2_src.txt":
            raise OSError("Simulated hardware I/O or permissions error during step 2")
        return original_execute_mutation(folder, item, op_log)

    tx_service._execute_item_mutation = mock_mutation

    # Execute plan: step 1 succeeds on disk, step 2 raises OSError -> rollback triggers
    job = tx_service.execute_plan(plan.id)
    assert job.status in ("failed", "rolled_back")

    # Step 1 MUST be rolled back to step1_src.txt!
    assert src1.exists()
    assert src1.read_text() == "Step 1 Original Content"
    assert not (root / "step1_dest.txt").exists()

    # Original step 2 source remains intact
    assert src2.exists()
    assert src2.read_text() == "Step 2 Original Content"


# ==============================================================================
# Checklist Item 3: Credential and Sensitive Data Redaction
# ==============================================================================
def test_sensitive_credentials_never_in_sqlite_or_logs(db: Session):
    """Verifies that Windows Credential Manager is the exclusive store for secrets and
    audit logs sanitize all sensitive tokens."""
    raw_secret = "sk-test-dummy-model-api-key-112233"

    # Store via CredentialService
    CredentialService.set_secret("test_live_key", raw_secret)
    retrieved = CredentialService.get_secret("test_live_key")
    assert retrieved == raw_secret

    # Verify audit log sanitization
    audit_repo = AuditLogRepository(db)
    log = audit_repo.record(
        actor_type="user",
        action="update_ai_credentials",
        entity_type="settings",
        entity_id="ai",
        details={
            "router_endpoint": "http://127.0.0.1:20128/v1",
            "api_key": raw_secret,
            "nested": {"token": raw_secret, "info": "safe_data"},
        },
    )

    # In SQLite details_json, raw secret MUST be redacted
    assert raw_secret not in log.details_json
    assert "***REDACTED***" in log.details_json

    # Test logging filter
    import logging
    filter_instance = SensitiveDataFilter()
    dummy_record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg=f"Calling 9Router with key: {raw_secret} and Bearer {raw_secret}",
        args=(), exc_info=None,
    )
    filter_instance.filter(dummy_record)
    assert raw_secret not in dummy_record.msg
    assert "***REDACTED***" in dummy_record.msg


# ==============================================================================
# Checklist Item 4: Audit Integrity and Restricted Agent/Tool Permissions
# ==============================================================================
def test_restricted_agent_tools_and_approval_boundaries(db: Session, secure_folder: ManagedFolder):
    """Verifies that MCP tools reject all dangerous tools, enforce advisory status,
    and prevent execution without Transaction Manager approval."""
    mcp_service = MCPService(db)

    # 1. Dangerous tools must be rejected
    for dangerous in ["shell_exec", "run_command", "bash", "cmd", "delete_file", "write_file", "execute_plan"]:
        res = mcp_service.call_tool(dangerous, {})
        assert res.is_error is True
        assert "Akses ditolak" in res.error_message or "tidak diizinkan" in res.error_message

    # 2. Plan creation is advisory only
    root = Path(secure_folder.root_path)
    (root / "advisor_doc.txt").write_text("Advisory Document")

    out = mcp_service.call_tool(
        "plan_create_rename",
        {
            "managed_folder_id": secure_folder.id,
            "title": "Advisory Rename",
            "renames": [
                {
                    "source_relative_path": "advisor_doc.txt",
                    "new_file_name": "renamed_advisor_doc.txt",
                }
            ],
        },
    )
    assert out.is_error is False
    assert out.data["status"] in ("draft", "pending_review")
    assert out.data["requires_approval"] is True

    # File on disk remains unchanged
    assert (root / "advisor_doc.txt").exists()
    assert not (root / "renamed_advisor_doc.txt").exists()

    # 3. Audit trail records the change plan created by AI
    audit_logs = db.query(AuditLog).filter(AuditLog.action == "create_change_plan", AuditLog.actor_type == "ai").all()
    assert len(audit_logs) >= 1
    assert audit_logs[0].actor_type == "ai"
