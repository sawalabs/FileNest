from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class OrganizationPlanRequest(BaseModel):
    managed_folder_id: str
    target_subfolder: Optional[str] = Field(
        default="",
        description="Relative subfolder within the managed folder to organize, or empty string for root.",
    )
    strategy: str = Field(
        default="by_category",
        description="Organization strategy: 'by_category', 'by_date', 'by_extension', 'by_project', 'custom'.",
    )
    custom_rules: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Custom rules or instructions for organization.",
    )
    include_subfolders: bool = Field(
        default=True,
        description="Whether to scan and organize subfolders recursively.",
    )
    move_unorganized_only: bool = Field(
        default=True,
        description="Skip files that are already located in an appropriately organized folder.",
    )
    title: Optional[str] = Field(
        default=None,
        description="Custom title for the generated Change Plan.",
    )


class StructureTreeNode(BaseModel):
    name: str
    relative_path: str
    item_type: str  # "directory" or "file"
    files_count: int = 0
    size_bytes: int = 0
    is_new: bool = False
    children: List["StructureTreeNode"] = []


class ProposedChangeItem(BaseModel):
    item_id: Optional[str] = None
    sequence_no: int
    operation: str  # "create_directory", "move"
    source_relative_path: Optional[str] = None
    destination_relative_path: str
    file_name: str
    size_bytes: int = 0
    category: Optional[str] = None
    status: str = "pending"  # "pending", "conflict", "skipped"
    conflict_reason: Optional[str] = None


class OrganizationPlanResult(BaseModel):
    change_plan_id: str
    managed_folder_id: str
    managed_folder_name: str
    strategy: str
    title: str
    status: str
    created_at: str

    # Summary numbers
    files_analyzed_count: int = 0
    files_to_move_count: int = 0
    folders_to_create_count: int = 0
    conflicts_count: int = 0
    total_size_bytes: int = 0
    protected_folders_skipped_count: int = 0
    protected_folders_skipped: List[str] = []

    # Comparison views
    current_structure: List[StructureTreeNode] = []
    proposed_structure: List[StructureTreeNode] = []

    # Proposed operations
    items: List[ProposedChangeItem] = []

    model_config = ConfigDict(from_attributes=True)


class ProtectedSubfolderItem(BaseModel):
    id: str
    managed_folder_id: str
    relative_path: str
    name: str
    source: str = "manual"  # "manual", "smart_detect", "ai"
    category: str = "custom"  # "tool_bundle", "code_project", "sdk_runtime", "custom"
    reason: str = "Flagged manually to keep internal files intact"
    confidence: float = 1.0
    is_protected: bool = True
    created_at: str


class ProtectedSubfolderCreate(BaseModel):
    relative_path: str = Field(..., min_length=1, max_length=1024)
    reason: Optional[str] = None


class ProtectedSubfolderToggle(BaseModel):
    is_protected: bool


class ProtectedFoldersListResponse(BaseModel):
    managed_folder_id: str
    protected_folders: List[ProtectedSubfolderItem] = []
    available_subfolders: List[str] = []


class ProtectedFoldersDetectResponse(BaseModel):
    managed_folder_id: str
    newly_flagged_count: int = 0
    total_protected_count: int = 0
    detection_mode: str = "smart_heuristic"
    protected_folders: List[ProtectedSubfolderItem] = []
    available_subfolders: List[str] = []
