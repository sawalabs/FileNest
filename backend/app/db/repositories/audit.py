import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from backend.app.db.models.audit import AuditLog


CATEGORY_ACTION_MAP = {
    "file_changes": [
        "quick_create_directory",
        "quick_rename",
        "quick_move",
        "quick_copy",
        "quick_delete",
        "file_created",
        "file_modified",
        "file_renamed",
        "file_moved",
        "file_copied",
        "file_deleted",
        "folder_created",
        "folder_renamed",
        "folder_moved",
        "folder_deleted",
    ],
    "plans_approvals": [
        "create_change_plan",
        "submit_plan_for_review",
        "approve_change_plan",
        "reject_change_plan",
        "batch_approve_plans",
        "batch_reject_plans",
        "analysis_started",
        "analysis_completed",
    ],
    "executions": [
        "execute_plan",
        "execute_transaction",
        "rollback_transaction",
        "execute_approved_plans",
        "execution_started",
        "execution_completed",
        "execution_failed",
        "execution_rolled_back",
    ],
    "monitoring": [
        "monitoring_started",
        "monitoring_paused",
        "monitoring_resumed",
        "monitoring_stopped",
        "watcher_created",
        "watcher_removed",
        "monitoring_event",
    ],
    "rules": [
        "rule_created",
        "rule_updated",
        "rule_approved",
        "rule_deleted",
    ],
    "system": [
        "create_managed_folder",
        "update_managed_folder",
        "remove_managed_folder",
        "scan_managed_folder",
        "system_startup",
        "system_shutdown",
    ],
}


def _sanitize_audit_data(data: Any) -> Any:
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            if any(s in str(k).lower() for s in ["api_key", "password", "token", "secret", "auth", "credential"]):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = _sanitize_audit_data(v)
        return sanitized
    elif isinstance(data, list):
        return [_sanitize_audit_data(item) for item in data]
    elif isinstance(data, str):
        if data.startswith("sk-") and len(data) > 8:
            return "***REDACTED***"
        return data
    return data


class AuditLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        actor_type: str,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> AuditLog:
        # Sensitive values must never be stored in audit logs (Rule 80 & database-design.md)
        details_clean = _sanitize_audit_data(details) if details else None
        details_json = json.dumps(details_clean) if details_clean else None
        log = AuditLog(
            actor_type=actor_type,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details_json=details_json,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def list_by_entity(self, entity_type: str, entity_id: str) -> List[AuditLog]:
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.created_at.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def _apply_filters(
        self,
        stmt,
        category: Optional[str] = None,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
    ):
        if category and category != "all":
            allowed_actions = CATEGORY_ACTION_MAP.get(category)
            if allowed_actions:
                stmt = stmt.where(AuditLog.action.in_(allowed_actions))

        if action:
            stmt = stmt.where(AuditLog.action == action)
        if actor_type:
            stmt = stmt.where(AuditLog.actor_type == actor_type)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_id:
            stmt = stmt.where(AuditLog.entity_id == entity_id)
        if start_date:
            stmt = stmt.where(AuditLog.created_at >= start_date)
        if end_date:
            stmt = stmt.where(AuditLog.created_at <= end_date)
        if search:
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            search_pattern = f"%{escaped}%"
            stmt = stmt.where(
                or_(
                    AuditLog.action.ilike(search_pattern, escape="\\"),
                    AuditLog.entity_type.ilike(search_pattern, escape="\\"),
                    AuditLog.entity_id.ilike(search_pattern, escape="\\"),
                    AuditLog.details_json.ilike(search_pattern, escape="\\"),
                )
            )
        return stmt

    def list_logs(
        self,
        category: Optional[str] = None,
        action: Optional[str] = None,
        actor_type: Optional[str] = None,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[AuditLog], int]:
        count_stmt = select(func.count(AuditLog.id))
        count_stmt = self._apply_filters(
            count_stmt,
            category=category,
            action=action,
            actor_type=actor_type,
            entity_type=entity_type,
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        total = self.db.execute(count_stmt).scalar() or 0

        query_stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
        query_stmt = self._apply_filters(
            query_stmt,
            category=category,
            action=action,
            actor_type=actor_type,
            entity_type=entity_type,
            entity_id=entity_id,
            start_date=start_date,
            end_date=end_date,
            search=search,
        )
        query_stmt = query_stmt.limit(limit).offset(offset)
        items = list(self.db.execute(query_stmt).scalars().all())

        return items, total
