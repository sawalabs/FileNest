from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class FileItemMetadata(BaseModel):
    name: str = Field(description="Name of the file or directory")
    relative_path: str = Field(description="Path relative to the Managed Folder root")
    parent_relative_path: str = Field(description="Parent folder path relative to root")
    item_type: str = Field(description="'file' or 'directory'")
    size_bytes: int = Field(default=0, description="Size in bytes")
    extension: Optional[str] = Field(default=None, description="Lowercase file extension without leading dot")
    mime_type: Optional[str] = Field(default=None, description="Guessed MIME type")
    category: str = Field(default="other", description="High-level category (document, image, video, audio, archive, code, other)")
    modified_at: Optional[str] = Field(default=None, description="Filesystem modified timestamp in UTC ISO-8601")
    created_fs_at: Optional[str] = Field(default=None, description="Filesystem created timestamp in UTC ISO-8601")
    is_hidden: bool = Field(default=False, description="Whether the file/directory is hidden")
    is_symlink: bool = Field(default=False, description="Whether the entry is a symlink or reparse point")
    is_inaccessible: bool = Field(default=False, description="Whether the entry could not be read")
    error_message: Optional[str] = Field(default=None, description="Error reason if inaccessible")


class DirectoryListingResponse(BaseModel):
    managed_folder_id: str
    managed_folder_name: str
    current_relative_path: str
    parent_relative_path: Optional[str] = None
    entries: List[FileItemMetadata]
    total_files: int
    total_directories: int
    total_size_bytes: int


class FolderSummaryResponse(BaseModel):
    managed_folder_id: str
    relative_path: str
    total_size_bytes: int
    file_count: int
    directory_count: int
    category_counts: Dict[str, int]
    category_bytes: Dict[str, int]
    inaccessible_count: int


class GlobalSearchHit(BaseModel):
    managed_folder_id: str
    managed_folder_name: str
    name: str
    relative_path: str
    parent_relative_path: str
    item_type: str
    size_bytes: int = 0
    extension: Optional[str] = None
    category: str = "other"
    modified_at: Optional[str] = None


class GlobalSearchResponse(BaseModel):
    query: str
    hits: List[GlobalSearchHit]
    truncated: bool = False
