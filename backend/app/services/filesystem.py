import os
import stat
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.repositories.file import FileRepository
from backend.app.schemas.filesystem import (
    DirectoryListingResponse,
    FileItemMetadata,
    FolderSummaryResponse,
    GlobalSearchHit,
    GlobalSearchResponse,
)
from backend.app.services.managed_folder import (
    ManagedFolderException,
    PathValidator,
)

FILE_CATEGORIES: Dict[str, set[str]] = {
    "document": {
        "pdf", "doc", "docx", "txt", "rtf", "odt", "md",
        "csv", "xls", "xlsx", "ppt", "pptx", "epub",
    },
    "image": {
        "png", "jpg", "jpeg", "gif", "bmp", "webp", "svg",
        "tiff", "ico", "heic", "avif",
    },
    "video": {
        "mp4", "mkv", "avi", "mov", "wmv", "flv", "webm", "m4v",
    },
    "audio": {
        "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a", "opus",
    },
    "archive": {
        "zip", "rar", "7z", "tar", "gz", "bz2", "xz", "iso",
    },
    "code": {
        "py", "js", "ts", "tsx", "jsx", "html", "css", "rs",
        "c", "cpp", "h", "hpp", "json", "yaml", "yml", "toml",
        "xml", "sql", "sh", "ps1", "bat", "java", "kt", "go",
    },
}

SUPPORTED_IMAGE_MIMES: Dict[str, str] = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
    "gif": "image/gif",
    "bmp": "image/bmp",
    "svg": "image/svg+xml",
    "ico": "image/x-icon",
    "avif": "image/avif",
}

SUPPORTED_TEXT_EXTENSIONS: set[str] = {
    "txt", "md", "markdown", "rst", "log", "csv", "tsv",
    "json", "yaml", "yml", "xml", "html", "css",
    "js", "jsx", "ts", "tsx", "py", "rs", "sql", "sh", "bat", "cmd",
    "toml", "ini", "env", "conf", "cfg",
}


def detect_file_category(extension_or_name: Optional[str]) -> str:
    """Categorizes a file based on its lowercase extension or filename."""
    if not extension_or_name:
        return "other"
    clean = extension_or_name.lower().strip()
    if "." in clean:
        ext = clean.rsplit(".", 1)[-1]
    else:
        ext = clean
    for category, extensions in FILE_CATEGORIES.items():
        if ext in extensions:
            return category
    return "other"


def is_reparse_point_or_symlink(path: Path) -> bool:
    """Detects if path is a symlink or Windows reparse point (junction/mount point)."""
    if path.is_symlink():
        return True
    try:
        st = path.lstat()
        file_attrs = getattr(st, "st_file_attributes", 0)
        return bool(file_attrs & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except Exception:
        return False


def is_hidden_item(path: Path) -> bool:
    """Detects if a path is marked as hidden (dotfile or Windows hidden attribute)."""
    if path.name.startswith("."):
        return True
    try:
        st = path.stat(follow_symlinks=False)
        file_attrs = getattr(st, "st_file_attributes", 0)
        return bool(file_attrs & getattr(stat, "FILE_ATTRIBUTE_HIDDEN", 0x2))
    except Exception:
        return False


def format_timestamp(ts: Optional[float]) -> Optional[str]:
    """Converts a posix timestamp to UTC ISO-8601 string."""
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except Exception:
        return None


class FilesystemService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_repo = AuditLogRepository(db)
        self.file_repo = FileRepository(db)

    def _get_active_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise ManagedFolderException(f"Managed Folder '{folder_id}' not found")
        if not folder.is_enabled:
            raise ManagedFolderException(f"Managed Folder '{folder.name}' is disabled")
        return folder

    def get_entry_metadata(self, folder: ManagedFolder, path: Path, root_path: Path) -> FileItemMetadata:
        """Inspects a single filesystem entry safely."""
        try:
            rel_path = path.relative_to(root_path).as_posix()
        except ValueError:
            rel_path = path.name

        parent_rel = Path(rel_path).parent.as_posix()
        if parent_rel == ".":
            parent_rel = ""

        name = path.name
        is_symlink = is_reparse_point_or_symlink(path)
        is_hidden = is_hidden_item(path)

        if is_symlink:
            return FileItemMetadata(
                name=name,
                relative_path=rel_path,
                parent_relative_path=parent_rel,
                item_type="file" if not path.is_dir() else "directory",
                size_bytes=0,
                is_symlink=True,
                is_hidden=is_hidden,
                is_inaccessible=False,
                error_message="Skipped symlink / reparse point",
            )

        try:
            st = path.stat(follow_symlinks=False)
            is_dir = stat.S_ISDIR(st.st_mode)
            item_type = "directory" if is_dir else "file"
            size_bytes = st.st_size if not is_dir else 0

            ext = path.suffix.lower().lstrip(".") if not is_dir and path.suffix else None
            mime_type = mimetypes.guess_type(path.name)[0] if not is_dir else None
            category = detect_file_category(ext) if not is_dir else "folder"

            return FileItemMetadata(
                name=name,
                relative_path=rel_path,
                parent_relative_path=parent_rel,
                item_type=item_type,
                size_bytes=size_bytes,
                extension=ext,
                mime_type=mime_type,
                category=category,
                modified_at=format_timestamp(st.st_mtime),
                created_fs_at=format_timestamp(getattr(st, "st_ctime", st.st_mtime)),
                is_hidden=is_hidden,
                is_symlink=False,
                is_inaccessible=False,
            )
        except (PermissionError, OSError) as e:
            return FileItemMetadata(
                name=name,
                relative_path=rel_path,
                parent_relative_path=parent_rel,
                item_type="file",
                size_bytes=0,
                is_hidden=is_hidden,
                is_symlink=False,
                is_inaccessible=True,
                error_message=f"Access denied or unreadable: {e}",
            )

    def list_directory(
        self,
        managed_folder_id: str,
        relative_path: str = "",
        include_hidden: bool = False,
        sort_by: str = "name",
        sort_order: str = "asc",
    ) -> DirectoryListingResponse:
        """Safely lists entries in a directory within a Managed Folder."""
        folder = self._get_active_folder(managed_folder_id)
        root = Path(folder.root_path).resolve()
        target_dir = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target_dir.exists():
            raise ManagedFolderException(f"Directory not found: '{relative_path}'")
        if not target_dir.is_dir():
            raise ManagedFolderException(f"Path is a file, not a directory: '{relative_path}'")
        if is_reparse_point_or_symlink(target_dir):
            raise ManagedFolderException(f"Cannot traverse symlink or reparse point: '{relative_path}'")

        entries: List[FileItemMetadata] = []
        total_files = 0
        total_directories = 0
        total_size = 0

        try:
            with os.scandir(target_dir) as it:
                for entry in it:
                    entry_path = Path(entry.path)
                    meta = self.get_entry_metadata(folder, entry_path, root)

                    if not include_hidden and meta.is_hidden:
                        continue

                    entries.append(meta)
                    if meta.item_type == "directory":
                        total_directories += 1
                    else:
                        total_files += 1
                        total_size += meta.size_bytes
        except PermissionError:
            raise ManagedFolderException(f"Permission denied reading directory: '{relative_path}'")
        except OSError as e:
            raise ManagedFolderException(f"Filesystem error reading directory '{relative_path}': {e}")

        # Sort: directories first, then files; ordered by sort_by and sort_order (QA-01)
        reverse = sort_order.strip().lower() == "desc"
        sort_field = sort_by.strip().lower()

        def _sort_key(item: FileItemMetadata):
            if sort_field == "size":
                return (item.size_bytes, item.name.lower())
            if sort_field == "modified":
                return (item.modified_at or "", item.name.lower())
            return item.name.lower()

        dirs = [e for e in entries if e.item_type == "directory"]
        files = [e for e in entries if e.item_type != "directory"]
        dirs.sort(key=_sort_key, reverse=reverse)
        files.sort(key=_sort_key, reverse=reverse)
        entries = dirs + files

        # Calculate current relative path and parent relative path
        current_rel = target_dir.relative_to(root).as_posix() if target_dir != root else ""
        parent_rel: Optional[str] = None
        if current_rel:
            p = Path(current_rel).parent.as_posix()
            parent_rel = "" if p == "." else p

        return DirectoryListingResponse(
            managed_folder_id=folder.id,
            managed_folder_name=folder.name,
            current_relative_path=current_rel,
            parent_relative_path=parent_rel,
            entries=entries,
            total_files=total_files,
            total_directories=total_directories,
            total_size_bytes=total_size,
        )

    def get_item_metadata(self, managed_folder_id: str, relative_path: str) -> FileItemMetadata:
        """Returns metadata for a specific file or folder."""
        folder = self._get_active_folder(managed_folder_id)
        root = Path(folder.root_path).resolve()
        target = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target.exists():
            raise ManagedFolderException(f"Path does not exist: '{relative_path}'")

        return self.get_entry_metadata(folder, target, root)

    def calculate_folder_summary(self, managed_folder_id: str, relative_path: str = "") -> FolderSummaryResponse:
        """Calculates recursive size and category distribution without traversing symlinks."""
        folder = self._get_active_folder(managed_folder_id)
        target_dir = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target_dir.exists() or not target_dir.is_dir():
            raise ManagedFolderException(f"Valid directory required for summary: '{relative_path}'")

        total_bytes = 0
        file_count = 0
        directory_count = 0
        inaccessible_count = 0
        category_counts: Dict[str, int] = {cat: 0 for cat in FILE_CATEGORIES.keys()}
        category_counts["other"] = 0
        category_bytes: Dict[str, int] = {cat: 0 for cat in FILE_CATEGORIES.keys()}
        category_bytes["other"] = 0

        # Non-symlink walking
        for root_dir, dirs, files in os.walk(target_dir, followlinks=False):
            # Exclude symlink directories in-place from being traversed
            dirs[:] = [d for d in dirs if not is_reparse_point_or_symlink(Path(root_dir) / d)]
            directory_count += len(dirs)

            for file_name in files:
                file_path = Path(root_dir) / file_name
                if is_reparse_point_or_symlink(file_path):
                    continue

                try:
                    st = file_path.stat(follow_symlinks=False)
                    size = st.st_size
                    total_bytes += size
                    file_count += 1

                    ext = file_path.suffix.lower().lstrip(".") if file_path.suffix else None
                    cat = detect_file_category(ext)
                    category_counts[cat] = category_counts.get(cat, 0) + 1
                    category_bytes[cat] = category_bytes.get(cat, 0) + size
                except (PermissionError, OSError):
                    inaccessible_count += 1

        return FolderSummaryResponse(
            managed_folder_id=folder.id,
            relative_path=relative_path,
            total_size_bytes=total_bytes,
            file_count=file_count,
            directory_count=directory_count,
            category_counts=category_counts,
            category_bytes=category_bytes,
            inaccessible_count=inaccessible_count,
        )

    def reconcile_managed_folder(self, managed_folder_id: str) -> Dict[str, Any]:
        """
        Reconciles database FileRecords against the live filesystem for a Managed Folder.
        Stale/deleted files on disk are marked as deleted (is_deleted=1).
        Restored files are reactivated (is_deleted=0).
        Existing files with modified size/mtime are updated.
        Never touches or mutates any user files on the filesystem.
        """
        folder = self._get_active_folder(managed_folder_id)
        root = Path(folder.root_path).resolve()
        stats = self.file_repo.reconcile_folder(folder.id, root)

        self.audit_repo.record(
            actor_type="system",
            action="folder_reconciled",
            entity_type="managed_folder",
            entity_id=folder.id,
            details=stats,
        )
        return {
            "managed_folder_id": folder.id,
            "managed_folder_name": folder.name,
            **stats,
        }

    def get_file_preview_stream(
        self,
        managed_folder_id: str,
        relative_path: str,
        thumbnail: bool = False,
    ) -> Tuple[Path, str, int]:
        """Validates and retrieves the target file path, mime-type, and size for image/binary preview streaming.
        Enforces scope confinement and max size limits.
        """
        folder = self._get_active_folder(managed_folder_id)
        target = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target.exists():
            raise ManagedFolderException(f"File not found: '{relative_path}'")
        if not target.is_file():
            raise ManagedFolderException(f"Path is not a regular file: '{relative_path}'")

        ext = target.suffix.lower().lstrip(".")
        mime_type = SUPPORTED_IMAGE_MIMES.get(ext)
        if not mime_type:
            mime_type, _ = mimetypes.guess_type(target.name)
            if not mime_type or not mime_type.startswith("image/"):
                raise ManagedFolderException(f"Unsupported preview image format: '.{ext}'")

        st = target.stat()
        MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB
        if st.st_size > MAX_IMAGE_SIZE:
            raise ManagedFolderException(f"Image too large for preview ({st.st_size} bytes, max {MAX_IMAGE_SIZE} bytes)")

        return target, mime_type, st.st_size

    def get_file_text_preview(
        self,
        managed_folder_id: str,
        relative_path: str,
        max_bytes: int = 65536,
    ) -> Dict[str, Any]:
        """Reads a sanitized text snippet preview from a text/code file within the managed folder."""
        folder = self._get_active_folder(managed_folder_id)
        target = PathValidator.resolve_and_verify_scope(folder, relative_path)

        if not target.exists():
            raise ManagedFolderException(f"File not found: '{relative_path}'")
        if not target.is_file():
            raise ManagedFolderException(f"Path is not a regular file: '{relative_path}'")

        ext = target.suffix.lower().lstrip(".")
        if ext not in SUPPORTED_TEXT_EXTENSIONS:
            cat = detect_file_category(ext)
            if cat not in ("code", "document"):
                raise ManagedFolderException(f"File type '.{ext}' does not support text preview")

        bounded_bytes = min(max_bytes, 262144)  # Clamp to at most 256KB
        st = target.stat()
        file_size = st.st_size

        try:
            with open(target, "rb") as f:
                raw_chunk = f.read(bounded_bytes)

            # Detect null bytes (binary file heuristic)
            if b"\x00" in raw_chunk[:1024]:
                raise ManagedFolderException("Cannot preview binary file as text")

            text = raw_chunk.decode("utf-8", errors="replace")
            truncated = file_size > len(raw_chunk)
            lines_count = text.count("\n") + 1

            return {
                "relative_path": relative_path,
                "name": target.name,
                "extension": ext,
                "size_bytes": file_size,
                "preview_bytes": len(raw_chunk),
                "lines_count": lines_count,
                "truncated": truncated,
                "content": text,
            }
        except ManagedFolderException:
            raise
        except Exception as e:
            raise ManagedFolderException(f"Failed to read file preview: {str(e)}")

    def search_files(
        self,
        query: str,
        managed_folder_id: Optional[str] = None,
        limit: int = 25,
    ) -> GlobalSearchResponse:
        """Searches files and folders by name across registered Managed Folders (non-mutating, bounded)."""
        clean_query = query.strip()
        if not clean_query:
            return GlobalSearchResponse(query=clean_query, hits=[], truncated=False)

        needle = clean_query.lower()
        if managed_folder_id:
            folders = [self._get_active_folder(managed_folder_id)]
        else:
            folders = (
                self.db.query(ManagedFolder)
                .filter(ManagedFolder.is_enabled == True)
                .order_by(ManagedFolder.name)
                .all()
            )

        hits: List[GlobalSearchHit] = []
        visited = 0
        max_visited = 2500
        truncated = False

        for folder in folders:
            root = Path(folder.root_path).resolve()
            if not root.exists() or not root.is_dir():
                continue

            for current_root, dirs, files in os.walk(root, followlinks=False):
                # Skip symlinks/reparse points and hidden/trash folders
                safe_dirs = []
                for d in dirs:
                    dp = Path(current_root) / d
                    if d.startswith(".") or d in ("node_modules", "__pycache__", ".git"):
                        continue
                    if is_reparse_point_or_symlink(dp):
                        continue
                    safe_dirs.append(d)
                dirs[:] = safe_dirs

                for d in dirs:
                    visited += 1
                    dp = Path(current_root) / d
                    if needle in d.lower():
                        rel = dp.relative_to(root).as_posix()
                        parent_rel = dp.parent.relative_to(root).as_posix() if dp.parent != root else ""
                        try:
                            st = dp.stat(follow_symlinks=False)
                            mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                        except OSError:
                            mod_iso = None
                        hits.append(
                            GlobalSearchHit(
                                managed_folder_id=folder.id,
                                managed_folder_name=folder.name,
                                name=d,
                                relative_path=rel,
                                parent_relative_path="" if parent_rel == "." else parent_rel,
                                item_type="directory",
                                size_bytes=0,
                                extension=None,
                                category="folder",
                                modified_at=mod_iso,
                            )
                        )
                        if len(hits) >= limit:
                            truncated = True
                            return GlobalSearchResponse(query=clean_query, hits=hits, truncated=True)
                    if visited >= max_visited:
                        truncated = True
                        break

                for fname in files:
                    visited += 1
                    fp = Path(current_root) / fname
                    if is_reparse_point_or_symlink(fp):
                        continue
                    if needle in fname.lower():
                        rel = fp.relative_to(root).as_posix()
                        parent_rel = fp.parent.relative_to(root).as_posix() if fp.parent != root else ""
                        ext = fp.suffix.lower().lstrip(".") if fp.suffix else None
                        try:
                            st = fp.stat(follow_symlinks=False)
                            fsize = st.st_size
                            mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                        except OSError:
                            fsize = 0
                            mod_iso = None
                        hits.append(
                            GlobalSearchHit(
                                managed_folder_id=folder.id,
                                managed_folder_name=folder.name,
                                name=fname,
                                relative_path=rel,
                                parent_relative_path="" if parent_rel == "." else parent_rel,
                                item_type="file",
                                size_bytes=fsize,
                                extension=ext,
                                category=detect_file_category(ext),
                                modified_at=mod_iso,
                            )
                        )
                        if len(hits) >= limit:
                            return GlobalSearchResponse(query=clean_query, hits=hits, truncated=True)
                    if visited >= max_visited:
                        truncated = True
                        break

                if visited >= max_visited:
                    break
            if visited >= max_visited:
                break

        return GlobalSearchResponse(query=clean_query, hits=hits, truncated=truncated)
