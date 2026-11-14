from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class LargeFileItem(BaseModel):
    managed_folder_id: Optional[str] = None
    name: str
    relative_path: str
    size_bytes: int
    category: str
    extension: Optional[str] = None
    modified_at: Optional[str] = None


class DuplicateFileItem(BaseModel):
    managed_folder_id: Optional[str] = None
    name: str
    relative_path: str
    size_bytes: int
    modified_at: Optional[str] = None


class DuplicateGroup(BaseModel):
    hash: str
    size_bytes: int
    files_count: int
    potential_savings_bytes: int
    files: List[DuplicateFileItem]


class EmptyFolderItem(BaseModel):
    managed_folder_id: Optional[str] = None
    name: str
    relative_path: str
    modified_at: Optional[str] = None


class CategoryDistribution(BaseModel):
    category: str
    files_count: int
    total_size_bytes: int
    percentage: float


class FileTypeStats(BaseModel):
    category: str
    extension: str
    files_count: int
    total_size_bytes: int
    percentage: float


class LargestFolderItem(BaseModel):
    managed_folder_id: Optional[str] = None
    name: str
    relative_path: str
    total_size_bytes: int
    files_count: int
    percentage: float


class StorageRecommendation(BaseModel):
    id: str
    title: str
    description: str
    target_tab: str
    impact_bytes: int = 0
    count: int = 0


class StorageUsageTrendPoint(BaseModel):
    date: str
    total_size_bytes: int


class StorageAnalysisResult(BaseModel):
    managed_folder_id: Optional[str] = None
    managed_folder_name: str
    analyzed_at: str
    total_storage_bytes: int = 0
    total_files_count: int = 0
    total_folders_count: int = 0
    large_files_count: int = 0
    large_files_bytes: int = 0
    large_files_percentage: float = 0.0
    duplicate_groups_count: int = 0
    duplicate_files_count: int = 0
    potential_savings_bytes: int = 0
    empty_folders_count: int = 0
    category_distribution: List[CategoryDistribution] = []
    file_types: List[FileTypeStats] = []
    largest_folders: List[LargestFolderItem] = []
    recommendations: List[StorageRecommendation] = []
    large_files: List[LargeFileItem] = []
    duplicate_groups: List[DuplicateGroup] = []
    empty_folders: List[EmptyFolderItem] = []
    trend_points: List[StorageUsageTrendPoint] = []

    model_config = ConfigDict(from_attributes=True)


class StorageAnalysisRequest(BaseModel):
    managed_folder_id: Optional[str] = Field(
        default=None,
        description="ID of specific Managed Folder to analyze, or None to analyze all managed folders.",
    )
    large_file_threshold_bytes: int = Field(
        default=100 * 1024 * 1024,
        description="Minimum file size in bytes to classify as large file (default 100 MB).",
    )
    calculate_hashes: bool = Field(
        default=True,
        description="Whether to calculate content hashes for duplicate candidate files.",
    )


class StorageCleanupItemInput(BaseModel):
    managed_folder_id: str
    relative_path: str = Field(min_length=1)
    reason: Optional[str] = None


class StorageCleanupPlanRequest(BaseModel):
    cleanup_type: Literal["duplicates", "large_files", "empty_folders"] = "duplicates"
    title: Optional[str] = None
    items: List[StorageCleanupItemInput] = Field(min_length=1)


class StorageCleanupPlanResponse(BaseModel):
    created_plan_ids: List[str]
    total_items_queued: int
    message: str
