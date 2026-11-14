from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DashboardSummaryCards(BaseModel):
    managed_folders_count: int = 0
    total_files_count: int = 0
    total_size_bytes: int = 0
    pending_changes_count: int = 0


class DashboardCategoryItem(BaseModel):
    category: str
    files_count: int = 0
    total_size_bytes: int = 0
    percentage: float = 0.0


class DashboardFolderDistributionItem(BaseModel):
    id: str
    name: str
    root_path: str
    size_bytes: int = 0
    files_count: int = 0
    percentage: float = 0.0


class DashboardManagedFolderItem(BaseModel):
    id: str
    name: str
    root_path: str
    size_bytes: int = 0
    files_count: int = 0
    is_monitoring_active: bool = False
    is_accessible: bool = True
    last_scanned_at: Optional[str] = None


class DashboardRecentActivityItem(BaseModel):
    id: str
    timestamp: str
    action: str
    actor_type: str = "system"
    entity_type: str
    entity_id: Optional[str] = None
    location: Optional[str] = None
    details: Optional[str] = None
    status: str = "success"


class DashboardRecommendationItem(BaseModel):
    id: str
    title: str
    description: str
    type: str  # "organization", "smart_rename", "duplicates", "empty_folders", "general"
    target_route: str
    impact_count: int = 0
    impact_bytes: int = 0


class DashboardJobItem(BaseModel):
    id: str
    job_name: str
    job_type: str  # "scan", "analysis", "transaction"
    status: str  # "queued", "running", "completed", "failed", "cancelled"
    progress_percent: int = 0
    folder_name: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error_message: Optional[str] = None


class DashboardStorageTrendPoint(BaseModel):
    date: str
    total_size_bytes: int = 0
    files_count: int = 0
    files_added: int = 0
    files_modified: int = 0
    files_deleted: int = 0


class DashboardOverviewResponse(BaseModel):
    summary_cards: DashboardSummaryCards
    storage_categories: List[DashboardCategoryItem] = []
    folder_distribution: List[DashboardFolderDistributionItem] = []
    managed_folders: List[DashboardManagedFolderItem] = []
    recent_activities: List[DashboardRecentActivityItem] = []
    recommendations: List[DashboardRecommendationItem] = []
    jobs: List[DashboardJobItem] = []
    storage_history: List[DashboardStorageTrendPoint] = []
    is_stale: bool = False
    last_refreshed_at: str

    model_config = ConfigDict(from_attributes=True)


class DashboardAnalyzeRequest(BaseModel):
    folder_id: Optional[str] = None
    mode: str = Field(default="metadata", description="'all', 'single', 'metadata', or 'deep'")
