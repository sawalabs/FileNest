import json
import mimetypes
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.mcp import (
    MCPCallContent,
    MCPCallResponse,
    MCPCategoryBreakdown,
    MCPCreateOrganizationPlanInput,
    MCPCreatePlanOutput,
    MCPCreateRenamePlanInput,
    MCPDetectDuplicatesInput,
    MCPDetectDuplicatesOutput,
    MCPDirectoryEntry,
    MCPDuplicateGroup,
    MCPGetMetadataInput,
    MCPGetMetadataOutput,
    MCPGetStorageBreakdownInput,
    MCPGetStorageBreakdownOutput,
    MCPJsonRpcRequest,
    MCPJsonRpcResponse,
    MCPListDirectoryInput,
    MCPListDirectoryOutput,
    MCPSearchFilesInput,
    MCPSearchFilesOutput,
    MCPToolDefinition,
    MCPToolInputSchema,
    MCPToolListResponse,
)
from backend.app.schemas.transaction import (
    ChangePlanCreate,
    ChangePlanItemCreate,
    OperationType,
    PlanType,
)
from backend.app.services.filesystem import (
    detect_file_category,
    format_timestamp,
    is_hidden_item,
    is_reparse_point_or_symlink,
)
from backend.app.services.managed_folder import ManagedFolderException, PathValidator
from backend.app.services.settings_service import SettingsService
from backend.app.services.storage import StorageAnalyzerService
from backend.app.services.transaction import TransactionManagerService


class MCPToolForbiddenException(Exception):
    """Raised when an agent attempts to invoke a forbidden or unexposed tool."""
    pass


class MCPPathViolationException(Exception):
    """Raised when an agent attempts to access a path outside of Managed Folders."""
    pass


class MCPService:
    """Restricted Model Context Protocol (MCP) tool provider for AI specialists and agents.

    Provides narrowly scoped, schema-validated tools for filesystem inspection,
    metadata lookup, storage analysis, and draft plan creation.
    Strictly forbids raw command execution or unmediated filesystem mutation.
    """

    ALLOWED_TOOLS: Set[str] = {
        "fs_list_directory",
        "fs_get_metadata",
        "fs_search_files",
        "storage_get_breakdown",
        "storage_detect_duplicates",
        "plan_create_organization",
        "plan_create_rename",
    }

    FORBIDDEN_TOOLS: Set[str] = {
        "shell_exec",
        "exec",
        "execute_command",
        "run_command",
        "bash",
        "powershell",
        "cmd",
        "write_file",
        "delete_file",
        "remove_file",
        "rmtree",
        "execute_plan",
    }

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)
        self.transaction_service = TransactionManagerService(db)
        self.storage_service = StorageAnalyzerService(db)
        self.audit_repo = AuditLogRepository(db)

    # =========================================================================
    # Path & Scope Confinement Validation
    # =========================================================================

    def _get_active_folder(self, folder_id: str) -> ManagedFolder:
        """Retrieves and validates that the Managed Folder exists and is enabled."""
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise MCPPathViolationException(f"Managed Folder '{folder_id}' tidak ditemukan.")
        if not folder.is_enabled:
            raise MCPPathViolationException(f"Managed Folder '{folder.name}' sedang dinonaktifkan.")
        return folder

    def _resolve_safe_path(self, folder: ManagedFolder, relative_path: str) -> Path:
        """Strictly confines relative_path within the Managed Folder boundary."""
        try:
            target = PathValidator.resolve_and_verify_scope(folder, relative_path)
        except ManagedFolderException as e:
            raise MCPPathViolationException(f"Path boundary violation: {str(e)}")

        # Block traversal of reparse points or symlinks
        if target.exists() and is_reparse_point_or_symlink(target):
            raise MCPPathViolationException(
                f"Akses ditolak: Target '{relative_path}' merupakan symlink atau junction point."
            )
        return target

    # =========================================================================
    # Tool Schemas & Discovery
    # =========================================================================

    def list_tools(self) -> MCPToolListResponse:
        """Returns the catalog of all restricted MCP tools exposed to AI agents."""
        definitions = [
            MCPToolDefinition(
                name="fs_list_directory",
                description="Lists directory entries safely within a Managed Folder with metadata and pagination.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "relative_path": {
                            "type": "string",
                            "description": "Relative directory path inside folder root (empty string for root)",
                            "default": "",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of items to return (1-500)",
                            "default": 100,
                        },
                        "offset": {
                            "type": "integer",
                            "description": "Offset index for pagination",
                            "default": 0,
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Whether to include hidden and system files",
                            "default": False,
                        },
                    },
                    required=["managed_folder_id"],
                ),
            ),
            MCPToolDefinition(
                name="fs_get_metadata",
                description="Retrieves file size, timestamps, mime type, hash, and optional privacy-filtered snippet.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "relative_path": {
                            "type": "string",
                            "description": "Relative file path inside folder root",
                        },
                        "include_snippet": {
                            "type": "boolean",
                            "description": "Request text snippet (subject to user privacy settings and sensitivity check)",
                            "default": False,
                        },
                        "max_snippet_chars": {
                            "type": "integer",
                            "description": "Maximum characters in content snippet (50-2000)",
                            "default": 500,
                        },
                    },
                    required=["managed_folder_id", "relative_path"],
                ),
            ),
            MCPToolDefinition(
                name="fs_search_files",
                description="Performs structured search within a Managed Folder by query, extension, and size.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "query": {
                            "type": "string",
                            "description": "Substring to search in file name",
                        },
                        "extension": {
                            "type": "string",
                            "description": "File extension to filter (e.g. 'pdf', 'docx', 'png')",
                        },
                        "min_size_bytes": {
                            "type": "integer",
                            "description": "Minimum file size in bytes",
                        },
                        "max_size_bytes": {
                            "type": "integer",
                            "description": "Maximum file size in bytes",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum results to return (1-200)",
                            "default": 50,
                        },
                    },
                    required=["managed_folder_id"],
                ),
            ),
            MCPToolDefinition(
                name="storage_get_breakdown",
                description="Retrieves storage analysis breakdown by category, extensions, and largest files.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                    },
                    required=["managed_folder_id"],
                ),
            ),
            MCPToolDefinition(
                name="storage_detect_duplicates",
                description="Identifies potential duplicate file groups grouped by identical content size and hash.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "min_size_bytes": {
                            "type": "integer",
                            "description": "Minimum file size in bytes to check for duplicates",
                            "default": 1024,
                        },
                        "limit_groups": {
                            "type": "integer",
                            "description": "Maximum duplicate groups to return",
                            "default": 20,
                        },
                    },
                    required=["managed_folder_id"],
                ),
            ),
            MCPToolDefinition(
                name="plan_create_organization",
                description="Proposes a structured organization plan (move, rename, create directory). Never mutates files directly; routes to Review Changes for user approval.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "title": {
                            "type": "string",
                            "description": "Descriptive title of the proposed organization plan",
                        },
                        "description": {
                            "type": "string",
                            "description": "Explanation of organization rationale",
                        },
                        "operations": {
                            "type": "array",
                            "description": "List of proposed atomic operations",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "operation": {
                                        "type": "string",
                                        "enum": ["move", "rename", "create_directory"],
                                    },
                                    "source_relative_path": {"type": "string"},
                                    "destination_relative_path": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["operation"],
                            },
                        },
                    },
                    required=["managed_folder_id", "title", "operations"],
                ),
            ),
            MCPToolDefinition(
                name="plan_create_rename",
                description="Proposes a structured smart rename plan. Never mutates files directly; routes to Review Changes for user approval.",
                inputSchema=MCPToolInputSchema(
                    properties={
                        "managed_folder_id": {
                            "type": "string",
                            "description": "ID of the target registered Managed Folder",
                        },
                        "title": {
                            "type": "string",
                            "description": "Descriptive title of the proposed rename plan",
                        },
                        "description": {
                            "type": "string",
                            "description": "Explanation of rename rules used",
                        },
                        "renames": {
                            "type": "array",
                            "description": "List of rename mappings",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "source_relative_path": {"type": "string"},
                                    "new_file_name": {"type": "string"},
                                    "reason": {"type": "string"},
                                },
                                "required": ["source_relative_path", "new_file_name"],
                            },
                        },
                    },
                    required=["managed_folder_id", "title", "renames"],
                ),
            ),
        ]
        return MCPToolListResponse(tools=definitions, total_count=len(definitions))

    # =========================================================================
    # Tool Execution & Dispatcher
    # =========================================================================

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> MCPCallResponse:
        """Dispatches an MCP tool call through validation, isolation, and audit logging."""
        # 1. Reject forbidden tools
        if tool_name in self.FORBIDDEN_TOOLS:
            self._record_audit(
                action="mcp_tool_blocked",
                tool=tool_name,
                status="forbidden",
                details={"reason": "Explicitly forbidden mutating or shell execution tool."},
            )
            return MCPCallResponse(
                tool=tool_name,
                is_error=True,
                error_message=(
                    f"Akses ditolak: Tool '{tool_name}' dilarang demi keamanan sistem. "
                    "AI tidak memiliki izin eksekusi shell atau mutasi langsung."
                ),
            )

        # 2. Check whitelist
        if tool_name not in self.ALLOWED_TOOLS:
            self._record_audit(
                action="mcp_tool_unknown",
                tool=tool_name,
                status="unauthorized",
                details={"reason": "Tool not in permitted MCP whitelist."},
            )
            return MCPCallResponse(
                tool=tool_name,
                is_error=True,
                error_message=f"Tool '{tool_name}' tidak terdaftar dalam restricted MCP layer.",
            )

        # 3. Dispatch to handler
        try:
            if tool_name == "fs_list_directory":
                out = self._tool_fs_list_directory(arguments)
            elif tool_name == "fs_get_metadata":
                out = self._tool_fs_get_metadata(arguments)
            elif tool_name == "fs_search_files":
                out = self._tool_fs_search_files(arguments)
            elif tool_name == "storage_get_breakdown":
                out = self._tool_storage_get_breakdown(arguments)
            elif tool_name == "storage_detect_duplicates":
                out = self._tool_storage_detect_duplicates(arguments)
            elif tool_name == "plan_create_organization":
                out = self._tool_plan_create_organization(arguments)
            elif tool_name == "plan_create_rename":
                out = self._tool_plan_create_rename(arguments)
            else:
                raise MCPToolForbiddenException(f"Handler not found for '{tool_name}'")

            self._record_audit(
                action="mcp_tool_success",
                tool=tool_name,
                status="success",
                details={"folder_id": arguments.get("managed_folder_id")},
            )

            serialized_text = json.dumps(out.model_dump(), default=str)
            return MCPCallResponse(
                tool=tool_name,
                is_error=False,
                content=[MCPCallContent(type="text", text=serialized_text)],
                data=out.model_dump(),
            )
        except (MCPPathViolationException, ManagedFolderException) as e:
            self._record_audit(
                action="mcp_tool_violation",
                tool=tool_name,
                status="error",
                details={"error": str(e)},
            )
            return MCPCallResponse(
                tool=tool_name,
                is_error=True,
                error_message=f"Batasan direktori dilanggar: {str(e)}",
            )
        except Exception as e:
            logger.error(f"MCP tool '{tool_name}' error: {e}", exc_info=True)
            self._record_audit(
                action="mcp_tool_error",
                tool=tool_name,
                status="error",
                details={"error": str(e)},
            )
            return MCPCallResponse(
                tool=tool_name,
                is_error=True,
                error_message=f"Kesalahan saat menjalankan tool '{tool_name}': {str(e)}",
            )

    # =========================================================================
    # JSON-RPC 2.0 Handler
    # =========================================================================

    def handle_jsonrpc(self, request: MCPJsonRpcRequest) -> MCPJsonRpcResponse:
        """Processes standard MCP JSON-RPC 2.0 requests."""
        if request.method == "tools/list":
            tools_list = self.list_tools()
            return MCPJsonRpcResponse(
                id=request.id,
                result={"tools": [t.model_dump() for t in tools_list.tools]},
            )
        elif request.method == "tools/call":
            params = request.params or {}
            tool_name = params.get("name") or params.get("tool") or ""
            args = params.get("arguments") or {}
            call_res = self.call_tool(tool_name, args)
            if call_res.is_error:
                return MCPJsonRpcResponse(
                    id=request.id,
                    result={"isError": True, "content": [{"type": "text", "text": call_res.error_message or "Error"}]},
                )
            return MCPJsonRpcResponse(
                id=request.id,
                result={
                    "isError": False,
                    "content": [{"type": c.type, "text": c.text} for c in call_res.content],
                    "data": call_res.data,
                },
            )
        elif request.method == "ping":
            return MCPJsonRpcResponse(id=request.id, result={"status": "pong"})
        else:
            return MCPJsonRpcResponse(
                id=request.id,
                error={"code": -32601, "message": f"Method '{request.method}' not found"},
            )

    # =========================================================================
    # Specific Tool Implementations
    # =========================================================================

    def _tool_fs_list_directory(self, arguments: Dict[str, Any]) -> MCPListDirectoryOutput:
        inp = MCPListDirectoryInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)
        target_path = self._resolve_safe_path(folder, inp.relative_path)

        if not target_path.exists():
            raise MCPPathViolationException(f"Direktori '{inp.relative_path}' tidak ditemukan.")
        if not target_path.is_dir():
            raise MCPPathViolationException(f"Path '{inp.relative_path}' bukan direktori.")

        root = Path(folder.root_path).resolve()
        raw_entries: List[MCPDirectoryEntry] = []

        with os.scandir(target_path) as it:
            for entry in it:
                p = Path(entry.path)
                if not inp.include_hidden and is_hidden_item(p):
                    continue
                if is_reparse_point_or_symlink(p):
                    continue

                try:
                    rel = p.relative_to(root).as_posix()
                except ValueError:
                    rel = p.name

                is_d = entry.is_dir(follow_symlinks=False)
                try:
                    st = entry.stat(follow_symlinks=False)
                    size = st.st_size if not is_d else 0
                    mtime = format_timestamp(st.st_mtime)
                except OSError:
                    size = 0
                    mtime = None

                ext = p.suffix.lower().lstrip(".") if not is_d and p.suffix else None
                cat = detect_file_category(ext) if not is_d else "folder"

                raw_entries.append(
                    MCPDirectoryEntry(
                        name=p.name,
                        relative_path=rel,
                        is_directory=is_d,
                        size_bytes=size,
                        modified_at=mtime,
                        extension=ext,
                        category=cat,
                    )
                )

        raw_entries.sort(key=lambda x: (0 if x.is_directory else 1, x.name.lower()))
        total_count = len(raw_entries)
        paginated = raw_entries[inp.offset : inp.offset + inp.limit]
        has_more = (inp.offset + len(paginated)) < total_count

        return MCPListDirectoryOutput(
            managed_folder_id=folder.id,
            relative_path=inp.relative_path,
            entries=paginated,
            total_entries=total_count,
            has_more=has_more,
        )

    def _tool_fs_get_metadata(self, arguments: Dict[str, Any]) -> MCPGetMetadataOutput:
        inp = MCPGetMetadataInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)
        target = self._resolve_safe_path(folder, inp.relative_path)

        if not target.exists():
            return MCPGetMetadataOutput(
                exists=False,
                managed_folder_id=folder.id,
                relative_path=inp.relative_path,
                file_name=target.name,
                size_bytes=0,
                is_directory=False,
            )

        root = Path(folder.root_path).resolve()
        try:
            rel = target.relative_to(root).as_posix()
        except ValueError:
            rel = inp.relative_path

        is_d = target.is_dir()
        st = target.stat(follow_symlinks=False)
        size = st.st_size if not is_d else 0
        ext = target.suffix.lower().lstrip(".") if not is_d and target.suffix else None
        mime = mimetypes.guess_type(target.name)[0] if not is_d else None

        # Privacy & Sensitivity Check
        ai_cfg = self.settings_service.get_ai_settings()
        sensitive_exts = set(e.lower().lstrip(".") for e in ai_cfg.sensitive_file_extensions)
        is_sensitive = bool(ext and ext in sensitive_exts)

        content_snippet: Optional[str] = None
        redacted_reason: Optional[str] = None

        if inp.include_snippet and not is_d:
            if not ai_cfg.content_extraction_consent:
                redacted_reason = "Izin ekstraksi konten dokumen belum diberikan dalam pengaturan AI."
            elif ai_cfg.metadata_only:
                redacted_reason = "Mode privasi metadata-only aktif."
            elif is_sensitive:
                redacted_reason = f"Ekstensi file '.{ext}' masuk dalam daftar file sensitif."
            elif size > 2 * 1024 * 1024:
                redacted_reason = "Ukuran file melebihi 2MB untuk preview teks aman."
            else:
                try:
                    with open(target, "r", encoding="utf-8", errors="replace") as f:
                        content_snippet = f.read(inp.max_snippet_chars)
                except Exception as e:
                    redacted_reason = f"Tidak dapat membaca file teks: {str(e)}"

        return MCPGetMetadataOutput(
            exists=True,
            managed_folder_id=folder.id,
            relative_path=rel,
            file_name=target.name,
            extension=ext,
            size_bytes=size,
            is_directory=is_d,
            mime_type=mime,
            modified_at=format_timestamp(st.st_mtime),
            created_at=format_timestamp(getattr(st, "st_ctime", st.st_mtime)),
            is_sensitive=is_sensitive,
            content_snippet=content_snippet,
            snippet_redacted_reason=redacted_reason,
        )

    def _tool_fs_search_files(self, arguments: Dict[str, Any]) -> MCPSearchFilesOutput:
        inp = MCPSearchFilesInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)
        root = Path(folder.root_path).resolve()

        query_str = inp.query.lower().strip() if inp.query else ""
        ext_filter = inp.extension.lower().lstrip(".") if inp.extension else None

        matches: List[MCPDirectoryEntry] = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune hidden or symlink directories
            dirnames[:] = [
                d for d in dirnames
                if not is_hidden_item(Path(dirpath) / d) and not is_reparse_point_or_symlink(Path(dirpath) / d)
            ]

            for fname in filenames:
                fpath = Path(dirpath) / fname
                if is_hidden_item(fpath) or is_reparse_point_or_symlink(fpath):
                    continue

                if query_str and query_str not in fname.lower():
                    continue

                f_ext = fpath.suffix.lower().lstrip(".") if fpath.suffix else None
                if ext_filter and f_ext != ext_filter:
                    continue

                try:
                    st = fpath.stat(follow_symlinks=False)
                    f_size = st.st_size
                except OSError:
                    continue

                if inp.min_size_bytes is not None and f_size < inp.min_size_bytes:
                    continue
                if inp.max_size_bytes is not None and f_size > inp.max_size_bytes:
                    continue

                try:
                    rel = fpath.relative_to(root).as_posix()
                except ValueError:
                    rel = fname

                matches.append(
                    MCPDirectoryEntry(
                        name=fname,
                        relative_path=rel,
                        is_directory=False,
                        size_bytes=f_size,
                        modified_at=format_timestamp(st.st_mtime),
                        extension=f_ext,
                        category=detect_file_category(f_ext),
                    )
                )

                if len(matches) >= inp.limit:
                    break

            if len(matches) >= inp.limit:
                break

        return MCPSearchFilesOutput(
            managed_folder_id=folder.id,
            matches=matches,
            total_matches=len(matches),
        )

    def _tool_storage_get_breakdown(self, arguments: Dict[str, Any]) -> MCPGetStorageBreakdownOutput:
        inp = MCPGetStorageBreakdownInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)

        # Get or trigger storage analysis
        analysis = self.storage_service.get_latest_analysis(folder.id)
        if not analysis:
            analysis = self.storage_service.analyze_folder(folder.id)

        categories: List[MCPCategoryBreakdown] = [
            MCPCategoryBreakdown(
                category=cat.category,
                file_count=cat.files_count,
                total_size_bytes=cat.total_size_bytes,
                percentage_size=cat.percentage,
            )
            for cat in analysis.category_distribution
        ]

        largest: List[MCPDirectoryEntry] = [
            MCPDirectoryEntry(
                name=lf.name,
                relative_path=lf.relative_path,
                is_directory=False,
                size_bytes=lf.size_bytes,
                modified_at=lf.modified_at,
                extension=lf.extension,
                category=lf.category,
            )
            for lf in analysis.large_files[:10]
        ]

        return MCPGetStorageBreakdownOutput(
            managed_folder_id=folder.id,
            total_files=analysis.total_files_count,
            total_size_bytes=analysis.total_storage_bytes,
            categories=categories,
            largest_files=largest,
        )

    def _tool_storage_detect_duplicates(self, arguments: Dict[str, Any]) -> MCPDetectDuplicatesOutput:
        inp = MCPDetectDuplicatesInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)

        analysis = self.storage_service.get_latest_analysis(folder.id)
        if not analysis:
            analysis = self.storage_service.analyze_folder(folder.id)

        groups: List[MCPDuplicateGroup] = []
        filtered_groups = [
            g for g in analysis.duplicate_groups
            if g.size_bytes >= inp.min_size_bytes
        ][: inp.limit_groups]

        total_dup_files = sum(len(g.files) for g in filtered_groups)
        total_wasted = sum(g.potential_savings_bytes for g in filtered_groups)

        for g in filtered_groups:
            file_paths = [f.relative_path for f in g.files]
            groups.append(
                MCPDuplicateGroup(
                    size_bytes=g.size_bytes,
                    file_count=len(g.files),
                    wasted_bytes=g.potential_savings_bytes,
                    files=file_paths,
                )
            )

        return MCPDetectDuplicatesOutput(
            managed_folder_id=folder.id,
            total_groups=len(groups),
            total_duplicate_files=total_dup_files,
            potential_savings_bytes=total_wasted,
            groups=groups,
        )

    def _tool_plan_create_organization(self, arguments: Dict[str, Any]) -> MCPCreatePlanOutput:
        """Strictly creates a draft change plan in Review Changes without executing mutations."""
        inp = MCPCreateOrganizationPlanInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)

        plan_items: List[ChangePlanItemCreate] = []
        for idx, op in enumerate(inp.operations, start=1):
            # Validate boundaries of all source and destination paths
            if op.source_relative_path:
                self._resolve_safe_path(folder, op.source_relative_path)
            if op.destination_relative_path:
                self._resolve_safe_path(folder, op.destination_relative_path)

            op_type = OperationType(op.operation)
            plan_items.append(
                ChangePlanItemCreate(
                    operation=op_type,
                    source_relative_path=op.source_relative_path,
                    destination_relative_path=op.destination_relative_path,
                    sequence_no=idx,
                )
            )

        create_payload = ChangePlanCreate(
            managed_folder_id=folder.id,
            title=inp.title.strip(),
            plan_type=PlanType.ORGANIZE,
            items=plan_items,
        )

        plan = self.transaction_service.create_plan(create_payload, created_by="ai")

        return MCPCreatePlanOutput(
            plan_id=plan.id,
            managed_folder_id=folder.id,
            title=plan.title,
            plan_type=plan.plan_type,
            status=plan.status,
            items_count=len(plan_items),
            requires_approval=True,
            review_url=f"/review/{plan.id}",
            message="Change plan successfully created and routed to Review Changes for user approval.",
        )

    def _tool_plan_create_rename(self, arguments: Dict[str, Any]) -> MCPCreatePlanOutput:
        """Strictly creates a draft rename plan in Review Changes without executing mutations."""
        inp = MCPCreateRenamePlanInput(**arguments)
        folder = self._get_active_folder(inp.managed_folder_id)

        plan_items: List[ChangePlanItemCreate] = []
        for idx, r in enumerate(inp.renames, start=1):
            src_path = self._resolve_safe_path(folder, r.source_relative_path)
            if not src_path.exists():
                raise MCPPathViolationException(f"File sumber tidak ditemukan: '{r.source_relative_path}'")

            parent = Path(r.source_relative_path).parent.as_posix()
            dest_rel = r.new_file_name if parent in (".", "") else f"{parent}/{r.new_file_name}"
            self._resolve_safe_path(folder, dest_rel)

            plan_items.append(
                ChangePlanItemCreate(
                    operation=OperationType.RENAME,
                    source_relative_path=r.source_relative_path,
                    destination_relative_path=dest_rel,
                    sequence_no=idx,
                )
            )

        create_payload = ChangePlanCreate(
            managed_folder_id=folder.id,
            title=inp.title.strip(),
            plan_type=PlanType.RENAME,
            items=plan_items,
        )

        plan = self.transaction_service.create_plan(create_payload, created_by="ai")

        return MCPCreatePlanOutput(
            plan_id=plan.id,
            managed_folder_id=folder.id,
            title=plan.title,
            plan_type=plan.plan_type,
            status=plan.status,
            items_count=len(plan_items),
            requires_approval=True,
            review_url=f"/review/{plan.id}",
            message="Smart rename plan successfully created and routed to Review Changes for user approval.",
        )

    def _record_audit(self, action: str, tool: str, status: str, details: Dict[str, Any]) -> None:
        try:
            full_details = dict(details)
            full_details["status"] = status
            self.audit_repo.record(
                actor_type="ai",
                action=action,
                entity_type="mcp_tool",
                entity_id=tool,
                details=full_details,
            )
        except Exception as e:
            logger.warning(f"Failed to record MCP audit log: {e}")
