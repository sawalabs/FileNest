from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SpecialistType(str, Enum):
    DISK_ANALYST = "disk_analyst"
    FOLDER_ARCHITECT = "folder_architect"
    RENAME_SPECIALIST = "rename_specialist"
    DUPLICATE_ANALYST = "duplicate_analyst"
    REVIEW_AGENT = "review_agent"


# =============================================================================
# Request Schemas
# =============================================================================

class SpecialistRunRequest(BaseModel):
    managed_folder_id: str
    specialist: SpecialistType
    user_instructions: Optional[str] = None
    target_relative_path: Optional[str] = ""
    options: Dict[str, Any] = Field(default_factory=dict)
    model: Optional[str] = None


class DiskAnalystRequest(BaseModel):
    managed_folder_id: str
    user_instructions: Optional[str] = None
    large_file_threshold_mb: int = Field(default=50, ge=1)
    model: Optional[str] = None


class FolderArchitectRequest(BaseModel):
    managed_folder_id: str
    user_instructions: Optional[str] = None
    target_relative_path: str = ""
    organization_style: Optional[str] = "category"  # "category", "date", "project"
    create_draft_plan: bool = True
    model: Optional[str] = None


class RenameSpecialistRequest(BaseModel):
    managed_folder_id: str
    user_instructions: Optional[str] = None
    target_relative_path: str = ""
    naming_convention: Optional[str] = "standard"  # "standard", "date_prefix", "kebab_case"
    create_draft_plan: bool = True
    model: Optional[str] = None


class DuplicateAnalystRequest(BaseModel):
    managed_folder_id: str
    user_instructions: Optional[str] = None
    min_size_bytes: int = Field(default=1024, ge=1)
    retention_strategy: Optional[str] = "keep_oldest"  # "keep_oldest", "keep_shortest_path", "keep_newest"
    create_cleanup_plan: bool = False
    model: Optional[str] = None


class ReviewAgentRequest(BaseModel):
    plan_id: str
    user_instructions: Optional[str] = None
    model: Optional[str] = None


# =============================================================================
# Result Schemas
# =============================================================================

class WasteSourceItem(BaseModel):
    category: str
    description: str
    size_bytes: int
    count: int
    recommendation: str


class DiskAnalystResult(BaseModel):
    managed_folder_id: str
    specialist: SpecialistType = SpecialistType.DISK_ANALYST
    total_storage_bytes: int
    total_files: int
    largest_category: str
    health_score: int = Field(ge=0, le=100)
    potential_savings_bytes: int
    waste_sources: List[WasteSourceItem] = []
    actionable_recommendations: List[str] = []
    summary: str
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class FolderArchitectMoveItem(BaseModel):
    source_relative_path: str
    destination_relative_path: str
    reason: str


class FolderArchitectResult(BaseModel):
    managed_folder_id: str
    specialist: SpecialistType = SpecialistType.FOLDER_ARCHITECT
    strategy_used: str
    proposed_structure: List[str] = []
    proposed_moves: List[FolderArchitectMoveItem] = []
    moves_count: int
    plan_id: Optional[str] = None
    plan_status: Optional[str] = None
    requires_approval: bool = True
    summary: str
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class RenameMappingItem(BaseModel):
    source_relative_path: str
    original_name: str
    proposed_name: str
    reason: str


class RenameSpecialistResult(BaseModel):
    managed_folder_id: str
    specialist: SpecialistType = SpecialistType.RENAME_SPECIALIST
    strategy_used: str
    renames: List[RenameMappingItem] = []
    renames_count: int
    plan_id: Optional[str] = None
    plan_status: Optional[str] = None
    requires_approval: bool = True
    summary: str
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class DuplicateClusterItem(BaseModel):
    hash: str
    size_bytes: int
    wasted_bytes: int
    keep_file: str
    cleanup_candidates: List[str]
    retention_reason: str


class DuplicateAnalystResult(BaseModel):
    managed_folder_id: str
    specialist: SpecialistType = SpecialistType.DUPLICATE_ANALYST
    total_clusters: int
    total_duplicate_files: int
    potential_savings_bytes: int
    clusters: List[DuplicateClusterItem] = []
    plan_id: Optional[str] = None
    plan_status: Optional[str] = None
    requires_approval: bool = True
    summary: str
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)


class ReviewRiskItem(BaseModel):
    severity: str  # "LOW", "MEDIUM", "HIGH"
    category: str  # "COLLISION", "DATA_LOSS", "PATH_ESCAPE", "STALE_SOURCE"
    item_path: str
    details: str


class ReviewAgentResult(BaseModel):
    plan_id: str
    specialist: SpecialistType = SpecialistType.REVIEW_AGENT
    plan_title: str
    plan_type: str
    plan_status: str
    risk_level: str  # "LOW", "MEDIUM", "HIGH"
    total_operations: int
    destructive_operations_count: int
    risks: List[ReviewRiskItem] = []
    safety_verdict: str  # "APPROVED_RECOMMENDED", "PROCEED_WITH_CAUTION", "BLOCKED_HIGH_RISK"
    review_summary: str
    can_safely_execute: bool
    execution_time_ms: float = 0.0

    model_config = ConfigDict(from_attributes=True)

