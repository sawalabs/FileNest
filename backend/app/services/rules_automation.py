import fnmatch
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.core.security import safe_regex_search, validate_regex_pattern
from backend.app.db.base import generate_uuid, utc_now_iso
from backend.app.db.models.execution import ExecutionJob
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.monitoring import MonitoringEvent
from backend.app.db.models.organization import OrganizationRule, RuleExecution
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.rules import (
    OrganizationRuleCreate,
    OrganizationRuleResponse,
    OrganizationRuleUpdate,
    RuleAction,
    RuleCondition,
    RuleEvaluationResult,
    RuleExecutionResponse,
    RuleScope,
)
from backend.app.schemas.transaction import (
    ChangePlanCreate,
    ChangePlanItemCreate,
    OperationType,
    PlanType,
)
from backend.app.services.filesystem import (
    detect_file_category,
    format_timestamp,
    is_hidden_item,
    is_reparse_point_or_symlink,
)
from backend.app.services.managed_folder import ManagedFolderException, PathValidator
from backend.app.services.settings_service import SettingsService
from backend.app.services.transaction import (
    TransactionException,
    TransactionManagerService,
)


class RulesAutomationException(Exception):
    """Raised for errors in rule management or automation execution."""
    pass


class RulesAutomationService:
    """Manages organization & rename rules with strict scope confinement,
    version-based approval invalidation, and collision-aware automation."""

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)
        self.transaction_service = TransactionManagerService(db)
        self.audit_repo = AuditLogRepository(db)

    def _get_active_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise RulesAutomationException(f"Managed Folder '{folder_id}' tidak ditemukan.")
        if not folder.is_enabled:
            raise RulesAutomationException(f"Managed Folder '{folder.name}' sedang dinonaktifkan.")
        return folder

    # =========================================================================
    # Rule Lifecycle & CRUD
    # =========================================================================

    def create_rule(self, payload: OrganizationRuleCreate) -> OrganizationRule:
        """Creates a new rule with version=1 and unapproved status."""
        folder = self._get_active_folder(payload.managed_folder_id)

        # Validate scope subpath if present
        if payload.scope.subpath:
            PathValidator.resolve_and_verify_scope(folder, payload.scope.subpath)

        # Validate conditions regex patterns to prevent ReDoS
        for cond in payload.conditions:
            if cond.operator == "matches_regex":
                try:
                    validate_regex_pattern(str(cond.value))
                except ValueError as err:
                    raise RulesAutomationException(f"Kondisi regex tidak valid: {str(err)}")

        rule = OrganizationRule(
            managed_folder_id=folder.id,
            name=payload.name.strip(),
            rule_type=payload.rule_type,
            scope_json=json.dumps(payload.scope.model_dump()),
            conditions_json=json.dumps([c.model_dump() for c in payload.conditions]),
            actions_json=json.dumps([a.model_dump() for a in payload.actions]),
            is_enabled=1 if payload.is_enabled else 0,
            approved_at=None,
            approved_by=None,
            version=1,
            created_at=utc_now_iso(),
            updated_at=utc_now_iso(),
        )
        self.db.add(rule)
        self.db.commit()
        self.db.refresh(rule)

        self.audit_repo.record(
            actor_type="user",
            action="create_rule",
            entity_type="organization_rule",
            entity_id=rule.id,
            details={
                "name": rule.name,
                "rule_type": rule.rule_type,
                "folder_id": folder.id,
                "version": rule.version,
            },
        )
        return rule

    def get_rule(self, rule_id: str) -> OrganizationRule:
        rule = self.db.get(OrganizationRule, rule_id)
        if not rule:
            raise RulesAutomationException(f"Rule '{rule_id}' tidak ditemukan.")
        return rule

    def list_rules(self, folder_id: Optional[str] = None) -> List[OrganizationRule]:
        stmt = select(OrganizationRule)
        if folder_id:
            stmt = stmt.where(OrganizationRule.managed_folder_id == folder_id)
        stmt = stmt.order_by(desc(OrganizationRule.created_at))
        return list(self.db.execute(stmt).scalars().all())

    def update_rule(self, rule_id: str, payload: OrganizationRuleUpdate) -> OrganizationRule:
        """Updates a rule. Changing scope, conditions, or actions increments version
        and strictly resets approval status (requiring renewed approval)."""
        rule = self.get_rule(rule_id)
        folder = self._get_active_folder(rule.managed_folder_id)

        material_change = False

        if payload.name is not None and payload.name.strip():
            rule.name = payload.name.strip()

        if payload.scope is not None:
            if payload.scope.subpath:
                PathValidator.resolve_and_verify_scope(folder, payload.scope.subpath)
            new_scope_json = json.dumps(payload.scope.model_dump())
            if new_scope_json != rule.scope_json:
                rule.scope_json = new_scope_json
                material_change = True

        if payload.conditions is not None:
            for cond in payload.conditions:
                if cond.operator == "matches_regex":
                    try:
                        validate_regex_pattern(str(cond.value))
                    except ValueError as err:
                        raise RulesAutomationException(f"Kondisi regex tidak valid: {str(err)}")
            new_cond_json = json.dumps([c.model_dump() for c in payload.conditions])
            if new_cond_json != rule.conditions_json:
                rule.conditions_json = new_cond_json
                material_change = True

        if payload.actions is not None:
            new_act_json = json.dumps([a.model_dump() for a in payload.actions])
            if new_act_json != rule.actions_json:
                rule.actions_json = new_act_json
                material_change = True

        if payload.is_enabled is not None:
            rule.is_enabled = 1 if payload.is_enabled else 0

        # CRITICAL SAFETY: Material scope or logic change invalidates prior approval
        if material_change:
            rule.version += 1
            rule.approved_at = None
            rule.approved_by = None
            logger.info(
                f"Rule '{rule.id}' scope or behavior changed. Version incremented to {rule.version}. Approval revoked."
            )

        rule.updated_at = utc_now_iso()
        self.db.commit()
        self.db.refresh(rule)

        self.audit_repo.record(
            actor_type="user",
            action="update_rule",
            entity_type="organization_rule",
            entity_id=rule.id,
            details={
                "name": rule.name,
                "version": rule.version,
                "material_change": material_change,
                "is_approved": bool(rule.approved_at),
            },
        )
        return rule

    def approve_rule(self, rule_id: str, approved_by: str = "user") -> OrganizationRule:
        """Explicitly approves a rule for its current version and exact scope."""
        rule = self.get_rule(rule_id)
        rule.approved_at = utc_now_iso()
        rule.approved_by = approved_by
        rule.updated_at = utc_now_iso()

        self.db.commit()
        self.db.refresh(rule)

        self.audit_repo.record(
            actor_type="user",
            action="approve_rule",
            entity_type="organization_rule",
            entity_id=rule.id,
            details={
                "name": rule.name,
                "approved_by": approved_by,
                "version": rule.version,
            },
        )
        return rule

    def toggle_rule(self, rule_id: str, is_enabled: bool) -> OrganizationRule:
        rule = self.get_rule(rule_id)
        rule.is_enabled = 1 if is_enabled else 0
        rule.updated_at = utc_now_iso()
        self.db.commit()
        self.db.refresh(rule)

        self.audit_repo.record(
            actor_type="user",
            action="toggle_rule",
            entity_type="organization_rule",
            entity_id=rule.id,
            details={"is_enabled": bool(rule.is_enabled)},
        )
        return rule

    def delete_rule(self, rule_id: str) -> None:
        rule = self.get_rule(rule_id)
        name = rule.name
        self.db.delete(rule)
        self.db.commit()

        self.audit_repo.record(
            actor_type="user",
            action="delete_rule",
            entity_type="organization_rule",
            entity_id=rule_id,
            details={"deleted_name": name},
        )

    # =========================================================================
    # Evaluation Engine
    # =========================================================================

    def evaluate_file(self, folder_id: str, relative_path: str) -> List[RuleEvaluationResult]:
        """Evaluates an existing file within a Managed Folder against all active rules."""
        folder = self._get_active_folder(folder_id)
        root = Path(folder.root_path).resolve()
        target_path = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target_path.exists() or target_path.is_dir():
            return []

        rules = self.list_rules(folder.id)
        results: List[RuleEvaluationResult] = []

        for rule in rules:
            if not rule.is_enabled:
                continue
            res = self._evaluate_single_rule(rule, folder, target_path, event_id=None)
            results.append(res)

        return results

    def evaluate_event(self, event: MonitoringEvent) -> List[RuleEvaluationResult]:
        """Evaluates a monitoring event (e.g. file_created, file_modified) against active rules."""
        if event.event_type not in ("created", "modified"):
            return []

        folder = self._get_active_folder(event.managed_folder_id)
        try:
            target_path = PathValidator.resolve_and_verify_scope(folder, event.relative_path)
            if not target_path.exists() or target_path.is_dir():
                return []
        except Exception:
            return []

        rules = self.list_rules(folder.id)
        results: List[RuleEvaluationResult] = []

        for rule in rules:
            if not rule.is_enabled:
                continue
            res = self._evaluate_single_rule(rule, folder, target_path, event_id=event.id)
            results.append(res)

        return results

    def _evaluate_single_rule(
        self,
        rule: OrganizationRule,
        folder: ManagedFolder,
        file_path: Path,
        event_id: Optional[str] = None,
    ) -> RuleEvaluationResult:
        """Core rule evaluation enforcing exact scope, version check, collision check, and execution routing."""
        root = Path(folder.root_path).resolve()
        rel_path = file_path.relative_to(root).as_posix()
        fname = file_path.name
        ext = file_path.suffix.lower().lstrip(".")

        from backend.app.services.organization import OrganizationService

        protected_paths = OrganizationService(self.db).get_active_protected_rel_paths(
            folder.id, auto_detect_new=False
        )
        rel_lower = rel_path.lower()
        if any(rel_lower.startswith(f"{p.lower()}/") for p in protected_paths):
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=False,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message="Berkas berada di dalam folder terlindungi (Project/Tool bundle).",
            )

        scope_dict = json.loads(rule.scope_json) if rule.scope_json else {}
        conditions_list = json.loads(rule.conditions_json) if rule.conditions_json else []
        actions_list = json.loads(rule.actions_json) if rule.actions_json else []

        # 1. Scope Confinement Check
        subpath = scope_dict.get("subpath", "").strip().rstrip("/\\")
        if subpath and not rel_path.startswith(subpath):
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=False,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message=f"Berkas berada di luar subpath scope yang ditentukan ('{subpath}').",
            )

        allowed_exts = [e.lower().lstrip(".") for e in scope_dict.get("extensions", []) if e]
        if allowed_exts and ext not in allowed_exts:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=False,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message=f"Ekstensi '{ext}' tidak masuk dalam daftar ekstensi yang disetujui {allowed_exts}.",
            )

        st = file_path.stat(follow_symlinks=False)
        f_size = st.st_size
        min_sz = scope_dict.get("min_size_bytes")
        max_sz = scope_dict.get("max_size_bytes")
        if min_sz is not None and f_size < min_sz:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=False,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message="Ukuran berkas di bawah batas minimum scope.",
            )
        if max_sz is not None and f_size > max_sz:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=False,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message="Ukuran berkas melebihi batas maksimum scope.",
            )

        # 2. Conditions Check
        file_meta = {
            "name": fname,
            "extension": ext,
            "category": detect_file_category(ext),
            "size_bytes": f_size,
        }
        for cond in conditions_list:
            field = cond.get("field", "")
            op = cond.get("operator", "equals")
            val = cond.get("value")
            actual = file_meta.get(field)

            if not self._check_condition(actual, op, val):
                return RuleEvaluationResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    file_path=rel_path,
                    matched=False,
                    eligible_for_auto_execution=False,
                    execution_status="skipped",
                    message=f"Kondisi {field} {op} {val} tidak terpenuhi.",
                )

        # 3. Actions & Target Path Computation
        if not actions_list:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=True,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message="Tidak ada aksi terkonfigurasi pada rule ini.",
            )

        primary_action = actions_list[0]
        act_type = primary_action.get("action_type", "move")
        target_dir = primary_action.get("target_directory", "").strip().strip("/\\")

        if act_type == "move":
            dest_rel = f"{target_dir}/{fname}" if target_dir else fname
            operation = OperationType.MOVE
        elif act_type == "rename":
            pattern = primary_action.get("naming_pattern", "{name}")
            parent = Path(rel_path).parent.as_posix()
            stem = file_path.stem
            date_str = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d")

            new_name = pattern.replace("{name}", stem).replace("{date}", date_str)
            if not new_name.endswith(file_path.suffix):
                new_name = f"{new_name}{file_path.suffix}"

            dest_rel = new_name if parent in (".", "") else f"{parent}/{new_name}"
            operation = OperationType.RENAME
        else:
            dest_rel = rel_path
            operation = OperationType.MOVE

        if rel_path == dest_rel:
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=True,
                eligible_for_auto_execution=False,
                execution_status="skipped",
                message="Berkas sudah berada di lokasi atau nama target.",
            )

        # Validate destination confinement
        dest_full = PathValidator.resolve_and_verify_scope(folder, dest_rel)

        # 4. COLLISION CHECK (Rule Constraint 4 & Rule 80)
        has_collision = dest_full.exists()
        is_rule_approved = bool(rule.approved_at)
        org_settings = self.settings_service.get_organization_settings()
        automation_enabled = org_settings.enable_approved_rule_automation

        # If collision exists OR rule is not approved -> Send to Review Changes!
        if has_collision or not is_rule_approved or not automation_enabled:
            reason = ""
            if has_collision:
                reason = f"Tabrakan tujuan terdeteksi: '{dest_rel}' sudah ada di disk. Dialihkan ke Review Changes."
            elif not is_rule_approved:
                reason = "Rule belum disetujui untuk eksekusi otomatis. Proposal dialihkan ke Review Changes."
            else:
                reason = "Otomasi rule dinonaktifkan dalam Settings. Proposal dialihkan ke Review Changes."

            # Create Draft Change Plan in pending_review status
            plan_items = self._build_plan_items(root, operation, rel_path, dest_rel)
            create_payload = ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Review Operasi Otomasi: {rule.name}",
                plan_type=PlanType.ORGANIZE if rule.rule_type == "organize" else PlanType.RENAME,
                items=plan_items,
            )
            draft_plan = self.transaction_service.create_plan(create_payload, created_by="ai")

            self._record_execution(
                rule_id=rule.id,
                event_id=event_id,
                rule_version=rule.version,
                status="pending_review",
                reason=reason,
            )

            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=True,
                eligible_for_auto_execution=False,
                execution_status="routed_to_review",
                plan_id=draft_plan.id,
                message=reason,
            )

        # 5. Deterministic Automatic Execution for 100% Approved & Safe Rules
        try:
            # Create approved plan and execute it safely via Transaction Manager
            plan_items = self._build_plan_items(root, operation, rel_path, dest_rel)
            create_payload = ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Otomasi Approved Rule: {rule.name} (v{rule.version})",
                plan_type=PlanType.ORGANIZE if rule.rule_type == "organize" else PlanType.RENAME,
                items=plan_items,
            )
            auto_plan = self.transaction_service.create_plan(create_payload, created_by="user")
            self.transaction_service.approve_plan(auto_plan.id, approved_by=f"rule:{rule.name}:v{rule.version}")
            job = self.transaction_service.execute_plan(auto_plan.id)

            self._record_execution(
                rule_id=rule.id,
                event_id=event_id,
                job_id=job.id,
                rule_version=rule.version,
                status="executed",
                reason=f"Dieksekusi otomatis dalam scope terverifikasi '{rule.name}'.",
            )

            self.audit_repo.record(
                actor_type="system",
                action="rule_executed",
                entity_type="organization_rule",
                entity_id=rule.id,
                details={
                    "file": rel_path,
                    "destination": dest_rel,
                    "version": rule.version,
                    "job_id": job.id,
                },
            )

            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=True,
                eligible_for_auto_execution=True,
                execution_status="executed",
                plan_id=auto_plan.id,
                message=f"Operasi berhasil dieksekusi otomatis: {rel_path} -> {dest_rel}",
            )
        except Exception as e:
            logger.error(f"Rule automatic execution error: {e}", exc_info=True)
            self._record_execution(
                rule_id=rule.id,
                event_id=event_id,
                rule_version=rule.version,
                status="failed",
                reason=f"Gagal saat eksekusi transaksi: {str(e)}",
            )
            return RuleEvaluationResult(
                rule_id=rule.id,
                rule_name=rule.name,
                file_path=rel_path,
                matched=True,
                eligible_for_auto_execution=True,
                execution_status="failed",
                message=f"Kegagalan eksekusi transaksi otomatis: {str(e)}",
            )

    def _build_plan_items(
        self,
        root: Path,
        operation: OperationType,
        rel_path: str,
        dest_rel: str,
    ) -> List[ChangePlanItemCreate]:
        """Prepares plan items, ensuring any missing destination directories are created first."""
        items: List[ChangePlanItemCreate] = []
        seq = 1

        parent = Path(dest_rel).parent
        missing_dirs: List[str] = []
        curr = parent
        while curr.as_posix() not in (".", ""):
            p_full = (root / curr).resolve()
            if not p_full.exists():
                missing_dirs.append(curr.as_posix())
            curr = curr.parent
        missing_dirs.reverse()

        for m_dir in missing_dirs:
            items.append(
                ChangePlanItemCreate(
                    operation=OperationType.CREATE_DIRECTORY,
                    destination_relative_path=m_dir,
                    sequence_no=seq,
                )
            )
            seq += 1

        items.append(
            ChangePlanItemCreate(
                operation=operation,
                source_relative_path=rel_path,
                destination_relative_path=dest_rel,
                sequence_no=seq,
            )
        )
        return items

    def _check_condition(self, actual: Any, operator: str, expected: Any) -> bool:
        if actual is None:
            return False

        if operator == "equals":
            return str(actual).lower() == str(expected).lower()
        elif operator == "contains":
            return str(expected).lower() in str(actual).lower()
        elif operator == "starts_with":
            return str(actual).lower().startswith(str(expected).lower())
        elif operator == "ends_with":
            return str(actual).lower().endswith(str(expected).lower())
        elif operator == "matches_regex":
            return safe_regex_search(str(expected), str(actual), timeout_seconds=0.5)
        elif operator == "in":
            if isinstance(expected, list):
                return str(actual).lower() in [str(x).lower() for x in expected]
            return False
        elif operator == "greater_than":
            try:
                return float(actual) > float(expected)
            except Exception:
                return False
        elif operator == "less_than":
            try:
                return float(actual) < float(expected)
            except Exception:
                return False
        return False

    def _record_execution(
        self,
        rule_id: str,
        rule_version: int,
        status: str,
        reason: Optional[str] = None,
        event_id: Optional[str] = None,
        job_id: Optional[str] = None,
    ) -> RuleExecution:
        record = RuleExecution(
            organization_rule_id=rule_id,
            monitoring_event_id=event_id,
            execution_job_id=job_id,
            rule_version=rule_version,
            status=status,
            reason=reason,
            created_at=utc_now_iso(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def list_executions(
        self, rule_id: Optional[str] = None, limit: int = 50
    ) -> List[RuleExecution]:
        stmt = select(RuleExecution)
        if rule_id:
            stmt = stmt.where(RuleExecution.organization_rule_id == rule_id)
        stmt = stmt.order_by(desc(RuleExecution.created_at)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    # =========================================================================
    # Model Conversion Helpers
    # =========================================================================

    def to_rule_response(self, rule: OrganizationRule) -> OrganizationRuleResponse:
        scope_data = json.loads(rule.scope_json) if rule.scope_json else {}
        conditions_data = json.loads(rule.conditions_json) if rule.conditions_json else []
        actions_data = json.loads(rule.actions_json) if rule.actions_json else []

        return OrganizationRuleResponse(
            id=rule.id,
            managed_folder_id=rule.managed_folder_id,
            name=rule.name,
            rule_type=rule.rule_type,
            scope=RuleScope(**scope_data),
            conditions=[RuleCondition(**c) for c in conditions_data],
            actions=[RuleAction(**a) for a in actions_data],
            is_enabled=bool(rule.is_enabled),
            approved_at=rule.approved_at,
            approved_by=rule.approved_by,
            is_approved=bool(rule.approved_at),
            version=rule.version,
            created_at=rule.created_at,
            updated_at=rule.updated_at,
        )

    def to_execution_response(self, execution: RuleExecution) -> RuleExecutionResponse:
        rule_name = execution.organization_rule.name if execution.organization_rule else "Unknown Rule"
        return RuleExecutionResponse(
            id=execution.id,
            organization_rule_id=execution.organization_rule_id,
            rule_name=rule_name,
            monitoring_event_id=execution.monitoring_event_id,
            execution_job_id=execution.execution_job_id,
            rule_version=execution.rule_version,
            status=execution.status,
            reason=execution.reason,
            created_at=execution.created_at,
        )
