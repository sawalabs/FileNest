from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MonitoringConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    recursive: Optional[bool] = True
    debounce_ms: Optional[int] = Field(default=1000, ge=100, le=10000)
    ignore_patterns: Optional[List[str]] = None


class MonitoringConfigResponse(BaseModel):
    id: str
    managed_folder_id: str
    is_enabled: bool
    recursive: bool
    debounce_ms: int
    ignore_patterns: List[str]
    created_at: str
    updated_at: str


class WatcherItemResponse(BaseModel):
    folder_id: str
    folder_name: str
    root_path: str
    status: str  # "watching", "paused", "stopped", "error", "initializing"
    is_enabled: bool
    recursive: bool
    debounce_ms: int
    ignore_patterns: List[str]
    events_count_24h: int
    last_event_at: Optional[str] = None
    error_message: Optional[str] = None


class MonitoringEventResponse(BaseModel):
    id: str
    managed_folder_id: str
    managed_folder_name: str
    event_type: str  # "created", "modified", "deleted", "moved"
    relative_path: str
    destination_relative_path: Optional[str] = None
    status: str
    occurred_at: str
    size_bytes: Optional[int] = None


class MonitoringEventListResponse(BaseModel):
    total: int
    items: List[MonitoringEventResponse]


class MonitoringSummaryStats(BaseModel):
    monitored_folders_count: int
    active_watchers_count: int
    total_events_24h: int
    files_created_count: int
    files_modified_count: int
    files_deleted_count: int
    total_change_size_bytes: int


class ActivityChartPoint(BaseModel):
    timestamp: str
    created: int
    modified: int
    deleted: int


class ActivityChartResponse(BaseModel):
    time_range: str
    data_points: List[ActivityChartPoint]


class DistributionItem(BaseModel):
    event_type: str
    count: int
    percentage: float


class DistributionResponse(BaseModel):
    total_events: int
    distribution: List[DistributionItem]

