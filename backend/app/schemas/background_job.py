from enum import Enum
from typing import Any, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class BackgroundJobType(str, Enum):
    STORAGE_ANALYSIS = "storage_analysis"
    SMART_RENAME = "smart_rename_plan"
    BATCH_OCR = "batch_ocr"
    ORGANIZATION = "organization_plan"
    CUSTOM_SCAN = "custom_scan"


class BackgroundJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"



class BackgroundJobCreate(BaseModel):
    job_type: BackgroundJobType
    title: str
    managed_folder_id: Optional[str] = None
    managed_folder_name: Optional[str] = None
    items_total: int = 0
    current_step: str = "Menyiapkan pekerjaan..."


class BackgroundJobUpdate(BaseModel):
    status: Optional[BackgroundJobStatus] = None
    progress: Optional[int] = Field(None, ge=0, le=100)
    current_step: Optional[str] = None
    items_processed: Optional[int] = None
    items_total: Optional[int] = None
    error_message: Optional[str] = None
    result_payload: Optional[str] = None


class BackgroundJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_type: str
    title: str
    status: str
    progress: int = 0
    current_step: str = ""
    items_total: int = 0
    items_processed: int = 0
    managed_folder_id: Optional[str] = None
    managed_folder_name: Optional[str] = None
    error_message: Optional[str] = None
    result_payload: Optional[str] = None
    cancellation_requested: bool = False
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    created_at: str
    updated_at: str


class BackgroundJobListResponse(BaseModel):
    total: int
    items: List[BackgroundJobResponse]


class BackgroundJobCancelResponse(BaseModel):
    id: str
    status: str
    message: str
