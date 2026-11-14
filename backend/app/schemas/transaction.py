from enum import Enum
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class OperationType(str, Enum):
    CREATE_DIRECTORY = "create_directory"
    RENAME = "rename"
    MOVE = "move"
    COPY = "copy"
    DELETE_TO_RECYCLE_BIN = "delete_to_recycle_bin"


class PlanType(str, Enum):
    MANUAL = "manual"
    ORGANIZE = "organize"
    RENAME = "rename"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    STALE = "stale"


class ItemStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CONFLICT = "conflict"


class ExecutionStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"
    ROLLED_BACK = "rolled_back"
    CANCELLED = "cancelled"


# Request Models
class ChangePlanItemCreate(BaseModel):
    operation: OperationType
    source_relative_path: Optional[str] = Field(
        default=None,
        description="Source path relative to managed folder root. Nullable for create_directory.",
    )
    destination_relative_path: Optional[str] = Field(
        default=None,
        description="Destination path relative to managed folder root. Nullable for delete operations.",
    )
    expected_size_bytes: Optional[int] = Field(
        default=None,
        description="Optional expected source file size in bytes to detect stale plans.",
    )
    expected_modified_at: Optional[str] = Field(
        default=None,
        description="Optional expected source modified timestamp (ISO-8601).",
    )
    expected_hash: Optional[str] = Field(
        default=None,
        description="Optional expected content hash.",
    )
    sequence_no: int = Field(default=1, description="Execution sequence order (1-based).")


class ChangePlanCreate(BaseModel):
    managed_folder_id: str
    analysis_run_id: Optional[str] = None
    title: str = Field(min_length=1, max_length=255)
    plan_type: PlanType = PlanType.MANUAL
    items: List[ChangePlanItemCreate] = Field(min_length=1)


class ChangePlanApproveRequest(BaseModel):
    approved_by: Optional[str] = "user"


class QuickFolderCreateRequest(BaseModel):
    managed_folder_id: str
    parent_relative_path: str = ""
    folder_name: str = Field(min_length=1, max_length=255)


class QuickRenameRequest(BaseModel):
    managed_folder_id: str
    source_relative_path: str = Field(min_length=1)
    new_name: str = Field(min_length=1, max_length=255)


class QuickMoveRequest(BaseModel):
    managed_folder_id: str
    source_relative_paths: List[str] = Field(min_length=1)
    destination_directory_relative_path: str = ""


class QuickCopyRequest(BaseModel):
    managed_folder_id: str
    source_relative_paths: List[str] = Field(min_length=1)
    destination_directory_relative_path: str = ""


class QuickDeleteRequest(BaseModel):
    managed_folder_id: str
    relative_paths: List[str] = Field(min_length=1)


# Validation Schema
class PlanValidationIssue(BaseModel):
    item_index: int
    sequence_no: int
    operation: str
    source_relative_path: Optional[str] = None
    destination_relative_path: Optional[str] = None
    issue_type: Literal["error", "warning", "conflict"]
    message: str


class PlanValidationSummary(BaseModel):
    is_valid: bool
    can_execute: bool
    total_items: int
    issues: List[PlanValidationIssue]


# Response Models
class OperationLogResponse(BaseModel):
    id: str
    execution_job_id: str
    change_plan_item_id: str
    operation: str
    source_path_snapshot: Optional[str] = None
    destination_path_snapshot: Optional[str] = None
    status: str
    backup_reference: Optional[str] = None
    error_message: Optional[str] = None
    started_at: str
    finished_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ChangePlanItemResponse(BaseModel):
    id: str
    change_plan_id: str
    operation: str
    source_relative_path: Optional[str] = None
    destination_relative_path: Optional[str] = None
    expected_size_bytes: Optional[int] = None
    expected_modified_at: Optional[str] = None
    expected_hash: Optional[str] = None
    status: str
    conflict_reason: Optional[str] = None
    sequence_no: int
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class ExecutionJobResponse(BaseModel):
    id: str
    change_plan_id: str
    status: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None
    created_at: str
    operations_count: int = 0
    completed_count: int = 0
    failed_count: int = 0
    operation_logs: List[OperationLogResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ChangePlanResponse(BaseModel):
    id: str
    managed_folder_id: str
    analysis_run_id: Optional[str] = None
    title: str
    plan_type: str
    status: str
    created_by: str
    approved_at: Optional[str] = None
    approved_by: Optional[str] = None
    created_at: str
    updated_at: str
    items: List[ChangePlanItemResponse] = []
    latest_execution_job: Optional[ExecutionJobResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UndoExecutionResponse(BaseModel):
    job_id: str
    reverted_count: int
    skipped_count: int
    failed_count: int
    status: str
    details: List[str] = []
