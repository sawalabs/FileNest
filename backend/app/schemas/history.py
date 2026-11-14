import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AuditLogItemResponse(BaseModel):
    id: str
    actor_type: str
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: str


class AuditLogListResponse(BaseModel):
    total: int
    items: List[AuditLogItemResponse]


class ExecutionHistoryItemResponse(BaseModel):
    id: str
    change_plan_id: str
    change_plan_title: str
    plan_type: str
    managed_folder_id: str
    managed_folder_name: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    operations_count: int
    completed_count: int
    failed_count: int
    rolled_back_count: int
    operation_logs: List[Dict[str, Any]] = Field(default_factory=list)


class ExecutionHistoryListResponse(BaseModel):
    total: int
    items: List[ExecutionHistoryItemResponse]


class HistorySummaryStats(BaseModel):
    total_activities: int
    file_changes_count: int
    executions_succeeded: int
    executions_failed: int
    rollbacks_count: int
    pending_plans_count: int


class BatchExecuteApprovedRequest(BaseModel):
    plan_ids: Optional[List[str]] = None


class BatchApprovalRequest(BaseModel):
    plan_ids: List[str]
    approved_by: Optional[str] = "user"


class BatchRejectRequest(BaseModel):
    plan_ids: List[str]
    reason: Optional[str] = None

