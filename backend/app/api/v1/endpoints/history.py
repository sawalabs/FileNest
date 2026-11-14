import csv
import io
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from backend.app.api.deps import get_db, get_transaction_service
from backend.app.db.models.audit import AuditLog
from backend.app.db.models.execution import ExecutionJob
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.history import (
    AuditLogItemResponse,
    AuditLogListResponse,
    ExecutionHistoryItemResponse,
    ExecutionHistoryListResponse,
    HistorySummaryStats,
)
from backend.app.services.transaction import TransactionManagerService

router = APIRouter()


def _serialize_audit_log(log: AuditLog) -> AuditLogItemResponse:
    details: Optional[Dict[str, Any]] = None
    if log.details_json:
        try:
            details = json.loads(log.details_json)
        except Exception:
            details = {"raw": log.details_json}
    return AuditLogItemResponse(
        id=log.id,
        actor_type=log.actor_type,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        details=details,
        created_at=log.created_at,
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
def get_audit_logs(
    category: Optional[str] = Query(None, description="Category tab filter"),
    action: Optional[str] = Query(None, description="Action filter"),
    actor_type: Optional[str] = Query(None, description="Actor type: user, ai, system"),
    entity_type: Optional[str] = Query(None, description="Entity type"),
    entity_id: Optional[str] = Query(None, description="Entity ID"),
    start_date: Optional[str] = Query(None, description="Start date ISO string"),
    end_date: Optional[str] = Query(None, description="End date ISO string"),
    search: Optional[str] = Query(None, description="Free-text search in details, actions, and entities"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> AuditLogListResponse:
    """Queries persistent audit logs with filtering and pagination."""
    repo = AuditLogRepository(db)
    items, total = repo.list_logs(
        category=category,
        action=action,
        actor_type=actor_type,
        entity_type=entity_type,
        entity_id=entity_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        limit=limit,
        offset=offset,
    )
    return AuditLogListResponse(
        total=total,
        items=[_serialize_audit_log(item) for item in items],
    )


@router.get("/executions", response_model=ExecutionHistoryListResponse)
def get_execution_history(
    status: Optional[str] = Query(None, description="Execution status filter"),
    folder_id: Optional[str] = Query(None, description="Managed folder ID"),
    start_date: Optional[str] = Query(None, description="Start date ISO string"),
    end_date: Optional[str] = Query(None, description="End date ISO string"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: TransactionManagerService = Depends(get_transaction_service),
) -> ExecutionHistoryListResponse:
    """Retrieves full execution jobs, operation logs, and rollback records."""
    jobs, total = service.list_execution_jobs(
        status=status,
        folder_id=folder_id,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
    )

    items: List[ExecutionHistoryItemResponse] = []
    for job in jobs:
        plan = job.change_plan
        folder = plan.managed_folder if plan else None
        completed = sum(1 for op in job.operation_logs if op.status == "completed")
        failed = sum(1 for op in job.operation_logs if op.status == "failed")
        rolled_back = sum(1 for op in job.operation_logs if op.status == "rollback_completed")

        op_logs = [
            {
                "id": op.id,
                "operation": op.operation,
                "source_path_snapshot": op.source_path_snapshot,
                "destination_path_snapshot": op.destination_path_snapshot,
                "status": op.status,
                "backup_reference": op.backup_reference,
                "error_message": op.error_message,
                "started_at": op.started_at,
                "finished_at": op.finished_at,
            }
            for op in job.operation_logs
        ]

        items.append(
            ExecutionHistoryItemResponse(
                id=job.id,
                change_plan_id=job.change_plan_id,
                change_plan_title=plan.title if plan else "Unknown Plan",
                plan_type=plan.plan_type if plan else "manual",
                managed_folder_id=plan.managed_folder_id if plan else "",
                managed_folder_name=folder.name if folder else "Unknown Folder",
                status=job.status,
                started_at=job.started_at,
                finished_at=job.finished_at,
                error_message=job.error_message,
                created_at=job.created_at,
                operations_count=len(job.operation_logs),
                completed_count=completed,
                failed_count=failed,
                rolled_back_count=rolled_back,
                operation_logs=op_logs,
            )
        )

    return ExecutionHistoryListResponse(total=total, items=items)


@router.get("/stats", response_model=HistorySummaryStats)
def get_history_stats(
    service: TransactionManagerService = Depends(get_transaction_service),
) -> HistorySummaryStats:
    """Returns summary statistics for the history dashboard."""
    stats = service.get_history_stats()
    return HistorySummaryStats(**stats)


@router.get("/export")
def export_history(
    format: str = Query("csv", pattern="^(csv|json)$"),
    category: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    actor_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Exports activity logs as CSV or JSON format."""
    repo = AuditLogRepository(db)
    logs, _ = repo.list_logs(
        category=category,
        action=action,
        actor_type=actor_type,
        start_date=start_date,
        end_date=end_date,
        search=search,
        limit=5000,
        offset=0,
    )

    if format == "json":
        data = [
            {
                "id": log.id,
                "actor_type": log.actor_type,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "details": json.loads(log.details_json) if log.details_json else None,
                "created_at": log.created_at,
            }
            for log in logs
        ]
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": 'attachment; filename="activity_history.json"'},
        )

    # Format as CSV with Formula / DDE Injection sanitization (SEC-07)
    def _sanitize_csv_cell(val: object) -> str:
        text = "" if val is None else str(val)
        if text.startswith(("=", "+", "-", "@", "\t", "\r")):
            return f"'{text}"
        return text

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Actor", "Action", "Entity Type", "Entity ID", "Details"])
    for log in logs:
        writer.writerow([
            _sanitize_csv_cell(log.id),
            _sanitize_csv_cell(log.created_at),
            _sanitize_csv_cell(log.actor_type),
            _sanitize_csv_cell(log.action),
            _sanitize_csv_cell(log.entity_type),
            _sanitize_csv_cell(log.entity_id),
            _sanitize_csv_cell(log.details_json),
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="activity_history.csv"'},
    )

