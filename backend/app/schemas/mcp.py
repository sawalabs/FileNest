from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field


# =============================================================================
# Standard MCP Protocol Models
# =============================================================================

class MCPToolInputSchema(BaseModel):
    type: str = "object"
    properties: Dict[str, Any] = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


class MCPToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: MCPToolInputSchema


class MCPToolListResponse(BaseModel):
    tools: List[MCPToolDefinition]
    total_count: int


class MCPCallRequest(BaseModel):
    tool: str
    arguments: Dict[str, Any] = Field(default_factory=dict)


class MCPCallContent(BaseModel):
    type: str = "text"
    text: str


class MCPCallResponse(BaseModel):
    tool: str
    is_error: bool = False
    content: List[MCPCallContent] = Field(default_factory=list)
    data: Optional[Any] = None
    error_message: Optional[str] = None


# =============================================================================
# JSON-RPC 2.0 Compatibility Models
# =============================================================================

class MCPJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    method: str
    params: Optional[Dict[str, Any]] = None


class MCPJsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Union[str, int]] = None
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


# =============================================================================
# Tool-Specific Typed Input / Output Models
# =============================================================================

class MCPDirectoryEntry(BaseModel):
    name: str
    relative_path: str
    is_directory: bool
    size_bytes: int = 0
    modified_at: Optional[str] = None
    extension: Optional[str] = None
    category: Optional[str] = None


class MCPListDirectoryInput(BaseModel):
    managed_folder_id: str
    relative_path: str = ""
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)
    include_hidden: bool = False


class MCPListDirectoryOutput(BaseModel):
    managed_folder_id: str
    relative_path: str
    entries: List[MCPDirectoryEntry]
    total_entries: int
    has_more: bool


class MCPGetMetadataInput(BaseModel):
    managed_folder_id: str
    relative_path: str
    include_snippet: bool = False
    max_snippet_chars: int = Field(default=500, ge=50, le=2000)


class MCPGetMetadataOutput(BaseModel):
    exists: bool
    managed_folder_id: str
    relative_path: str
    file_name: str
    extension: Optional[str] = None
    size_bytes: int
    is_directory: bool
    mime_type: Optional[str] = None
    modified_at: Optional[str] = None
    created_at: Optional[str] = None
    sha256: Optional[str] = None
    is_sensitive: bool = False
    content_snippet: Optional[str] = None
    snippet_redacted_reason: Optional[str] = None


class MCPSearchFilesInput(BaseModel):
    managed_folder_id: str
    query: Optional[str] = None
    extension: Optional[str] = None
    min_size_bytes: Optional[int] = None
    max_size_bytes: Optional[int] = None
    limit: int = Field(default=50, ge=1, le=200)


class MCPSearchFilesOutput(BaseModel):
    managed_folder_id: str
    matches: List[MCPDirectoryEntry]
    total_matches: int


class MCPCategoryBreakdown(BaseModel):
    category: str
    file_count: int
    total_size_bytes: int
    percentage_size: float


class MCPGetStorageBreakdownInput(BaseModel):
    managed_folder_id: str


class MCPGetStorageBreakdownOutput(BaseModel):
    managed_folder_id: str
    total_files: int
    total_size_bytes: int
    categories: List[MCPCategoryBreakdown]
    largest_files: List[MCPDirectoryEntry]


class MCPDuplicateGroup(BaseModel):
    size_bytes: int
    file_count: int
    wasted_bytes: int
    files: List[str]


class MCPDetectDuplicatesInput(BaseModel):
    managed_folder_id: str
    min_size_bytes: int = Field(default=1024, ge=1)
    limit_groups: int = Field(default=20, ge=1, le=100)


class MCPDetectDuplicatesOutput(BaseModel):
    managed_folder_id: str
    total_groups: int
    total_duplicate_files: int
    potential_savings_bytes: int
    groups: List[MCPDuplicateGroup]


class MCPPlanOperationItem(BaseModel):
    operation: Literal["move", "rename", "create_directory"]
    source_relative_path: Optional[str] = None
    destination_relative_path: Optional[str] = None
    reason: Optional[str] = None


class MCPCreateOrganizationPlanInput(BaseModel):
    managed_folder_id: str
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    operations: List[MCPPlanOperationItem] = Field(min_length=1)


class MCPPlanRenameItem(BaseModel):
    source_relative_path: str
    new_file_name: str
    reason: Optional[str] = None


class MCPCreateRenamePlanInput(BaseModel):
    managed_folder_id: str
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    renames: List[MCPPlanRenameItem] = Field(min_length=1)


class MCPCreatePlanOutput(BaseModel):
    plan_id: str
    managed_folder_id: str
    title: str
    plan_type: str
    status: str
    items_count: int
    requires_approval: bool = True
    review_url: str
    message: str

