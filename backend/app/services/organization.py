import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import utc_now_iso
from backend.app.db.models.app_setting import AppSetting
from backend.app.db.models.change_plan import ChangePlan, ChangePlanItem
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.organization import (
    OrganizationPlanRequest,
    OrganizationPlanResult,
    ProposedChangeItem,
    ProtectedFoldersDetectResponse,
    ProtectedFoldersListResponse,
    ProtectedSubfolderCreate,
    ProtectedSubfolderItem,
    StructureTreeNode,
)
from backend.app.schemas.settings import OrganizationSettings
from backend.app.services.filesystem import detect_file_category, is_reparse_point_or_symlink
from backend.app.services.managed_folder import ManagedFolderService, PathValidator
from backend.app.services.settings_service import SettingsService


PROJECT_MARKER_FILES = {
    "package.json",
    "tsconfig.json",
    "cargo.toml",
    "pyproject.toml",
    "requirements.txt",
    "pipfile",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "cmakelists.txt",
    "makefile",
    "composer.json",
    "gemfile",
    "pubspec.yaml",
    "tauri.conf.json",
    "manage.py",
    "androidmanifest.xml",
}

PROJECT_MARKER_EXTENSIONS = {".sln", ".csproj", ".vcxproj", ".xcodeproj"}

KNOWN_TOOL_OR_SDK_FOLDER_NAMES = {
    "platform-tools",
    "platform_tools",
    "cmdline-tools",
    "build-tools",
    "node_modules",
    ".venv",
    "venv",
    "env",
    "sdk",
    "jdk",
    "jre",
    "drivers",
    "driver",
}

BINARY_BUNDLE_EXTENSIONS = {".dll", ".sys", ".ocx", ".pak", ".asar", ".pyd", ".so", ".dylib"}
SUPPORT_CONFIG_EXTENSIONS = {".ini", ".cfg", ".conf", ".dat", ".bin", ".json", ".xml", ".manifest", ".lib"}

ORGANIZED_CATEGORY_FOLDER_NAMES = {
    "documents",
    "images",
    "videos",
    "audio",
    "archives",
    "source_code",
    "others",
    "archive",
    "resources",
    "assets",
}


CATEGORY_FOLDER_MAP = {
    "document": "Documents",
    "image": "Images",
    "video": "Videos",
    "audio": "Audio",
    "archive": "Archives",
    "code": "Source_Code",
    "other": "Others",
}

PROJECT_CATEGORY_MAP = {
    "code": "Source",
    "image": "Assets/Images",
    "video": "Assets/Videos",
    "audio": "Assets/Audio",
    "document": "Documents",
    "archive": "Archive",
    "other": "Resources",
}

CATEGORY_INDEX_MAP = {
    "document": 1,
    "image": 2,
    "video": 3,
    "audio": 4,
    "archive": 5,
    "code": 6,
    "other": 7,
}


class OrganizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def _get_managed_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise ValueError(f"Managed Folder '{folder_id}' not found")
        if not folder.is_enabled:
            raise ValueError(f"Managed Folder '{folder.name}' is currently disabled")
        return folder

    def generate_plan(self, request: OrganizationPlanRequest) -> OrganizationPlanResult:
        """Analyzes folder contents and generates an organization Change Plan with conflict checks.
        Strictly read-only; no filesystem mutations are performed."""
        folder = self._get_managed_folder(request.managed_folder_id)
        root_path = Path(folder.root_path).resolve()

        if not root_path.exists():
            raise ValueError(f"Managed Folder path does not exist on disk: {root_path}")

        # Target subfolder validation
        target_dir = root_path
        subfolder_prefix = ""
        if request.target_subfolder and request.target_subfolder.strip():
            subfolder_prefix = Path(request.target_subfolder.strip()).as_posix().strip("/")
            target_dir = PathValidator.resolve_and_verify_scope(folder, subfolder_prefix)
            if not target_dir.exists() or not target_dir.is_dir():
                raise ValueError(f"Target subfolder '{request.target_subfolder}' does not exist or is not a directory")

        # 1. Collect all files in scope while respecting protected/flagged project & tool folders
        protected_rel_paths = self.get_active_protected_rel_paths(folder.id, auto_detect_new=True)
        protected_lower = {p.lower() for p in protected_rel_paths}
        skipped_protected_folders: Set[str] = set()

        def _is_protected_rel(rel_dir: str) -> Optional[str]:
            norm = rel_dir.replace("\\", "/").strip("/")
            if not norm:
                return None
            norm_lower = norm.lower()
            for prot in protected_rel_paths:
                pl = prot.lower()
                if norm_lower == pl or norm_lower.startswith(f"{pl}/"):
                    return prot
            return None

        files_in_scope: List[Dict[str, Any]] = []
        existing_destinations_on_disk: Set[str] = set()

        if request.include_subfolders:
            for dirpath, dirnames, filenames in os.walk(target_dir):
                dpath = Path(dirpath)
                if is_reparse_point_or_symlink(dpath):
                    dirnames.clear()
                    continue

                dir_rel = dpath.relative_to(root_path).as_posix() if dpath != root_path else ""
                matched_parent = _is_protected_rel(dir_rel)
                if matched_parent:
                    skipped_protected_folders.add(matched_parent)
                    dirnames.clear()
                    continue

                # Filter hidden / excluded / protected child directories
                kept_dirs: List[str] = []
                for d in dirnames:
                    if d.startswith("."):
                        continue
                    child_rel = f"{dir_rel}/{d}" if dir_rel else d
                    if child_rel.lower() in protected_lower:
                        skipped_protected_folders.add(child_rel)
                        continue
                    matched_child = _is_protected_rel(child_rel)
                    if matched_child:
                        skipped_protected_folders.add(matched_child)
                        continue
                    kept_dirs.append(d)
                dirnames[:] = kept_dirs

                for fn in filenames:
                    if fn.startswith("."):
                        continue
                    fpath = dpath / fn
                    if is_reparse_point_or_symlink(fpath):
                        continue

                    rel_path = fpath.relative_to(root_path).as_posix()
                    existing_destinations_on_disk.add(rel_path.lower())

                    try:
                        st = fpath.stat()
                        cat = detect_file_category(fpath.name)
                        ext = fpath.suffix.lstrip(".").lower()
                        mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                        files_in_scope.append({
                            "name": fn,
                            "relative_path": rel_path,
                            "size_bytes": st.st_size,
                            "category": cat,
                            "extension": ext,
                            "modified_at": mod_iso,
                            "parent_rel": fpath.parent.relative_to(root_path).as_posix() if fpath.parent != root_path else "",
                        })
                    except (PermissionError, OSError):
                        continue
        else:
            # Only direct children of target_dir (skip if target_dir itself is inside a protected folder)
            target_dir_rel = target_dir.relative_to(root_path).as_posix() if target_dir != root_path else ""
            matched_target = _is_protected_rel(target_dir_rel)
            if matched_target:
                skipped_protected_folders.add(matched_target)
            else:
                for entry in os.scandir(target_dir):
                    if entry.name.startswith("."):
                        continue
                    if is_reparse_point_or_symlink(Path(entry.path)):
                        continue
                    if entry.is_file():
                        fpath = Path(entry.path)
                        rel_path = fpath.relative_to(root_path).as_posix()
                        existing_destinations_on_disk.add(rel_path.lower())
                        try:
                            st = entry.stat()
                            cat = detect_file_category(fpath.name)
                            ext = fpath.suffix.lstrip(".").lower()
                            mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()
                            files_in_scope.append({
                                "name": entry.name,
                                "relative_path": rel_path,
                                "size_bytes": st.st_size,
                                "category": cat,
                                "extension": ext,
                                "modified_at": mod_iso,
                                "parent_rel": fpath.parent.relative_to(root_path).as_posix() if fpath.parent != root_path else "",
                            })
                        except (PermissionError, OSError):
                            continue

        # 2. Compute destination paths based on strategy and synced global preferences
        settings_service = SettingsService(self.db)
        org_settings = settings_service.get_organization_settings()
        saved_org_raw = settings_service._get_setting_json("organization") or {}

        proposed_operations: List[ProposedChangeItem] = []
        planned_destinations: Set[str] = set()
        created_directories: Set[str] = set()
        top_folder_indices: Dict[str, int] = {}

        conflicts_count = 0
        seq = 1

        for f in files_in_scope:
            target_rel_dir = self._compute_target_directory(
                f,
                request.strategy,
                subfolder_prefix,
                request.custom_rules,
                org_settings=org_settings,
                saved_org_raw=saved_org_raw,
                top_folder_indices=top_folder_indices,
            )

            # Check if file is already in target dir
            current_parent = f["parent_rel"]
            if request.move_unorganized_only and current_parent.lower() == target_rel_dir.lower():
                # Already organized
                continue

            dest_rel_path = f"{target_rel_dir}/{f['name']}" if target_rel_dir else f["name"]

            # If target dir is not in created_directories and doesn't exist on disk, add create_directory op
            # Ensure all intermediate ancestor directories are also created hierarchically
            if target_rel_dir:
                parts = Path(target_rel_dir).parts
                current_accum = Path()
                for part in parts:
                    current_accum = current_accum / part
                    dir_rel = current_accum.as_posix()
                    if dir_rel not in created_directories:
                        full_dir = (root_path / dir_rel).resolve()
                        if not full_dir.exists():
                            created_directories.add(dir_rel)
                            proposed_operations.append(
                                ProposedChangeItem(
                                    sequence_no=seq,
                                    operation="create_directory",
                                    source_relative_path=None,
                                    destination_relative_path=dir_rel,
                                    file_name=part,
                                    size_bytes=0,
                                    category="directory",
                                    status="pending",
                                )
                            )
                            seq += 1
                        else:
                            created_directories.add(dir_rel)

            # Conflict checking
            item_status = "pending"
            conflict_reason = None

            dest_lower = dest_rel_path.lower()
            src_lower = f["relative_path"].lower()

            if dest_lower == src_lower:
                # Same path
                continue

            has_disk_collision = (
                dest_lower in existing_destinations_on_disk
                or (root_path / dest_rel_path).resolve().exists()
            ) and dest_lower != src_lower
            has_plan_collision = dest_lower in planned_destinations

            if org_settings.detect_destination_conflicts and (has_disk_collision or has_plan_collision):
                if saved_org_raw.get("conflict_resolution_strategy") == "add_sequence":
                    stem = Path(f["name"]).stem
                    suffix = Path(f["name"]).suffix
                    counter = 1
                    while True:
                        candidate_name = f"{stem}_{counter}{suffix}"
                        candidate_rel = f"{target_rel_dir}/{candidate_name}" if target_rel_dir else candidate_name
                        cand_lower = candidate_rel.lower()
                        cand_exists = (root_path / candidate_rel).resolve().exists()
                        if (
                            cand_lower not in existing_destinations_on_disk
                            and cand_lower not in planned_destinations
                            and not cand_exists
                        ):
                            dest_rel_path = candidate_rel
                            dest_lower = cand_lower
                            break
                        counter += 1
                    conflict_reason = f"Collision auto-resolved using sequence suffix ({dest_rel_path})"
                else:
                    item_status = "conflict"
                    if has_disk_collision:
                        conflict_reason = f"Destination path '{dest_rel_path}' already exists on disk"
                    else:
                        conflict_reason = f"Multiple files planned for destination '{dest_rel_path}'"
                    conflicts_count += 1

            planned_destinations.add(dest_lower)

            proposed_operations.append(
                ProposedChangeItem(
                    sequence_no=seq,
                    operation="move",
                    source_relative_path=f["relative_path"],
                    destination_relative_path=dest_rel_path,
                    file_name=f["name"],
                    size_bytes=f["size_bytes"],
                    category=f["category"],
                    status=item_status,
                    conflict_reason=conflict_reason,
                )
            )
            seq += 1

        # 3. Build structure comparisons
        current_structure = self._build_structure_tree(files_in_scope, is_proposed=False)
        proposed_structure = self._build_proposed_tree(files_in_scope, proposed_operations)

        # 4. Clean up stale unsubmitted preview drafts of the same type for this folder
        stale_drafts = list(
            self.db.execute(
                select(ChangePlan).where(
                    ChangePlan.managed_folder_id == folder.id,
                    ChangePlan.plan_type == "organize",
                    ChangePlan.status == "draft",
                    ChangePlan.created_by == "user",
                )
            )
            .scalars()
            .all()
        )
        for old_draft in stale_drafts:
            self.db.delete(old_draft)
        if stale_drafts:
            self.db.flush()

        # Persist ChangePlan to database as draft
        plan_title = request.title or f"Organize {folder.name} ({request.strategy})"
        plan = ChangePlan(
            managed_folder_id=folder.id,
            title=plan_title,
            plan_type="organize",
            status="draft",
            created_by="user",
        )
        self.db.add(plan)
        self.db.flush()

        for op in proposed_operations:
            item = ChangePlanItem(
                change_plan_id=plan.id,
                operation=op.operation,
                source_relative_path=op.source_relative_path,
                destination_relative_path=op.destination_relative_path,
                expected_size_bytes=op.size_bytes,
                status="conflict" if op.status == "conflict" else "pending",
                conflict_reason=op.conflict_reason,
                sequence_no=op.sequence_no,
            )
            self.db.add(item)
            self.db.flush()
            op.item_id = item.id

        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="create_organization_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={
                "strategy": request.strategy,
                "files_analyzed": len(files_in_scope),
                "operations_count": len(proposed_operations),
                "conflicts_count": conflicts_count,
            },
        )

        files_to_move = sum(1 for op in proposed_operations if op.operation == "move")
        folders_to_create = sum(1 for op in proposed_operations if op.operation == "create_directory")
        total_size = sum(f["size_bytes"] for f in files_in_scope)

        return OrganizationPlanResult(
            change_plan_id=plan.id,
            managed_folder_id=folder.id,
            managed_folder_name=folder.name,
            strategy=request.strategy,
            title=plan.title,
            status=plan.status,
            created_at=plan.created_at,
            files_analyzed_count=len(files_in_scope),
            files_to_move_count=files_to_move,
            folders_to_create_count=folders_to_create,
            conflicts_count=conflicts_count,
            total_size_bytes=total_size,
            protected_folders_skipped_count=len(skipped_protected_folders),
            protected_folders_skipped=sorted(skipped_protected_folders),
            current_structure=current_structure,
            proposed_structure=proposed_structure,
            items=proposed_operations,
        )

    @staticmethod
    def _format_folder_name(
        base_name: str,
        index: int,
        org_settings: OrganizationSettings,
        apply_naming: bool,
        apply_prefix: bool,
    ) -> str:
        """Applies configured naming convention and optional number prefix to a folder name."""
        formatted = base_name
        if apply_naming:
            words = [w for w in re.split(r"[^A-Za-z0-9]+", base_name) if w]
            naming = org_settings.default_folder_naming
            if words:
                if naming == "kebab-case":
                    formatted = "-".join(w.lower() for w in words)
                elif naming == "snake_case":
                    formatted = "_".join(w.lower() for w in words)
                elif naming == "PascalCase":
                    formatted = "".join(w[:1].upper() + w[1:] for w in words)

        if apply_prefix and org_settings.use_number_prefix:
            sep = org_settings.prefix_separator if org_settings.prefix_separator in ("_", "-", " ") else "_"
            formatted = f"{index:02d}{sep}{formatted}"

        return formatted

    def _compute_target_directory(
        self,
        file_info: Dict[str, Any],
        strategy: str,
        subfolder_prefix: str,
        custom_rules: Optional[Dict[str, Any]] = None,
        org_settings: Optional[OrganizationSettings] = None,
        saved_org_raw: Optional[Dict[str, Any]] = None,
        top_folder_indices: Optional[Dict[str, int]] = None,
    ) -> str:
        """Determines target relative directory for a file based on selected strategy."""
        cat = file_info["category"]
        ext = file_info["extension"]
        mod_at = file_info["modified_at"]
        saved_raw = saved_org_raw or {}

        base_target = ""

        if strategy == "by_category":
            if cat == "archive" and "default_archive_folder_name" in saved_raw and org_settings and org_settings.default_archive_folder_name.strip():
                folder_name = org_settings.default_archive_folder_name.strip()
            else:
                folder_name = CATEGORY_FOLDER_MAP.get(cat, "Others")
            base_target = folder_name
        elif strategy == "by_date":
            try:
                dt = datetime.fromisoformat(mod_at)
                base_target = f"{dt.year}/{dt.strftime('%Y-%m')}"
            except Exception:
                base_target = "Unknown_Date"
        elif strategy == "by_extension":
            base_target = ext.upper() if ext else "NO_EXT"
        elif strategy == "by_project":
            if cat == "archive" and "default_archive_folder_name" in saved_raw and org_settings and org_settings.default_archive_folder_name.strip():
                base_target = org_settings.default_archive_folder_name.strip()
            else:
                base_target = PROJECT_CATEGORY_MAP.get(cat, "Resources")
        elif strategy == "custom" and custom_rules:
            # Custom mapping by extension or category in custom_rules
            mapping = custom_rules.get("mapping", {})
            if ext in mapping:
                base_target = mapping[ext]
            elif cat in mapping:
                base_target = mapping[cat]
            else:
                base_target = custom_rules.get("default", "Others")
        else:
            base_target = CATEGORY_FOLDER_MAP.get(cat, "Others")

        apply_naming = "default_folder_naming" in saved_raw
        apply_prefix = "use_number_prefix" in saved_raw or "prefix_separator" in saved_raw
        if org_settings and (apply_naming or apply_prefix) and strategy in ("by_category", "by_project", "custom") and base_target:
            segments = base_target.split("/")
            first_seg = segments[0]
            if cat in CATEGORY_INDEX_MAP:
                idx = CATEGORY_INDEX_MAP[cat]
            elif top_folder_indices is not None:
                if first_seg not in top_folder_indices:
                    top_folder_indices[first_seg] = len(top_folder_indices) + 1
                idx = top_folder_indices[first_seg]
            else:
                idx = 1
            segments[0] = self._format_folder_name(
                first_seg,
                idx,
                org_settings,
                apply_naming=apply_naming,
                apply_prefix=apply_prefix,
            )
            base_target = "/".join(segments)

        if subfolder_prefix:
            return f"{subfolder_prefix}/{base_target}".strip("/")
        return base_target.strip("/")

    def _build_structure_tree(
        self, files: List[Dict[str, Any]], is_proposed: bool = False
    ) -> List[StructureTreeNode]:
        """Builds hierarchical folder summary for current structure."""
        dir_stats: Dict[str, Dict[str, Any]] = {}

        for f in files:
            parent = f["parent_rel"]
            if parent not in dir_stats:
                dir_stats[parent] = {"files_count": 0, "size_bytes": 0}
            dir_stats[parent]["files_count"] += 1
            dir_stats[parent]["size_bytes"] += f["size_bytes"]

        nodes: List[StructureTreeNode] = []
        for dpath, stats in sorted(dir_stats.items()):
            display_name = Path(dpath).name if dpath else "Root"
            nodes.append(
                StructureTreeNode(
                    name=display_name,
                    relative_path=dpath,
                    item_type="directory",
                    files_count=stats["files_count"],
                    size_bytes=stats["size_bytes"],
                    is_new=False,
                )
            )
        return nodes

    def _build_proposed_tree(
        self, files: List[Dict[str, Any]], operations: List[ProposedChangeItem]
    ) -> List[StructureTreeNode]:
        """Simulates proposed structure after applying planned operations."""
        # Map source path to destination path
        move_map = {
            op.source_relative_path: op.destination_relative_path
            for op in operations
            if op.operation == "move" and op.status != "conflict" and op.source_relative_path
        }

        created_dirs = {
            op.destination_relative_path
            for op in operations
            if op.operation == "create_directory"
        }

        dir_stats: Dict[str, Dict[str, Any]] = {}
        for d in created_dirs:
            dir_stats[d] = {"files_count": 0, "size_bytes": 0, "is_new": True}

        for f in files:
            final_path = move_map.get(f["relative_path"], f["relative_path"])
            parent = Path(final_path).parent.as_posix()
            if parent == ".":
                parent = ""

            if parent not in dir_stats:
                dir_stats[parent] = {"files_count": 0, "size_bytes": 0, "is_new": parent in created_dirs}

            dir_stats[parent]["files_count"] += 1
            dir_stats[parent]["size_bytes"] += f["size_bytes"]

        nodes: List[StructureTreeNode] = []
        for dpath, stats in sorted(dir_stats.items()):
            display_name = Path(dpath).name if dpath else "Root"
            nodes.append(
                StructureTreeNode(
                    name=display_name,
                    relative_path=dpath,
                    item_type="directory",
                    files_count=stats["files_count"],
                    size_bytes=stats["size_bytes"],
                    is_new=stats.get("is_new", False),
                )
            )
        return nodes

    # ==========================================
    # Protected Project & Tool Folders (Flagging & AI/Smart Auto-Detect)
    # ==========================================
    @staticmethod
    def _protected_setting_key(folder_id: str) -> str:
        return f"protected_subfolders:{folder_id}"

    def _load_saved_protected_folders(self, folder_id: str) -> List[ProtectedSubfolderItem]:
        setting = self.db.get(AppSetting, self._protected_setting_key(folder_id))
        if not setting or not setting.value_json:
            return []
        try:
            raw = json.loads(setting.value_json)
            if isinstance(raw, list):
                return [ProtectedSubfolderItem(**item) for item in raw]
        except Exception as e:
            logger.warning(f"Failed to parse protected folders setting for {folder_id}: {e}")
        return []

    def _save_protected_folders(self, folder_id: str, items: List[ProtectedSubfolderItem]) -> None:
        key = self._protected_setting_key(folder_id)
        val_str = json.dumps([item.model_dump() for item in items])
        setting = self.db.get(AppSetting, key)
        if setting:
            setting.value_json = val_str
            setting.updated_at = utc_now_iso()
        else:
            setting = AppSetting(key=key, value_json=val_str, updated_at=utc_now_iso())
            self.db.add(setting)
        self.db.commit()

    def _inspect_subfolder_for_protection(
        self, folder_path: Path, rel_path: str
    ) -> Optional[Dict[str, Any]]:
        """Classifies whether a subfolder is a self-contained binary/tool bundle, code project, or SDK."""
        name_lower = folder_path.name.lower()
        file_names_lower: Set[str] = set()
        child_dir_names_lower: Set[str] = set()
        ext_counts: Dict[str, int] = {}

        try:
            with os.scandir(folder_path) as it:
                for entry in it:
                    p = Path(entry.path)
                    if is_reparse_point_or_symlink(p):
                        continue
                    en_lower = entry.name.lower()
                    if entry.is_dir(follow_symlinks=False):
                        child_dir_names_lower.add(en_lower)
                    elif entry.is_file(follow_symlinks=False):
                        file_names_lower.add(en_lower)
                        ext = p.suffix.lower()
                        if ext:
                            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        except (PermissionError, OSError):
            return None

        # Check binary / DLL runtime count (also check 1 level deeper e.g. app/bin/*.dll)
        dll_count = sum(ext_counts.get(ext, 0) for ext in BINARY_BUNDLE_EXTENSIONS)
        exe_count = ext_counts.get(".exe", 0)
        support_count = sum(ext_counts.get(ext, 0) for ext in SUPPORT_CONFIG_EXTENSIONS)

        # 1. Explicit project / repository markers take top priority (even if folder matches generic name)
        if ".git" in child_dir_names_lower:
            return {
                "category": "code_project",
                "confidence": 0.99,
                "reason": "Git repository (.git) terdeteksi — struktur source code dijaga tetap utuh.",
            }

        matched_marker = next((m for m in PROJECT_MARKER_FILES if m in file_names_lower), None)
        if not matched_marker:
            matched_marker = next(
                (fn for fn in file_names_lower if Path(fn).suffix.lower() in PROJECT_MARKER_EXTENSIONS),
                None,
            )
        if matched_marker:
            return {
                "category": "code_project",
                "confidence": 0.97,
                "reason": f"Project marker '{matched_marker}' terdeteksi — folder project dilindungi.",
            }

        # 2. SDK / Python venv / runtime environment layout
        if "pyvenv.cfg" in file_names_lower or (
            ({"bin", "scripts"} & child_dir_names_lower) and ({"lib", "include"} & child_dir_names_lower)
        ):
            return {
                "category": "sdk_runtime",
                "confidence": 0.96,
                "reason": "Struktur runtime / virtual environment terdeteksi.",
            }

        # 3. Binary / DLL tool bundle (e.g. platform-tools with adb.exe & *.dll)
        if dll_count > 0 or (exe_count >= 1 and support_count >= 1) or name_lower in KNOWN_TOOL_OR_SDK_FOLDER_NAMES:
            if name_lower in KNOWN_TOOL_OR_SDK_FOLDER_NAMES and dll_count == 0 and exe_count == 0:
                reason = f"Direktori tool/SDK '{folder_path.name}' dikenal sebagai bundle aplikasi."
                category = "sdk_runtime"
                conf = 0.92
            else:
                parts: List[str] = []
                if exe_count:
                    parts.append(f"{exe_count} .exe")
                if dll_count:
                    parts.append(f"{dll_count} .dll/binary")
                if support_count:
                    parts.append(f"{support_count} config/data")
                detail = ", ".join(parts) if parts else folder_path.name
                reason = f"Tool / binary bundle ({detail}) — file .dll & .exe tidak akan dipisah."
                category = "tool_bundle"
                conf = 0.97
            return {
                "category": category,
                "confidence": conf,
                "reason": reason,
            }

        return None

    def _scan_subfolders_for_ui(
        self, root_path: Path, protected_items: List[ProtectedSubfolderItem]
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Collects depth 1-2 non-hidden subdirectories for dropdown selection and heuristic inspection."""
        existing_rel_lower = {it.relative_path.lower() for it in protected_items}
        available: List[str] = []
        candidates_summary: List[Dict[str, Any]] = []

        def _scan_dir(parent: Path, prefix: str, depth: int) -> None:
            if depth > 2:
                return
            try:
                entries = sorted(os.scandir(parent), key=lambda e: e.name.lower())
            except (PermissionError, OSError):
                return

            for entry in entries:
                if entry.name.startswith("."):
                    continue
                p = Path(entry.path)
                if is_reparse_point_or_symlink(p) or not entry.is_dir(follow_symlinks=False):
                    continue
                rel = f"{prefix}/{entry.name}" if prefix else entry.name
                if rel.lower() not in existing_rel_lower:
                    available.append(rel)
                    if entry.name.lower() not in ORGANIZED_CATEGORY_FOLDER_NAMES:
                        try:
                            sample_files = [
                                f.name for f in list(p.iterdir())[:12] if f.is_file()
                            ]
                            if sample_files:
                                candidates_summary.append({"relative_path": rel, "files": sample_files})
                        except (PermissionError, OSError):
                            pass
                _scan_dir(p, rel, depth + 1)

        _scan_dir(root_path, "", 1)
        return available, candidates_summary

    def _run_heuristic_auto_detect(
        self, folder: ManagedFolder, preserve_disabled: bool = True
    ) -> Tuple[List[ProtectedSubfolderItem], int]:
        """Runs deterministic smart detection across depth 1-2 subfolders and returns updated list + new count."""
        root_path = Path(folder.root_path).resolve()
        items = self._load_saved_protected_folders(folder.id)
        by_path = {it.relative_path.lower(): it for it in items}
        newly_added = 0

        if not root_path.exists() or not root_path.is_dir():
            return items, 0

        def _walk_level(current: Path, prefix: str, depth: int) -> None:
            nonlocal newly_added
            if depth > 2:
                return
            try:
                entries = sorted(os.scandir(current), key=lambda e: e.name.lower())
            except (PermissionError, OSError):
                return

            for entry in entries:
                if entry.name.startswith("."):
                    continue
                p = Path(entry.path)
                if is_reparse_point_or_symlink(p) or not entry.is_dir(follow_symlinks=False):
                    continue
                rel = f"{prefix}/{entry.name}" if prefix else entry.name
                rel_lower = rel.lower()

                existing = by_path.get(rel_lower)
                if existing:
                    if not preserve_disabled and not existing.is_protected:
                        existing.is_protected = True
                        newly_added += 1
                    # Already tracked; don't redundantly walk inside if active
                    if existing.is_protected:
                        continue

                verdict = self._inspect_subfolder_for_protection(p, rel)
                if verdict and not existing:
                    new_item = ProtectedSubfolderItem(
                        id=str(uuid.uuid4()),
                        managed_folder_id=folder.id,
                        relative_path=rel,
                        name=entry.name,
                        source="smart_detect",
                        category=verdict["category"],
                        reason=verdict["reason"],
                        confidence=verdict["confidence"],
                        is_protected=True,
                        created_at=utc_now_iso(),
                    )
                    items.append(new_item)
                    by_path[rel_lower] = new_item
                    newly_added += 1
                    continue

                _walk_level(p, rel, depth + 1)

        _walk_level(root_path, "", 1)

        if newly_added > 0:
            self._save_protected_folders(folder.id, items)

        return items, newly_added

    def list_protected_folders(self, folder_id: str) -> ProtectedFoldersListResponse:
        folder = self._get_managed_folder(folder_id)
        root_path = Path(folder.root_path).resolve()
        items = self._load_saved_protected_folders(folder.id)
        available, _ = self._scan_subfolders_for_ui(root_path, items)
        return ProtectedFoldersListResponse(
            managed_folder_id=folder.id,
            protected_folders=items,
            available_subfolders=available,
        )

    async def detect_protected_folders(
        self, folder_id: str, use_ai: bool = True
    ) -> ProtectedFoldersDetectResponse:
        folder = self._get_managed_folder(folder_id)
        root_path = Path(folder.root_path).resolve()
        if not root_path.exists():
            raise ValueError(f"Managed Folder path does not exist on disk: {root_path}")

        items, newly_added = self._run_heuristic_auto_detect(folder, preserve_disabled=True)
        detection_mode = "smart_heuristic"
        available, candidates = self._scan_subfolders_for_ui(root_path, items)

        # Optional AI enhancement via 9Router for ambiguous remaining folders
        if use_ai and candidates:
            try:
                from backend.app.schemas.router import RouterChatMessage, RouterChatRequest
                from backend.app.services.router_gateway import RouterGatewayService

                gateway = RouterGatewayService(self.db)
                ai_cfg = SettingsService(self.db).get_ai_settings()
                if ai_cfg.default_model and (
                    getattr(ai_cfg, "router_endpoint", None) or getattr(ai_cfg, "nine_router_endpoint", None)
                ):
                    prompt = (
                        "You are classifying subfolders inside a desktop user's folder to decide which folders "
                        "should be PROTECTED from automated 'Organize by File Type' (for example: portable apps, "
                        "CLI/platform tools with DLL/EXE files, game directories, SDKs, or software projects). "
                        "Do NOT flag normal personal folders like 'Photos', 'Invoices', or 'My Documents'. "
                        f"Candidates (JSON): {json.dumps(candidates[:20])}. "
                        'Respond strictly with JSON object: {"protect": [{"relative_path": "...", "category": "tool_bundle|code_project|sdk_runtime", "reason": "..."}]}.'
                    )
                    ai_res = await gateway.chat_completion(
                        RouterChatRequest(
                            messages=[RouterChatMessage(role="user", content=prompt)],
                            temperature=0.1,
                            max_tokens=400,
                            json_mode=True,
                            timeout_seconds=3,
                        )
                    )
                    detection_mode = "hybrid_ai"
                    parsed = ai_res.parsed_json or {}
                    existing_lower = {it.relative_path.lower() for it in items}
                    for entry in parsed.get("protect", []) if isinstance(parsed, dict) else []:
                        rel = str(entry.get("relative_path", "")).strip().strip("/\\")
                        if not rel or rel.lower() in existing_lower:
                            continue
                        try:
                            target = PathValidator.resolve_and_verify_scope(folder, rel)
                            if not target.exists() or not target.is_dir():
                                continue
                        except Exception:
                            continue
                        new_item = ProtectedSubfolderItem(
                            id=str(uuid.uuid4()),
                            managed_folder_id=folder.id,
                            relative_path=rel,
                            name=Path(rel).name,
                            source="ai",
                            category=str(entry.get("category") or "tool_bundle"),
                            reason=str(entry.get("reason") or "Terdeteksi oleh AI sebagai folder tool/project."),
                            confidence=0.9,
                            is_protected=True,
                            created_at=utc_now_iso(),
                        )
                        items.append(new_item)
                        existing_lower.add(rel.lower())
                        newly_added += 1
                    if newly_added > 0:
                        self._save_protected_folders(folder.id, items)
                    available, _ = self._scan_subfolders_for_ui(root_path, items)
            except Exception as e:
                logger.debug(f"AI folder protection enrichment skipped (fallback to heuristic): {e}")

        self.audit_repo.record(
            actor_type="system" if newly_added else "user",
            action="protected_folders_detected",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"newly_flagged": newly_added, "mode": detection_mode},
        )

        return ProtectedFoldersDetectResponse(
            managed_folder_id=folder.id,
            newly_flagged_count=newly_added,
            total_protected_count=sum(1 for it in items if it.is_protected),
            detection_mode=detection_mode,
            protected_folders=items,
            available_subfolders=available,
        )

    def add_protected_folder(
        self, folder_id: str, payload: ProtectedSubfolderCreate
    ) -> ProtectedSubfolderItem:
        folder = self._get_managed_folder(folder_id)
        rel_clean = payload.relative_path.strip().replace("\\", "/").strip("/")
        target = PathValidator.resolve_and_verify_scope(folder, rel_clean)
        if not target.exists() or not target.is_dir():
            raise ValueError(f"Subfolder '{payload.relative_path}' does not exist or is not a directory")

        canonical_rel = target.relative_to(Path(folder.root_path).resolve()).as_posix()
        if not canonical_rel or canonical_rel == ".":
            raise ValueError("Cannot flag root Managed Folder itself; choose a subfolder inside it.")

        items = self._load_saved_protected_folders(folder.id)
        for existing in items:
            if existing.relative_path.lower() == canonical_rel.lower():
                existing.is_protected = True
                existing.source = "manual"
                if payload.reason:
                    existing.reason = payload.reason.strip()
                self._save_protected_folders(folder.id, items)
                return existing

        new_item = ProtectedSubfolderItem(
            id=str(uuid.uuid4()),
            managed_folder_id=folder.id,
            relative_path=canonical_rel,
            name=target.name,
            source="manual",
            category="custom",
            reason=(payload.reason or "Ditandai manual agar isi folder tidak ikut di-organize.").strip(),
            confidence=1.0,
            is_protected=True,
            created_at=utc_now_iso(),
        )
        items.append(new_item)
        self._save_protected_folders(folder.id, items)

        self.audit_repo.record(
            actor_type="user",
            action="protected_folder_added",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"relative_path": canonical_rel},
        )
        return new_item

    def toggle_protected_folder(
        self, folder_id: str, item_id: str, is_protected: bool
    ) -> ProtectedSubfolderItem:
        folder = self._get_managed_folder(folder_id)
        items = self._load_saved_protected_folders(folder.id)
        for item in items:
            if item.id == item_id:
                item.is_protected = is_protected
                self._save_protected_folders(folder.id, items)
                self.audit_repo.record(
                    actor_type="user",
                    action="protected_folder_toggled",
                    entity_type="managed_folder",
                    entity_id=folder.id,
                    details={"relative_path": item.relative_path, "is_protected": is_protected},
                )
                return item
        raise ValueError(f"Protected folder entry '{item_id}' not found")

    def delete_protected_folder(self, folder_id: str, item_id: str) -> bool:
        folder = self._get_managed_folder(folder_id)
        items = self._load_saved_protected_folders(folder.id)
        filtered = [it for it in items if it.id != item_id]
        if len(filtered) == len(items):
            return False
        self._save_protected_folders(folder.id, filtered)
        self.audit_repo.record(
            actor_type="user",
            action="protected_folder_removed",
            entity_type="managed_folder",
            entity_id=folder.id,
            details={"item_id": item_id},
        )
        return True

    def get_active_protected_rel_paths(
        self, folder_id: str, auto_detect_new: bool = True
    ) -> Set[str]:
        """Returns normalized active protected subfolder paths plus directory exclusions."""
        folder = self._get_managed_folder(folder_id)
        if auto_detect_new:
            items, _ = self._run_heuristic_auto_detect(folder, preserve_disabled=True)
        else:
            items = self._load_saved_protected_folders(folder.id)

        active: Set[str] = {
            it.relative_path.replace("\\", "/").strip("/")
            for it in items
            if it.is_protected and it.relative_path.strip("/")
        }

        # Also respect directory exclusions configured in Managed Folders
        try:
            mf_service = ManagedFolderService(self.db)
            for excl in mf_service.get_folder_exclusions(folder.id):
                if excl.is_enabled and excl.exclusion_type == "directory" and excl.value.strip():
                    active.add(excl.value.replace("\\", "/").strip("/"))
        except Exception:
            pass

        return active
