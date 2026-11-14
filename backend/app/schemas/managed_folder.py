import json
from typing import List, Optional
from pydantic import BaseModel, Field


class FolderCapabilities(BaseModel):
    organization: bool = True
    smart_rename: bool = True
    monitoring: bool = False
    analysis: bool = True
    content_extraction: bool = False


class FolderExclusionItem(BaseModel):
    id: str
    folder_id: str
    exclusion_type: str  # directory, extension, pattern, file
    value: str
    reason: Optional[str] = None
    is_enabled: bool = True
    created_at: str


class FolderExclusionCreate(BaseModel):
    exclusion_type: str = Field(..., description="directory, extension, pattern, or file")
    value: str = Field(min_length=1, max_length=1024)
    reason: Optional[str] = None


class FolderHealthCheck(BaseModel):
    folder_id: str
    folder_name: str
    root_path: str
    is_accessible: bool
    exists: bool
    can_read: bool
    can_write: bool
    is_symlink: bool
    is_reparse_point: bool
    watcher_status: str  # active, paused, stopped, disabled
    last_scanned_at: Optional[str] = None
    last_error: Optional[str] = None
    overall_status: str  # healthy, warning, error, inaccessible


class FolderUsageStats(BaseModel):
    folder_id: str
    total_size_bytes: int
    total_files_count: int
    storage_limit_bytes: Optional[int] = None
    usage_percentage: Optional[float] = None
    last_scanned_at: Optional[str] = None


class FolderSummaryCards(BaseModel):
    total_folders: int
    active_folders: int
    total_size_bytes: int
    total_files: int
    active_rules_count: int
    monitored_folders_count: int
    health_status: str  # healthy, warning, error


class ManagedFolderCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255, description="Display name for the managed folder")
    root_path: str = Field(min_length=1, max_length=1024, description="Canonical path to the directory")
    monitoring_enabled: bool = Field(default=False, description="Enable automatic filesystem monitoring")
    scan_on_startup: bool = Field(default=False, description="Opt-in scan on startup")
    exclude_patterns: List[str] = Field(default_factory=list, description="Glob patterns to exclude from scanning")
    capabilities: Optional[FolderCapabilities] = None


class ManagedFolderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    monitoring_enabled: Optional[bool] = None
    scan_on_startup: Optional[bool] = None
    exclude_patterns: Optional[List[str]] = None
    capabilities: Optional[FolderCapabilities] = None


class ManagedFolderResponse(BaseModel):
    id: str
    name: str
    root_path: str
    is_enabled: bool
    monitoring_enabled: bool
    scan_on_startup: bool
    exclude_patterns: List[str]
    capabilities: FolderCapabilities = Field(default_factory=FolderCapabilities)
    total_size_bytes: int = 0
    total_files: int = 0
    health_status: str = "healthy"
    last_scanned_at: Optional[str] = None
    created_at: str
    updated_at: str

    @classmethod
    def from_orm_model(cls, model, capabilities: Optional[FolderCapabilities] = None, size: int = 0, files_count: int = 0, health: str = "healthy") -> "ManagedFolderResponse":
        exclude_patterns: List[str] = []
        if model.exclude_patterns_json:
            try:
                exclude_patterns = json.loads(model.exclude_patterns_json)
            except Exception:
                exclude_patterns = []

        return cls(
            id=model.id,
            name=model.name,
            root_path=model.root_path,
            is_enabled=bool(model.is_enabled),
            monitoring_enabled=bool(model.monitoring_enabled),
            scan_on_startup=bool(model.scan_on_startup),
            exclude_patterns=exclude_patterns,
            capabilities=capabilities or FolderCapabilities(monitoring=bool(model.monitoring_enabled)),
            total_size_bytes=size,
            total_files=files_count,
            health_status=health,
            last_scanned_at=model.last_scanned_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
