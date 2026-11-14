from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class SmartRenamePlanRequest(BaseModel):
    managed_folder_id: str
    target_subfolder: Optional[str] = Field(
        default="",
        description="Subfolder to rename files in, or empty string for the entire managed folder.",
    )
    target_relative_paths: Optional[List[str]] = Field(
        default=None,
        description="Specific relative file paths to rename. If None, all files in subfolder are analyzed.",
    )
    strategy: str = Field(
        default="make_consistent",
        description="Naming strategy: 'make_consistent', 'pattern', 'add_meaningful', 'describe_content'.",
    )
    use_ai_content: bool = Field(
        default=False,
        description="Extract file content / OCR text to generate meaningful descriptive filenames using AI.",
    )
    run_ocr_background: bool = Field(
        default=False,
        description="If True, initiates OCR text extraction and AI renaming asynchronously in background.",
    )
    pattern: Optional[str] = Field(
        default="{name}",
        description="Naming pattern template (e.g. '{project}_{type}_{date}_{number}').",
    )
    case_transform: str = Field(
        default="lower",
        description="Case transform: 'lower', 'upper', 'title', 'preserve'.",
    )
    space_replacement: str = Field(
        default="_",
        description="Replace spaces with: '_' (underscore), '-' (hyphen), 'none' (leave spaces).",
    )
    keep_extension: bool = Field(
        default=True,
        description="Whether to preserve original file extensions.",
    )
    add_sequence_on_collision: bool = Field(
        default=True,
        description="Automatically append numeric sequence (_01, _02) if name collision occurs.",
    )
    skip_compliant_files: bool = Field(
        default=True,
        description="Skip files that already match the proposed naming convention.",
    )
    prefix: Optional[str] = Field(
        default="",
        description="Optional prefix to add to all proposed filenames.",
    )
    suffix: Optional[str] = Field(
        default="",
        description="Optional suffix to add before extension.",
    )
    title: Optional[str] = Field(
        default=None,
        description="Custom title for the Change Plan.",
    )


class SmartRenamePreviewItem(BaseModel):
    item_id: Optional[str] = None
    sequence_no: int
    source_relative_path: str
    original_name: str
    proposed_name: str
    destination_relative_path: str
    size_bytes: int = 0
    extension: Optional[str] = None
    category: Optional[str] = None
    status: str = "ready"  # "ready", "conflict", "unchanged"
    conflict_reason: Optional[str] = None


class SmartRenamePlanResult(BaseModel):
    change_plan_id: str
    managed_folder_id: str
    managed_folder_name: str
    strategy: str
    title: str
    status: str
    created_at: str

    files_analyzed_count: int = 0
    files_to_rename_count: int = 0
    files_unchanged_count: int = 0
    conflicts_count: int = 0
    total_size_bytes: int = 0

    items: List[SmartRenamePreviewItem] = []

    model_config = ConfigDict(from_attributes=True)


class ItemOCRAnalyzeRequest(BaseModel):
    plan_id: str
    item_id: str


class ItemOCRAnalyzeResponse(BaseModel):
    item_id: str
    plan_id: str
    source_relative_path: str
    original_name: str
    proposed_name: str
    destination_relative_path: str
    extracted_text: Optional[str] = None
    status: str = "ready"  # "ready", "conflict", "unchanged"
    conflict_reason: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None


class BatchOCRJobStatus(BaseModel):
    plan_id: str
    is_running: bool = False
    total_items: int = 0
    processed_items: int = 0
    success_count: int = 0
    error_count: int = 0
    current_item_name: Optional[str] = None
    message: Optional[str] = None


class QuickOCRRenameRequest(BaseModel):
    folder_id: str
    relative_path: str


class QuickOCRRenameResponse(BaseModel):
    original_name: str
    proposed_name: str
    relative_path: str
    extracted_text: Optional[str] = None
    category: str = "other"
    success: bool = True
    error_message: Optional[str] = None


