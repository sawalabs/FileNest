import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import utc_now_iso
from backend.app.db.models.change_plan import ChangePlan, ChangePlanItem
from backend.app.db.models.execution import ExecutionJob, OperationLog
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.transaction import (
    ChangePlanCreate,
    ChangePlanItemCreate,
    ExecutionJobResponse,
    OperationLogResponse,
    OperationType,
    PlanStatus,
    PlanType,
    PlanValidationIssue,
    PlanValidationSummary,
    QuickCopyRequest,
    QuickDeleteRequest,
    QuickFolderCreateRequest,
    QuickMoveRequest,
    QuickRenameRequest,
    UndoExecutionResponse,
)
from backend.app.services.filesystem import is_reparse_point_or_symlink
from backend.app.services.managed_folder import ManagedFolderException, PathValidator


class TransactionException(Exception):
    """Custom exception for filesystem transaction errors, conflicts, and validation failures."""
    pass


def send_to_recycle_bin(path: Path) -> Tuple[bool, Optional[Path]]:
    """Moves a file or directory safely to Windows Recycle Bin.
    Never permanently deletes files automatically.
    Returns:
        (success, quarantined_dest):
        - If sent to native Windows Recycle Bin, returns (True, None).
        - If fallback to local quarantine (.trash directory) was used, returns (True, quarantined_dest).
    """
    resolved = path.resolve()
    if not resolved.exists():
        raise FileNotFoundError(f"Path does not exist: {resolved}")

    # Use native Windows Shell API for reversible Recycle Bin deletion
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class SHFILEOPSTRUCTW(ctypes.Structure):
                _fields_ = [
                    ("hwnd", wintypes.HWND),
                    ("wFunc", wintypes.UINT),
                    ("pFrom", wintypes.LPCWSTR),
                    ("pTo", wintypes.LPCWSTR),
                    ("fFlags", wintypes.WORD),
                    ("fAnyOperationsAborted", wintypes.BOOL),
                    ("hNameMappings", wintypes.LPVOID),
                    ("lpszProgressTitle", wintypes.LPCWSTR),
                ]

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x0040
            FOF_NOCONFIRMATION = 0x0010
            FOF_SILENT = 0x0004
            FOF_NOERRORUI = 0x0400

            fileop = SHFILEOPSTRUCTW()
            fileop.hwnd = 0
            fileop.wFunc = FO_DELETE
            fileop.pFrom = f"{str(resolved)}\0\0"
            fileop.pTo = None
            fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI

            result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(fileop))
            if result == 0 and not resolved.exists():
                return True, None
            logger.warning(f"SHFileOperationW returned {result}, falling back to quarantine")
        except Exception as e:
            logger.warning(f"Native Windows Recycle Bin failed, using quarantine fallback: {e}")

    # Fallback to local quarantine (.trash directory)
    quarantine_dir = resolved.parent / ".trash"
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    timestamp = int(datetime.now(timezone.utc).timestamp())
    dest = quarantine_dir / f"{resolved.name}.{timestamp}.deleted"
    shutil.move(str(resolved), str(dest))
    return True, dest


class TransactionManagerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def _get_managed_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise TransactionException(f"Managed Folder '{folder_id}' not found")
        if not folder.is_enabled:
            raise TransactionException(f"Managed Folder '{folder.name}' is currently disabled")
        return folder

    # -------------------------------------------------------------------------
    # Plan Management
    # -------------------------------------------------------------------------

    def create_plan(self, payload: ChangePlanCreate, created_by: str = "user") -> ChangePlan:
        """Creates and stores a validated change plan in draft/pending status."""
        folder = self._get_managed_folder(payload.managed_folder_id)

        plan = ChangePlan(
            managed_folder_id=folder.id,
            analysis_run_id=payload.analysis_run_id,
            title=payload.title.strip(),
            plan_type=payload.plan_type.value,
            status="pending_review" if created_by == "ai" else "draft",
            created_by=created_by,
        )
        self.db.add(plan)
        self.db.flush()

        for idx, item_data in enumerate(payload.items, start=1):
            seq = item_data.sequence_no or idx
            item = ChangePlanItem(
                change_plan_id=plan.id,
                operation=item_data.operation.value,
                source_relative_path=item_data.source_relative_path,
                destination_relative_path=item_data.destination_relative_path,
                expected_size_bytes=item_data.expected_size_bytes,
                expected_modified_at=item_data.expected_modified_at,
                expected_hash=item_data.expected_hash,
                status="pending",
                sequence_no=seq,
            )
            self.db.add(item)

        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="create_change_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type=created_by,
            details={"title": plan.title, "items_count": len(payload.items)},
        )

        return plan

    def get_plan(self, plan_id: str) -> ChangePlan:
        plan = self.db.get(ChangePlan, plan_id)
        if not plan:
            raise TransactionException(f"Change Plan '{plan_id}' not found")
        return plan

    def list_plans(
        self, folder_id: Optional[str] = None, status: Optional[str] = None
    ) -> List[ChangePlan]:
        stmt = select(ChangePlan).order_by(desc(ChangePlan.created_at))
        if folder_id:
            stmt = stmt.where(ChangePlan.managed_folder_id == folder_id)
        if status:
            stmt = stmt.where(ChangePlan.status == status)
        plans = list(self.db.execute(stmt).scalars().all())

        # Automatically purge empty (0-item) unexecuted draft/pending plans so ghost records don't linger
        non_empty: List[ChangePlan] = []
        removed_any = False
        for p in plans:
            if p.status in ("draft", "pending_review") and len(p.items) == 0:
                self.db.delete(p)
                removed_any = True
            else:
                non_empty.append(p)
        if removed_any:
            self.db.commit()

        return non_empty

    def update_plan_item(
        self, plan_id: str, item_id: str, new_destination_relative_path: str
    ) -> ChangePlanItem:
        """Updates proposed destination path of a draft plan item with immediate path confinement."""
        plan = self.get_plan(plan_id)
        if plan.status not in ("draft", "pending_review"):
            raise TransactionException(f"Cannot edit items of plan in status '{plan.status}'")

        item = self.db.get(ChangePlanItem, item_id)
        if not item or item.change_plan_id != plan.id:
            raise TransactionException(f"Change Plan item '{item_id}' not found in plan '{plan_id}'")

        clean_dest = new_destination_relative_path.strip().replace("\\", "/")
        folder = self._get_managed_folder(plan.managed_folder_id)
        try:
            dest_abs = PathValidator.resolve_and_verify_scope(folder, clean_dest)
        except ManagedFolderException as e:
            raise TransactionException(f"Invalid or unsafe destination path: {str(e)}")

        item.destination_relative_path = clean_dest
        if dest_abs.exists():
            item.status = "conflict"
            item.conflict_reason = "Destination file already exists"
        else:
            item.status = "pending"
            item.conflict_reason = None

        self.db.commit()
        self.db.refresh(item)
        return item

    def delete_plan_item(self, plan_id: str, item_id: str) -> bool:
        """Removes an item from a draft change plan."""
        plan = self.get_plan(plan_id)
        if plan.status not in ("draft", "pending_review"):
            raise TransactionException(f"Cannot delete items from plan in status '{plan.status}'")

        item = self.db.get(ChangePlanItem, item_id)
        if not item or item.change_plan_id != plan.id:
            raise TransactionException(f"Change Plan item '{item_id}' not found in plan '{plan_id}'")

        self.db.delete(item)
        self.db.flush()
        self.db.refresh(plan)
        if len(plan.items) == 0:
            self.db.delete(plan)
        self.db.commit()
        return True

    def submit_plan(self, plan_id: str) -> ChangePlan:
        """Transitions draft plan to pending_review."""
        plan = self.get_plan(plan_id)
        if plan.status != "draft":
            raise TransactionException(f"Only draft plans can be submitted for review (current: '{plan.status}')")

        plan.status = "pending_review"
        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="submit_plan_for_review",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={"title": plan.title},
        )
        return plan

    # -------------------------------------------------------------------------
    # Plan Validation
    # -------------------------------------------------------------------------

    def validate_plan(self, plan_id: str) -> PlanValidationSummary:
        """Validates all operations in a Change Plan against filesystem state."""
        plan = self.get_plan(plan_id)
        folder = self._get_managed_folder(plan.managed_folder_id)

        issues: List[PlanValidationIssue] = []
        simulated_created_dirs: set[str] = set()
        simulated_created_paths: set[str] = set()
        simulated_removed_paths: set[str] = set()

        # Pre-seed simulated created directories from any create_directory operation in the plan,
        # including all their intermediate parent directories
        for it in plan.items:
            if it.operation == "create_directory" and it.destination_relative_path:
                curr_d = Path(it.destination_relative_path)
                while curr_d not in (Path("."), Path("/"), Path("")):
                    simulated_created_dirs.add(curr_d.as_posix())
                    curr_d = curr_d.parent

        for idx, item in enumerate(plan.items):
            op = item.operation
            item_has_conflict = False

            src_norm = Path(item.source_relative_path).as_posix() if item.source_relative_path else ""
            dst_norm = Path(item.destination_relative_path).as_posix() if item.destination_relative_path else ""

            # 1. Source verification
            if op in ("rename", "move", "copy", "delete_to_recycle_bin"):
                if not item.source_relative_path:
                    issues.append(
                        PlanValidationIssue(
                            item_index=idx,
                            sequence_no=item.sequence_no,
                            operation=op,
                            issue_type="error",
                            message="Source relative path is required",
                        )
                    )
                    item_has_conflict = True
                elif src_norm in simulated_removed_paths:
                    issues.append(
                        PlanValidationIssue(
                            item_index=idx,
                            sequence_no=item.sequence_no,
                            operation=op,
                            source_relative_path=item.source_relative_path,
                            issue_type="conflict",
                            message=f"Source path was already moved or deleted in a preceding step: {item.source_relative_path}",
                        )
                    )
                    item_has_conflict = True
                elif src_norm in simulated_created_paths:
                    # Valid: source exists from an earlier step in this plan
                    pass
                else:
                    try:
                        src_path = PathValidator.resolve_and_verify_scope(folder, item.source_relative_path)
                        if not src_path.exists():
                            issues.append(
                                PlanValidationIssue(
                                    item_index=idx,
                                    sequence_no=item.sequence_no,
                                    operation=op,
                                    source_relative_path=item.source_relative_path,
                                    issue_type="conflict",
                                    message=f"Source path does not exist: {item.source_relative_path}",
                                )
                            )
                            item_has_conflict = True
                        elif is_reparse_point_or_symlink(src_path):
                            issues.append(
                                PlanValidationIssue(
                                    item_index=idx,
                                    sequence_no=item.sequence_no,
                                    operation=op,
                                    source_relative_path=item.source_relative_path,
                                    issue_type="error",
                                    message="Symlinks and reparse points cannot be mutated",
                                )
                            )
                            item_has_conflict = True
                        else:
                            # Stale verification check
                            st = src_path.stat()
                            if item.expected_size_bytes is not None and st.st_size != item.expected_size_bytes:
                                issues.append(
                                    PlanValidationIssue(
                                        item_index=idx,
                                        sequence_no=item.sequence_no,
                                        operation=op,
                                        source_relative_path=item.source_relative_path,
                                        issue_type="warning",
                                        message=f"File size changed from expected {item.expected_size_bytes} to {st.st_size} bytes",
                                    )
                                )
                    except ManagedFolderException as e:
                        issues.append(
                            PlanValidationIssue(
                                item_index=idx,
                                sequence_no=item.sequence_no,
                                operation=op,
                                source_relative_path=item.source_relative_path,
                                issue_type="error",
                                message=str(e),
                            )
                        )
                        item_has_conflict = True

            # 2. Destination verification
            if op in ("create_directory", "rename", "move", "copy"):
                if not item.destination_relative_path:
                    issues.append(
                        PlanValidationIssue(
                            item_index=idx,
                            sequence_no=item.sequence_no,
                            operation=op,
                            issue_type="error",
                            message="Destination relative path is required",
                        )
                    )
                    item_has_conflict = True
                else:
                    try:
                        dst_path = PathValidator.resolve_and_verify_scope(folder, item.destination_relative_path)
                        
                        # Check case-only rename of the same file
                        is_same_file_case_rename = (
                            op in ("rename", "move")
                            and src_norm
                            and dst_norm
                            and src_norm.lower() == dst_norm.lower()
                        )

                        if is_same_file_case_rename:
                            # On Windows/case-insensitive filesystems, dst_path.exists() is True
                            # because the source file itself exists on disk.
                            # Only treat as collision if another operation in this plan created this exact path.
                            is_occupied = dst_norm.lower() in {p.lower() for p in simulated_created_paths}
                        elif op == "create_directory":
                            # Creating an already existing directory is idempotent; only conflict if it exists as a FILE
                            is_occupied = dst_path.is_file()
                        else:
                            in_sim_created = (
                                dst_norm in simulated_created_paths
                                or (os.name == "nt" and dst_norm.lower() in {p.lower() for p in simulated_created_paths})
                            )
                            exists_on_disk = dst_path.exists()
                            was_sim_removed = (
                                dst_norm in simulated_removed_paths
                                or (os.name == "nt" and dst_norm.lower() in {p.lower() for p in simulated_removed_paths})
                            )
                            is_occupied = in_sim_created or (exists_on_disk and not was_sim_removed)

                        if is_occupied:
                            issues.append(
                                PlanValidationIssue(
                                    item_index=idx,
                                    sequence_no=item.sequence_no,
                                    operation=op,
                                    destination_relative_path=item.destination_relative_path,
                                    issue_type="conflict",
                                    message=f"Destination collision: '{item.destination_relative_path}' already exists (no silent overwrite permitted)",
                                )
                            )
                            item_has_conflict = True
                        else:
                            # Check destination parent directory existence
                            parent_rel = Path(item.destination_relative_path).parent.as_posix()
                            if parent_rel not in (".", ""):
                                parent_path = (Path(folder.root_path) / parent_rel).resolve()
                                if not parent_path.exists() and parent_rel not in simulated_created_dirs:
                                    issues.append(
                                        PlanValidationIssue(
                                            item_index=idx,
                                            sequence_no=item.sequence_no,
                                            operation=op,
                                            destination_relative_path=item.destination_relative_path,
                                            issue_type="error",
                                            message=f"Destination parent folder '{parent_rel}' does not exist",
                                        )
                                    )
                                    item_has_conflict = True

                        # For move: destination cannot be nested inside source directory
                        if op == "move" and item.source_relative_path:
                            try:
                                src_p = (Path(folder.root_path) / item.source_relative_path).resolve()
                                if dst_path == src_p or src_p in dst_path.parents:
                                    issues.append(
                                        PlanValidationIssue(
                                            item_index=idx,
                                            sequence_no=item.sequence_no,
                                            operation=op,
                                            source_relative_path=item.source_relative_path,
                                            destination_relative_path=item.destination_relative_path,
                                            issue_type="error",
                                            message="Cannot move a directory into itself or a subfolder of itself",
                                        )
                                    )
                                    item_has_conflict = True
                            except Exception:
                                pass

                    except ManagedFolderException as e:
                        issues.append(
                            PlanValidationIssue(
                                item_index=idx,
                                sequence_no=item.sequence_no,
                                operation=op,
                                destination_relative_path=item.destination_relative_path,
                                issue_type="error",
                                message=str(e),
                            )
                        )
                        item_has_conflict = True

            # Update simulated state if this item did not have blocking errors
            if not item_has_conflict:
                if op == "create_directory":
                    simulated_created_dirs.add(dst_norm)
                    curr_d = Path(dst_norm).parent
                    while curr_d not in (Path("."), Path("/"), Path("")):
                        simulated_created_dirs.add(curr_d.as_posix())
                        curr_d = curr_d.parent
                    simulated_created_paths.add(dst_norm)
                elif op in ("rename", "move"):
                    simulated_removed_paths.add(src_norm)
                    simulated_created_paths.add(dst_norm)
                elif op == "copy":
                    simulated_created_paths.add(dst_norm)
                elif op == "delete_to_recycle_bin":
                    simulated_removed_paths.add(src_norm)

            # Update item status in DB
            if item_has_conflict:
                item.status = "conflict"
                conflicts = [iss.message for iss in issues if iss.sequence_no == item.sequence_no]
                item.conflict_reason = "; ".join(conflicts)
            else:
                item.status = "approved" if plan.status == "approved" else "pending"
                item.conflict_reason = None

        has_blocking_errors = any(iss.issue_type in ("error", "conflict") for iss in issues)
        if has_blocking_errors:
            if plan.status not in ("draft", "rejected"):
                plan.status = "draft"
        self.db.commit()

        return PlanValidationSummary(
            is_valid=not has_blocking_errors,
            can_execute=not has_blocking_errors and len(plan.items) > 0,
            total_items=len(plan.items),
            issues=issues,
        )

    # -------------------------------------------------------------------------
    # Approval and Rejection
    # -------------------------------------------------------------------------

    def approve_plan(self, plan_id: str, approved_by: str = "user") -> ChangePlan:
        """Approves a plan after verifying zero conflicts or safety violations."""
        plan = self.get_plan(plan_id)
        if plan.status in ("completed", "executing"):
            raise TransactionException(f"Cannot approve plan currently in status '{plan.status}'")

        validation = self.validate_plan(plan_id)
        if not validation.can_execute:
            raise TransactionException(
                f"Cannot approve plan with {len(validation.issues)} validation issues or conflicts"
            )

        plan.status = "approved"
        plan.approved_at = utc_now_iso()
        plan.approved_by = approved_by
        for item in plan.items:
            item.status = "approved"

        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="approve_change_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={"approved_by": approved_by, "items_count": len(plan.items)},
        )

        return plan

    def reject_plan(self, plan_id: str, reason: Optional[str] = None) -> ChangePlan:
        plan = self.get_plan(plan_id)
        if plan.status in ("completed", "executing"):
            raise TransactionException(f"Cannot reject plan in status '{plan.status}'")

        plan.status = "rejected"
        for item in plan.items:
            item.status = "skipped"

        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="reject_change_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={"reason": reason},
        )

        return plan

    # -------------------------------------------------------------------------
    # Deterministic Execution with Best-Effort Rollback
    # -------------------------------------------------------------------------

    def execute_plan(self, plan_id: str) -> ExecutionJob:
        """Executes an approved plan deterministically with pre-mutation revalidation
        and best-effort rollback on partial failure."""
        plan = self.get_plan(plan_id)
        folder = self._get_managed_folder(plan.managed_folder_id)

        # Pre-execution validation pass
        validation = self.validate_plan(plan_id)
        if not validation.can_execute:
            error_msgs = [
                iss.message for iss in validation.issues if iss.issue_type in ("error", "conflict")
            ]
            details_str = "; ".join(error_msgs) if error_msgs else "unresolved validation errors"
            raise TransactionException(
                f"Execution halted: plan failed pre-execution validation checks ({len(error_msgs)} issues): {details_str}"
            )

        if plan.status != "approved":
            raise TransactionException(
                f"Plan must be approved before execution (current status: '{plan.status}')."
            )

        # Create execution job
        job = ExecutionJob(
            change_plan_id=plan.id,
            status="running",
            started_at=utc_now_iso(),
        )
        self.db.add(job)
        plan.status = "executing"
        self.db.commit()
        self.db.refresh(job)

        self.audit_repo.record(
            action="execution_started",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={"title": plan.title, "job_id": job.id, "items_count": len(plan.items)},
        )

        # Rollback stack: stores executed actions in order
        rollback_stack: List[Tuple[ChangePlanItem, OperationLog, Dict[str, Any]]] = []
        execution_failed = False
        failure_error = None

        for item in plan.items:
            item.status = "executing"
            self.db.commit()

            op_log = OperationLog(
                execution_job_id=job.id,
                change_plan_item_id=item.id,
                operation=item.operation,
                source_path_snapshot=item.source_relative_path,
                destination_path_snapshot=item.destination_relative_path,
                status="started",
                started_at=utc_now_iso(),
            )
            self.db.add(op_log)
            self.db.commit()
            self.db.refresh(op_log)

            try:
                # Execute individual operation with immediate revalidation
                revert_context = self._execute_item_mutation(folder, item, op_log)
                op_log.status = "completed"
                op_log.finished_at = utc_now_iso()
                item.status = "completed"
                self.db.commit()

                rollback_stack.append((item, op_log, revert_context))
            except Exception as e:
                logger.error(f"Operation failed on item {item.id} ({item.operation}): {e}")
                op_log.status = "failed"
                op_log.error_message = str(e)
                op_log.finished_at = utc_now_iso()
                item.status = "failed"
                item.conflict_reason = str(e)
                execution_failed = True
                failure_error = str(e)
                self.db.commit()
                break

        # If an error occurred, perform best-effort rollback on completed items
        if execution_failed:
            logger.warning(f"Initiating best-effort rollback for job {job.id}...")
            rollback_success = True

            while rollback_stack:
                r_item, r_log, r_context = rollback_stack.pop()
                try:
                    self._rollback_item_mutation(folder, r_item, r_context)
                    r_log.status = "rollback_completed"
                    r_item.status = "pending"
                except Exception as r_err:
                    logger.error(f"Rollback failed for item {r_item.id}: {r_err}")
                    r_log.status = "rollback_failed"
                    r_log.error_message = f"Rollback error: {r_err}"
                    rollback_success = False
                self.db.commit()

            job.status = "rolled_back" if rollback_success else "partial"
            job.error_message = failure_error
            job.finished_at = utc_now_iso()
            plan.status = "failed"
            self.db.commit()

            self.audit_repo.record(
                action="rollback_transaction" if rollback_success else "execution_failed",
                entity_type="execution_job",
                entity_id=job.id,
                actor_type="system",
                details={
                    "plan_id": plan.id,
                    "error": failure_error,
                    "rolled_back": rollback_success,
                },
            )
        else:
            job.status = "completed"
            job.finished_at = utc_now_iso()
            plan.status = "completed"
            self.db.commit()

            self.audit_repo.record(
                action="execution_completed",
                entity_type="execution_job",
                entity_id=job.id,
                actor_type="system",
                details={"plan_id": plan.id, "items_completed": len(plan.items)},
            )

        self.db.refresh(job)
        return job

    def _execute_item_mutation(
        self, folder: ManagedFolder, item: ChangePlanItem, op_log: OperationLog
    ) -> Dict[str, Any]:
        """Executes a single filesystem mutation with strict immediate revalidation."""
        op = item.operation
        revert_context: Dict[str, Any] = {"operation": op}

        # Resolve paths with scope confinement
        src_path: Optional[Path] = None
        dst_path: Optional[Path] = None

        if item.source_relative_path:
            src_path = PathValidator.resolve_and_verify_scope(folder, item.source_relative_path)
        if item.destination_relative_path:
            dst_path = PathValidator.resolve_and_verify_scope(folder, item.destination_relative_path)

        if op == OperationType.CREATE_DIRECTORY.value:
            if not dst_path:
                raise TransactionException("Missing destination path for create_directory")
            if dst_path.is_file():
                raise TransactionException(f"Destination already exists as a file: {dst_path.name}")
            dst_path.mkdir(parents=True, exist_ok=True)
            revert_context["created_path"] = str(dst_path)

        elif op == OperationType.RENAME.value:
            if not src_path or not dst_path:
                raise TransactionException("Rename requires both source and destination paths")
            if not src_path.exists():
                raise TransactionException(f"Source file does not exist: {src_path.name}")
            
            is_same_file_case = (
                src_path.resolve() == dst_path.resolve()
                and src_path.name.lower() == dst_path.name.lower()
            )
            if dst_path.exists() and not is_same_file_case:
                raise TransactionException(f"Destination collision: '{dst_path.name}' already exists")
            src_path.rename(dst_path)
            revert_context["source_path"] = str(src_path)
            revert_context["dest_path"] = str(dst_path)

        elif op == OperationType.MOVE.value:
            if not src_path or not dst_path:
                raise TransactionException("Move requires both source and destination paths")
            if not src_path.exists():
                raise TransactionException(f"Source file does not exist: {src_path.name}")
            
            is_same_file_case = (
                src_path.resolve() == dst_path.resolve()
                and src_path.name.lower() == dst_path.name.lower()
            )
            if dst_path.exists() and not is_same_file_case:
                raise TransactionException(f"Destination collision: '{dst_path.name}' already exists")
            
            # Ensure destination directory hierarchy exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            revert_context["source_path"] = str(src_path)
            revert_context["dest_path"] = str(dst_path)

        elif op == OperationType.COPY.value:
            if not src_path or not dst_path:
                raise TransactionException("Copy requires both source and destination paths")
            if not src_path.exists():
                raise TransactionException(f"Source file does not exist: {src_path.name}")
            if dst_path.exists():
                raise TransactionException(f"Destination collision: '{dst_path.name}' already exists")
            
            # Ensure destination directory hierarchy exists
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path), symlinks=False)
            else:
                shutil.copy2(str(src_path), str(dst_path))
            revert_context["created_path"] = str(dst_path)

        elif op == OperationType.DELETE_TO_RECYCLE_BIN.value:
            if not src_path:
                raise TransactionException("Delete requires a source path")
            if not src_path.exists():
                raise TransactionException(f"Source file does not exist: {src_path.name}")
            # Safe reversible deletion
            _, quarantined_dest = send_to_recycle_bin(src_path)
            revert_context["deleted_path"] = str(src_path)
            if quarantined_dest:
                op_log.backup_reference = f"local_quarantine:{quarantined_dest}"
                revert_context["quarantined_dest"] = str(quarantined_dest)
            else:
                op_log.backup_reference = "windows_recycle_bin"

        else:
            raise TransactionException(f"Unsupported operation type: {op}")

        return revert_context

    def _rollback_item_mutation(
        self, folder: ManagedFolder, item: ChangePlanItem, context: Dict[str, Any]
    ) -> None:
        """Best-effort reversal of a completed operation."""
        op = context.get("operation")

        if op in (OperationType.CREATE_DIRECTORY.value, OperationType.COPY.value):
            target = Path(context["created_path"])
            if target.exists():
                if target.is_dir():
                    # Only delete if directory is empty or if it was a copied tree
                    if op == OperationType.CREATE_DIRECTORY.value:
                        target.rmdir()
                    else:
                        shutil.rmtree(str(target))
                else:
                    target.unlink()

        elif op in (OperationType.RENAME.value, OperationType.MOVE.value):
            src = Path(context["source_path"])
            dst = Path(context["dest_path"])
            is_same_file_case = (
                src.name.lower() == dst.name.lower()
                and src.parent.resolve() == dst.parent.resolve()
            )
            if is_same_file_case:
                dst.rename(src)
            elif dst.exists() and not src.exists():
                shutil.move(str(dst), str(src))

        elif op == OperationType.DELETE_TO_RECYCLE_BIN.value:
            quarantined = context.get("quarantined_dest")
            orig = Path(context["deleted_path"])
            if quarantined:
                q_path = Path(quarantined)
                if q_path.exists() and not orig.exists():
                    orig.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(q_path), str(orig))
                    logger.info(f"Rollback restored file from local quarantine: '{q_path}' -> '{orig}'")
                    self.audit_repo.record(
                        action="rollback_restore_from_quarantine",
                        entity_type="file",
                        entity_id=item.id,
                        actor_type="system",
                        details={
                            "quarantined_path": str(q_path),
                            "restored_path": str(orig),
                            "change_plan_id": item.change_plan_id,
                            "managed_folder_id": folder.id,
                        },
                    )
                    # Clean up .trash folder if empty
                    try:
                        if q_path.parent.name == ".trash" and not any(q_path.parent.iterdir()):
                            q_path.parent.rmdir()
                    except Exception:
                        pass
                else:
                    logger.warning(
                        f"Could not restore from quarantine: q_path exists={q_path.exists()}, orig exists={orig.exists()}"
                    )
            else:
                # Files in native Recycle Bin cannot be programmatically restored safely
                logger.info(f"Rollback note: File '{context.get('deleted_path')}' is in Windows Recycle Bin")

    def undo_execution_job(self, job_id: str) -> UndoExecutionResponse:
        """Safely reverts a completed execution job in reverse operation order without overwriting existing files."""
        job = self.get_execution_job(job_id)
        if job.status not in ("completed", "partial"):
            raise TransactionException(
                f"Execution job '{job_id}' cannot be undone from status '{job.status}'."
            )

        plan = self.get_plan(job.change_plan_id)
        folder = self._get_managed_folder(plan.managed_folder_id)

        op_logs = list(
            self.db.execute(
                select(OperationLog)
                .where(OperationLog.execution_job_id == job.id)
                .order_by(OperationLog.started_at.desc(), OperationLog.id.desc())
            )
            .scalars()
            .all()
        )

        # Also respect ChangePlanItem sequence order if available
        item_seq = {it.id: it.sequence_no for it in plan.items}
        op_logs.sort(key=lambda l: item_seq.get(l.change_plan_item_id, 0), reverse=True)

        reverted_count = 0
        skipped_count = 0
        failed_count = 0
        details: List[str] = []

        for op_log in op_logs:
            if op_log.status != "completed":
                skipped_count += 1
                continue

            op = op_log.operation
            src_rel = op_log.source_path_snapshot
            dst_rel = op_log.destination_path_snapshot

            try:
                src_abs = PathValidator.resolve_and_verify_scope(folder, src_rel) if src_rel else None
                dst_abs = PathValidator.resolve_and_verify_scope(folder, dst_rel) if dst_rel else None

                if op in (OperationType.MOVE.value, OperationType.RENAME.value):
                    if not src_abs or not dst_abs:
                        skipped_count += 1
                        details.append(f"Skipped {op}: missing path snapshot.")
                        continue
                    is_same_file_case = (
                        src_abs.name.lower() == dst_abs.name.lower()
                        and src_abs.parent.resolve() == dst_abs.parent.resolve()
                    )
                    if not dst_abs.exists():
                        skipped_count += 1
                        details.append(f"Skipped {op} '{dst_rel}': destination no longer exists.")
                        continue
                    if src_abs.exists() and not is_same_file_case:
                        skipped_count += 1
                        details.append(f"Skipped {op} '{dst_rel}' -> '{src_rel}': original source path already occupied.")
                        continue
                    src_abs.parent.mkdir(parents=True, exist_ok=True)
                    if is_same_file_case:
                        dst_abs.rename(src_abs)
                    else:
                        shutil.move(str(dst_abs), str(src_abs))
                    op_log.status = "rollback_completed"
                    reverted_count += 1
                    details.append(f"Reverted {op}: '{dst_rel}' -> '{src_rel}'.")

                elif op == OperationType.COPY.value:
                    if not dst_abs or not dst_abs.exists():
                        skipped_count += 1
                        details.append(f"Skipped copy '{dst_rel}': copied target no longer exists.")
                        continue
                    send_to_recycle_bin(dst_abs)
                    op_log.status = "rollback_completed"
                    reverted_count += 1
                    details.append(f"Removed copy '{dst_rel}' to Recycle Bin / quarantine.")

                elif op == OperationType.CREATE_DIRECTORY.value:
                    if not dst_abs or not dst_abs.exists() or not dst_abs.is_dir():
                        skipped_count += 1
                        details.append(f"Skipped directory '{dst_rel}': no longer exists.")
                        continue
                    if any(dst_abs.iterdir()):
                        skipped_count += 1
                        details.append(f"Skipped directory '{dst_rel}': directory is not empty.")
                        continue
                    dst_abs.rmdir()
                    op_log.status = "rollback_completed"
                    reverted_count += 1
                    details.append(f"Removed empty created directory '{dst_rel}'.")

                elif op == OperationType.DELETE_TO_RECYCLE_BIN.value:
                    backup_ref = op_log.backup_reference or ""
                    if backup_ref.startswith("local_quarantine:"):
                        q_raw = backup_ref.split("local_quarantine:", 1)[1]
                        q_path = Path(q_raw).resolve()
                        # Ensure quarantine path is also strictly inside the managed folder
                        folder_root = Path(folder.root_path).resolve()
                        if folder_root not in q_path.parents:
                            raise TransactionException("Quarantine path escapes Managed Folder boundary.")
                        if not src_abs or not q_path.exists():
                            skipped_count += 1
                            details.append(f"Skipped restore '{src_rel}': quarantined file missing.")
                            continue
                        if src_abs.exists():
                            skipped_count += 1
                            details.append(f"Skipped restore '{src_rel}': path already occupied.")
                            continue
                        src_abs.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(q_path), str(src_abs))
                        try:
                            if q_path.parent.name == ".trash" and not any(q_path.parent.iterdir()):
                                q_path.parent.rmdir()
                        except Exception:
                            pass
                        op_log.status = "rollback_completed"
                        reverted_count += 1
                        details.append(f"Restored '{src_rel}' from local quarantine.")
                    else:
                        skipped_count += 1
                        details.append(
                            f"Skipped delete '{src_rel}': stored in native Windows Recycle Bin (restore manually from Recycle Bin)."
                        )
                else:
                    skipped_count += 1
                    details.append(f"Unsupported operation '{op}' for undo.")
            except Exception as err:
                failed_count += 1
                details.append(f"Failed reverting {op} '{src_rel or dst_rel}': {str(err)}")

        if reverted_count > 0:
            job.status = "rolled_back" if failed_count == 0 else "partial"

        self.db.commit()

        self.audit_repo.record(
            action="undo_execution_job",
            entity_type="execution_job",
            entity_id=job.id,
            actor_type="user",
            details={
                "plan_id": plan.id,
                "reverted_count": reverted_count,
                "skipped_count": skipped_count,
                "failed_count": failed_count,
            },
        )

        return UndoExecutionResponse(
            job_id=job.id,
            reverted_count=reverted_count,
            skipped_count=skipped_count,
            failed_count=failed_count,
            status=job.status,
            details=details,
        )

    # -------------------------------------------------------------------------
    # Quick / Direct Actions for UI
    # -------------------------------------------------------------------------

    def quick_create_directory(self, payload: QuickFolderCreateRequest) -> ExecutionJobResponse:
        """Creates a single directory through the Transaction Manager."""
        folder = self._get_managed_folder(payload.managed_folder_id)
        parent = payload.parent_relative_path.strip().strip("/\\")
        dest_rel = f"{parent}/{payload.folder_name}".strip("/") if parent else payload.folder_name
        PathValidator.resolve_and_verify_scope(folder, dest_rel)

        plan = self.create_plan(
            ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"New Folder: {payload.folder_name}",
                plan_type=PlanType.MANUAL,
                items=[
                    ChangePlanItemCreate(
                        operation=OperationType.CREATE_DIRECTORY,
                        destination_relative_path=dest_rel,
                        sequence_no=1,
                    )
                ],
            ),
            created_by="user",
        )
        self.approve_plan(plan.id, approved_by="user")
        job = self.execute_plan(plan.id)
        return self._build_execution_response(job)

    def quick_rename(self, payload: QuickRenameRequest) -> ExecutionJobResponse:
        """Renames a file or folder through the Transaction Manager."""
        folder = self._get_managed_folder(payload.managed_folder_id)
        src_rel = payload.source_relative_path.strip().strip("/\\")
        parent = Path(src_rel).parent.as_posix()
        dst_rel = f"{parent}/{payload.new_name}".strip("/") if parent != "." else payload.new_name
        PathValidator.resolve_and_verify_scope(folder, src_rel)
        PathValidator.resolve_and_verify_scope(folder, dst_rel)

        plan = self.create_plan(
            ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Rename: {Path(src_rel).name} -> {payload.new_name}",
                plan_type=PlanType.MANUAL,
                items=[
                    ChangePlanItemCreate(
                        operation=OperationType.RENAME,
                        source_relative_path=src_rel,
                        destination_relative_path=dst_rel,
                        sequence_no=1,
                    )
                ],
            ),
            created_by="user",
        )
        self.approve_plan(plan.id, approved_by="user")
        job = self.execute_plan(plan.id)
        return self._build_execution_response(job)

    def quick_move(self, payload: QuickMoveRequest) -> ExecutionJobResponse:
        """Moves items to a destination directory through the Transaction Manager."""
        folder = self._get_managed_folder(payload.managed_folder_id)
        dest_dir = payload.destination_directory_relative_path.strip().strip("/\\")
        if dest_dir:
            PathValidator.resolve_and_verify_scope(folder, dest_dir)
        for rel in payload.source_relative_paths:
            PathValidator.resolve_and_verify_scope(folder, rel)

        items: List[ChangePlanItemCreate] = []
        for idx, src_rel in enumerate(payload.source_relative_paths, start=1):
            name = Path(src_rel).name
            dst_rel = f"{dest_dir}/{name}".strip("/") if dest_dir else name
            items.append(
                ChangePlanItemCreate(
                    operation=OperationType.MOVE,
                    source_relative_path=src_rel,
                    destination_relative_path=dst_rel,
                    sequence_no=idx,
                )
            )

        plan = self.create_plan(
            ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Move {len(items)} item(s) to {dest_dir or 'root'}",
                plan_type=PlanType.MANUAL,
                items=items,
            ),
            created_by="user",
        )
        self.approve_plan(plan.id, approved_by="user")
        job = self.execute_plan(plan.id)
        return self._build_execution_response(job)

    def quick_copy(self, payload: QuickCopyRequest) -> ExecutionJobResponse:
        """Copies items to a destination directory through the Transaction Manager."""
        folder = self._get_managed_folder(payload.managed_folder_id)
        dest_dir = payload.destination_directory_relative_path.strip().strip("/\\")
        if dest_dir:
            PathValidator.resolve_and_verify_scope(folder, dest_dir)
        for rel in payload.source_relative_paths:
            PathValidator.resolve_and_verify_scope(folder, rel)

        items: List[ChangePlanItemCreate] = []
        for idx, src_rel in enumerate(payload.source_relative_paths, start=1):
            name = Path(src_rel).name
            dst_rel = f"{dest_dir}/{name}".strip("/") if dest_dir else name
            items.append(
                ChangePlanItemCreate(
                    operation=OperationType.COPY,
                    source_relative_path=src_rel,
                    destination_relative_path=dst_rel,
                    sequence_no=idx,
                )
            )

        plan = self.create_plan(
            ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Copy {len(items)} item(s) to {dest_dir or 'root'}",
                plan_type=PlanType.MANUAL,
                items=items,
            ),
            created_by="user",
        )
        self.approve_plan(plan.id, approved_by="user")
        job = self.execute_plan(plan.id)
        return self._build_execution_response(job)

    def quick_delete(self, payload: QuickDeleteRequest) -> ExecutionJobResponse:
        """Deletes items to the Recycle Bin through the Transaction Manager."""
        folder = self._get_managed_folder(payload.managed_folder_id)
        for rel in payload.relative_paths:
            PathValidator.resolve_and_verify_scope(folder, rel)

        items: List[ChangePlanItemCreate] = []
        for idx, src_rel in enumerate(payload.relative_paths, start=1):
            items.append(
                ChangePlanItemCreate(
                    operation=OperationType.DELETE_TO_RECYCLE_BIN,
                    source_relative_path=src_rel,
                    sequence_no=idx,
                )
            )

        plan = self.create_plan(
            ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Delete {len(items)} item(s) to Recycle Bin",
                plan_type=PlanType.MANUAL,
                items=items,
            ),
            created_by="user",
        )
        self.approve_plan(plan.id, approved_by="user")
        job = self.execute_plan(plan.id)
        return self._build_execution_response(job)

    def _build_execution_response(self, job: ExecutionJob) -> ExecutionJobResponse:
        completed = sum(1 for log in job.operation_logs if log.status == "completed")
        failed = sum(1 for log in job.operation_logs if log.status == "failed")
        return ExecutionJobResponse(
            id=job.id,
            change_plan_id=job.change_plan_id,
            status=job.status,
            started_at=job.started_at,
            finished_at=job.finished_at,
            error_message=job.error_message,
            created_at=job.created_at,
            operations_count=len(job.operation_logs),
            completed_count=completed,
            failed_count=failed,
            operation_logs=[OperationLogResponse.model_validate(l) for l in job.operation_logs],
        )

    def get_execution_job(self, job_id: str) -> ExecutionJob:
        job = self.db.get(ExecutionJob, job_id)
        if not job:
            raise TransactionException(f"Execution job '{job_id}' not found")
        return job

    def execute_approved_plans(
        self, plan_ids: Optional[List[str]] = None
    ) -> List[ExecutionJob]:
        """Executes all currently approved plans, or a specific list of approved plans."""
        if plan_ids is not None:
            plans = [self.get_plan(pid) for pid in plan_ids]
        else:
            plans = self.list_plans(status="approved")

        executed_jobs: List[ExecutionJob] = []
        for plan in plans:
            if plan.status == "approved":
                job = self.execute_plan(plan.id)
                executed_jobs.append(job)
        return executed_jobs

    def batch_approve_plans(
        self, plan_ids: List[str], approved_by: str = "user"
    ) -> List[ChangePlan]:
        """Approves multiple plans in batch, validating each first."""
        approved: List[ChangePlan] = []
        for pid in plan_ids:
            plan = self.approve_plan(pid, approved_by=approved_by)
            approved.append(plan)

        self.audit_repo.record(
            action="batch_approve_plans",
            entity_type="change_plan",
            entity_id=None,
            actor_type="user",
            details={"approved_count": len(approved), "plan_ids": plan_ids},
        )
        return approved

    def batch_reject_plans(
        self, plan_ids: List[str], reason: Optional[str] = None
    ) -> List[ChangePlan]:
        """Rejects multiple plans in batch."""
        rejected: List[ChangePlan] = []
        for pid in plan_ids:
            plan = self.reject_plan(pid, reason=reason)
            rejected.append(plan)

        self.audit_repo.record(
            action="batch_reject_plans",
            entity_type="change_plan",
            entity_id=None,
            actor_type="user",
            details={"rejected_count": len(rejected), "plan_ids": plan_ids, "reason": reason},
        )
        return rejected

    def list_execution_jobs(
        self,
        status: Optional[str] = None,
        folder_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[ExecutionJob], int]:
        """Retrieves historical execution jobs with filtering and total count."""
        stmt = (
            select(ExecutionJob)
            .join(ChangePlan, ExecutionJob.change_plan_id == ChangePlan.id)
            .order_by(desc(ExecutionJob.created_at))
        )
        count_stmt = (
            select(func.count(ExecutionJob.id))
            .join(ChangePlan, ExecutionJob.change_plan_id == ChangePlan.id)
        )

        if status:
            stmt = stmt.where(ExecutionJob.status == status)
            count_stmt = count_stmt.where(ExecutionJob.status == status)
        if folder_id:
            stmt = stmt.where(ChangePlan.managed_folder_id == folder_id)
            count_stmt = count_stmt.where(ChangePlan.managed_folder_id == folder_id)
        if start_date:
            stmt = stmt.where(ExecutionJob.created_at >= start_date)
            count_stmt = count_stmt.where(ExecutionJob.created_at >= start_date)
        if end_date:
            stmt = stmt.where(ExecutionJob.created_at <= end_date)
            count_stmt = count_stmt.where(ExecutionJob.created_at <= end_date)

        total = self.db.execute(count_stmt).scalar() or 0
        stmt = stmt.limit(limit).offset(offset)
        jobs = list(self.db.execute(stmt).scalars().all())
        return jobs, total

    def get_history_stats(self) -> Dict[str, int]:
        """Computes summary metrics for the History UI dashboard."""
        from backend.app.db.models.audit import AuditLog

        total_activities = self.db.execute(select(func.count(AuditLog.id))).scalar() or 0

        file_changes_count = (
            self.db.execute(
                select(func.count(OperationLog.id)).where(OperationLog.status == "completed")
            ).scalar()
            or 0
        )

        executions_succeeded = (
            self.db.execute(
                select(func.count(ExecutionJob.id)).where(ExecutionJob.status == "completed")
            ).scalar()
            or 0
        )

        executions_failed = (
            self.db.execute(
                select(func.count(ExecutionJob.id)).where(
                    ExecutionJob.status.in_(("failed", "partial"))
                )
            ).scalar()
            or 0
        )

        rollbacks_count = (
            self.db.execute(
                select(func.count(ExecutionJob.id)).where(ExecutionJob.status == "rolled_back")
            ).scalar()
            or 0
        )

        pending_plans_count = (
            self.db.execute(
                select(func.count(ChangePlan.id)).where(
                    ChangePlan.status.in_(("draft", "pending_review"))
                )
            ).scalar()
            or 0
        )

        return {
            "total_activities": total_activities,
            "file_changes_count": file_changes_count,
            "executions_succeeded": executions_succeeded,
            "executions_failed": executions_failed,
            "rollbacks_count": rollbacks_count,
            "pending_plans_count": pending_plans_count,
        }
