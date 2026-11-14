import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.models.change_plan import ChangePlan, ChangePlanItem
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.smart_rename import (
    BatchOCRJobStatus,
    ItemOCRAnalyzeResponse,
    QuickOCRRenameResponse,
    SmartRenamePlanRequest,
    SmartRenamePlanResult,
    SmartRenamePreviewItem,
)
from backend.app.services.filesystem import detect_file_category, is_reparse_point_or_symlink
from backend.app.services.managed_folder import PathValidator


ILLEGAL_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

BATCH_OCR_JOBS: Dict[str, Dict[str, Any]] = {}


def clean_filename_string(s: str) -> str:
    """Removes invalid characters and trims whitespace."""
    cleaned = ILLEGAL_CHARS_PATTERN.sub("", s)
    return cleaned.strip()


class SmartRenameService:
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

    async def generate_plan(self, request: SmartRenamePlanRequest) -> SmartRenamePlanResult:
        """Generates a smart rename preview and Change Plan with collision resolution.
        Strictly read-only; no filesystem mutations are performed."""
        folder = self._get_managed_folder(request.managed_folder_id)
        root_path = Path(folder.root_path).resolve()

        if not root_path.exists():
            raise ValueError(f"Managed Folder path does not exist on disk: {root_path}")

        # 1. Collect target files
        candidate_files: List[Dict[str, Any]] = []

        if request.target_relative_paths:
            # Specific files selected
            for rel in request.target_relative_paths:
                fpath = PathValidator.resolve_and_verify_scope(folder, rel)
                if not fpath.exists() or not fpath.is_file():
                    continue
                if is_reparse_point_or_symlink(fpath):
                    continue

                st = fpath.stat()
                cat = detect_file_category(fpath.name)
                ext = fpath.suffix.lstrip(".")
                mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()

                candidate_files.append({
                    "path": fpath,
                    "name": fpath.name,
                    "stem": fpath.stem,
                    "extension": ext,
                    "relative_path": fpath.relative_to(root_path).as_posix(),
                    "parent_rel": fpath.parent.relative_to(root_path).as_posix() if fpath.parent != root_path else "",
                    "size_bytes": st.st_size,
                    "category": cat,
                    "modified_at": mod_iso,
                })
        else:
            # Subfolder or whole folder
            target_dir = root_path
            if request.target_subfolder and request.target_subfolder.strip():
                sub_clean = Path(request.target_subfolder.strip()).as_posix().strip("/")
                target_dir = PathValidator.resolve_and_verify_scope(folder, sub_clean)
                if not target_dir.exists() or not target_dir.is_dir():
                    raise ValueError(f"Target subfolder '{request.target_subfolder}' does not exist")

            from backend.app.services.organization import OrganizationService

            protected_paths = OrganizationService(self.db).get_active_protected_rel_paths(
                folder.id, auto_detect_new=False
            )
            protected_lower = {p.lower() for p in protected_paths}

            for dirpath, dirnames, filenames in os.walk(target_dir):
                dpath = Path(dirpath)
                if is_reparse_point_or_symlink(dpath):
                    dirnames.clear()
                    continue

                dir_rel = dpath.relative_to(root_path).as_posix() if dpath != root_path else ""
                if dir_rel and any(
                    dir_rel.lower() == p or dir_rel.lower().startswith(f"{p}/")
                    for p in protected_lower
                ):
                    dirnames.clear()
                    continue

                kept_dirs = []
                for d in dirnames:
                    if d.startswith("."):
                        continue
                    child_rel = f"{dir_rel}/{d}" if dir_rel else d
                    if any(
                        child_rel.lower() == p or child_rel.lower().startswith(f"{p}/")
                        for p in protected_lower
                    ):
                        continue
                    kept_dirs.append(d)
                dirnames[:] = kept_dirs

                for fn in filenames:
                    if fn.startswith("."):
                        continue
                    fpath = dpath / fn
                    if is_reparse_point_or_symlink(fpath):
                        continue

                    try:
                        st = fpath.stat()
                        cat = detect_file_category(fpath.name)
                        ext = fpath.suffix.lstrip(".")
                        mod_iso = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat()

                        candidate_files.append({
                            "path": fpath,
                            "name": fn,
                            "stem": fpath.stem,
                            "extension": ext,
                            "relative_path": fpath.relative_to(root_path).as_posix(),
                            "parent_rel": fpath.parent.relative_to(root_path).as_posix() if fpath.parent != root_path else "",
                            "size_bytes": st.st_size,
                            "category": cat,
                            "modified_at": mod_iso,
                        })
                    except (PermissionError, OSError):
                        continue

        # Sort files by relative path for deterministic processing
        candidate_files.sort(key=lambda x: x["relative_path"].lower())

        # 2. Generate proposed names and detect collisions per directory
        preview_items: List[SmartRenamePreviewItem] = []
        conflicts_count = 0
        to_rename_count = 0
        unchanged_count = 0
        total_size = 0

        # Group candidates by parent directory to detect directory-level collisions
        dir_batches: Dict[str, List[Dict[str, Any]]] = {}
        for c in candidate_files:
            dir_batches.setdefault(c["parent_rel"], []).append(c)

        seq = 1

        for parent_rel, files in dir_batches.items():
            dir_path = (root_path / parent_rel).resolve() if parent_rel else root_path
            # Get existing filenames on disk in this directory
            existing_filenames: Set[str] = set()
            if dir_path.exists():
                try:
                    for entry in os.scandir(dir_path):
                        existing_filenames.add(entry.name.lower())
                except OSError:
                    pass

            planned_names_in_dir: Set[str] = set()

            run_sync_ocr = getattr(request, "sync_ocr", False) or (
                getattr(request, "use_ai_content", False)
                and request.target_relative_paths
                and len(request.target_relative_paths) <= 3
            )

            for idx, f in enumerate(files, start=1):
                total_size += f["size_bytes"]
                original_name = f["name"]

                proposed_name = await self._compute_proposed_name(
                    file_info=f,
                    strategy=request.strategy,
                    pattern=request.pattern,
                    case_transform=request.case_transform,
                    space_replacement=request.space_replacement,
                    keep_extension=request.keep_extension,
                    prefix=request.prefix,
                    suffix=request.suffix,
                    sequence_index=idx,
                    folder_name=folder.name,
                    folder=folder,
                    use_ai_content=getattr(request, "use_ai_content", False),
                    run_sync_ocr=run_sync_ocr,
                )

                # Check if proposed name equals original
                if proposed_name == original_name:
                    unchanged_count += 1
                    preview_items.append(
                        SmartRenamePreviewItem(
                            sequence_no=seq,
                            source_relative_path=f["relative_path"],
                            original_name=original_name,
                            proposed_name=proposed_name,
                            destination_relative_path=f["relative_path"],
                            size_bytes=f["size_bytes"],
                            extension=f["extension"],
                            category=f["category"],
                            status="unchanged",
                            conflict_reason=None,
                        )
                    )
                    seq += 1
                    continue

                # Collision detection against disk & intra-batch
                item_status = "ready"
                conflict_reason = None
                dest_fn_lower = proposed_name.lower()
                orig_fn_lower = original_name.lower()

                is_disk_collision = (dest_fn_lower in existing_filenames) and (dest_fn_lower != orig_fn_lower)
                is_batch_collision = dest_fn_lower in planned_names_in_dir

                if is_disk_collision or is_batch_collision:
                    if request.add_sequence_on_collision:
                        # Attempt to auto-resolve by adding sequence number
                        resolved_name = self._resolve_name_collision(
                            proposed_name, existing_filenames, planned_names_in_dir, orig_fn_lower
                        )
                        proposed_name = resolved_name
                        dest_fn_lower = proposed_name.lower()
                    else:
                        item_status = "conflict"
                        conflict_reason = f"File with name '{proposed_name}' already exists in this folder"
                        conflicts_count += 1

                planned_names_in_dir.add(dest_fn_lower)

                new_rel_path = f"{parent_rel}/{proposed_name}" if parent_rel else proposed_name

                if item_status == "ready":
                    to_rename_count += 1

                preview_items.append(
                    SmartRenamePreviewItem(
                        sequence_no=seq,
                        source_relative_path=f["relative_path"],
                        original_name=original_name,
                        proposed_name=proposed_name,
                        destination_relative_path=new_rel_path,
                        size_bytes=f["size_bytes"],
                        extension=f["extension"],
                        category=f["category"],
                        status=item_status,
                        conflict_reason=conflict_reason,
                    )
                )
                seq += 1

        # 3. Clean up stale unsubmitted preview drafts of the same type for this folder
        stale_drafts = list(
            self.db.execute(
                select(ChangePlan).where(
                    ChangePlan.managed_folder_id == folder.id,
                    ChangePlan.plan_type == "rename",
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

        # Persist draft ChangePlan in database
        plan_title = request.title or f"Smart Rename {folder.name} ({request.strategy})"
        plan = ChangePlan(
            managed_folder_id=folder.id,
            title=plan_title,
            plan_type="rename",
            status="draft",
            created_by="user",
        )
        self.db.add(plan)
        self.db.flush()

        for item in preview_items:
            # Only store items that actually represent a rename operation
            if item.status == "unchanged" and request.skip_compliant_files:
                continue

            change_item = ChangePlanItem(
                change_plan_id=plan.id,
                operation="rename",
                source_relative_path=item.source_relative_path,
                destination_relative_path=item.destination_relative_path,
                expected_size_bytes=item.size_bytes,
                status="conflict" if item.status == "conflict" else "pending",
                conflict_reason=item.conflict_reason,
                sequence_no=item.sequence_no,
            )
            self.db.add(change_item)
            self.db.flush()
            item.item_id = change_item.id

        self.db.commit()
        self.db.refresh(plan)

        self.audit_repo.record(
            action="create_rename_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            actor_type="user",
            details={
                "strategy": request.strategy,
                "files_analyzed": len(candidate_files),
                "to_rename": to_rename_count,
                "unchanged": unchanged_count,
                "conflicts": conflicts_count,
            },
        )

        return SmartRenamePlanResult(
            change_plan_id=plan.id,
            managed_folder_id=folder.id,
            managed_folder_name=folder.name,
            strategy=request.strategy,
            title=plan.title,
            status=plan.status,
            created_at=plan.created_at,
            files_analyzed_count=len(candidate_files),
            files_to_rename_count=to_rename_count,
            files_unchanged_count=unchanged_count,
            conflicts_count=conflicts_count,
            total_size_bytes=total_size,
            items=preview_items,
        )

    async def _compute_proposed_name(
        self,
        file_info: Dict[str, Any],
        strategy: str,
        pattern: Optional[str],
        case_transform: str,
        space_replacement: str,
        keep_extension: bool,
        prefix: Optional[str] = "",
        suffix: Optional[str] = "",
        sequence_index: int = 1,
        folder_name: str = "",
        folder: Optional[ManagedFolder] = None,
        use_ai_content: bool = False,
        run_sync_ocr: bool = False,
    ) -> str:
        stem = file_info["stem"]
        ext = file_info["extension"]
        cat = file_info["category"]
        mod_at = file_info["modified_at"]

        base_name = stem

        # Content/OCR Understanding Strategy
        if (strategy == "describe_content" or use_ai_content) and folder:
            is_image = cat == "image" or ext.lower() in ("png", "jpg", "jpeg", "webp", "bmp", "tiff")
            is_doc = cat == "document" or ext.lower() in ("pdf", "docx")

            content_text = ""
            if run_sync_ocr and (is_image or ext.lower() == "pdf"):
                try:
                    from backend.app.schemas.ocr import OCRExtractRequest
                    from backend.app.services.ocr_service import PaddleOCRService

                    ocr_svc = PaddleOCRService(self.db)
                    ocr_res = ocr_svc.extract_text(
                        OCRExtractRequest(
                            folder_id=folder.id,
                            relative_path=file_info["relative_path"],
                            max_pages=2,
                        )
                    )
                    if ocr_res.success and ocr_res.full_text:
                        content_text = ocr_res.full_text.strip()
                except Exception as e:
                    logger.warning("PaddleOCR skipped during smart rename for %s: %s", file_info["name"], e)

            if content_text:
                ai_suggested = await self._generate_ai_name_from_content(
                    filename=file_info["name"],
                    category=cat,
                    content_snippet=content_text[:800],
                )
                if ai_suggested:
                    base_name = ai_suggested
            elif is_image:
                cleaned = re.sub(r"^(IMG|DSC|PHOTO|FILE|DOC|SCAN|SCREENSHOT)[\-_0-9]+", "", base_name, flags=re.IGNORECASE)
                cleaned = clean_filename_string(cleaned).strip(" _-")
                base_name = cleaned if cleaned else f"image_{sequence_index:03d}"

            if space_replacement == "_":
                base_name = re.sub(r"[\s\-]+", "_", base_name)
            elif space_replacement == "-":
                base_name = re.sub(r"[\s\_]+", "-", base_name)

        elif strategy == "make_consistent":
            base_name = clean_filename_string(base_name)
            # Replace spaces
            if space_replacement == "_":
                base_name = re.sub(r"[\s\-]+", "_", base_name)
            elif space_replacement == "-":
                base_name = re.sub(r"[\s\_]+", "-", base_name)

            # Strip duplicate separators
            base_name = re.sub(r"_{2,}", "_", base_name)
            base_name = re.sub(r"-{2,}", "-", base_name)
            base_name = base_name.strip(" _-")

        elif strategy == "add_meaningful":
            # Strip noise words like IMG_, DSC_, Screenshot, copy, (1), etc.
            cleaned = re.sub(r"^(IMG|DSC|PHOTO|FILE|DOC|SCAN)[\-_0-9]+", "", base_name, flags=re.IGNORECASE)
            cleaned = re.sub(r"\b(copy|v\d+|final|draft|new)\b", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\(\d+\)", "", cleaned)
            cleaned = clean_filename_string(cleaned).strip(" _-")

            if cleaned:
                base_name = cleaned
            else:
                # Fallback to category + number
                base_name = f"{cat}_{sequence_index:03d}"

            if space_replacement == "_":
                base_name = re.sub(r"[\s\-]+", "_", base_name)
            elif space_replacement == "-":
                base_name = re.sub(r"[\s\_]+", "-", base_name)

        elif strategy == "pattern" and pattern:
            # Pattern format with variables
            dt_str = "unknown_date"
            try:
                dt_str = datetime.fromisoformat(mod_at).strftime("%Y-%m-%d")
            except Exception:
                pass

            clean_stem = clean_filename_string(stem)
            tmpl = pattern
            tmpl = tmpl.replace("{name}", clean_stem)
            tmpl = tmpl.replace("{project}", clean_filename_string(folder_name))
            tmpl = tmpl.replace("{type}", cat)
            tmpl = tmpl.replace("{date}", dt_str)
            tmpl = tmpl.replace("{number}", f"{sequence_index:03d}")
            tmpl = tmpl.replace("{ext}", ext)

            base_name = clean_filename_string(tmpl)
            if space_replacement == "_":
                base_name = re.sub(r"\s+", "_", base_name)
            elif space_replacement == "-":
                base_name = re.sub(r"\s+", "-", base_name)

        # Apply casing to base_name
        if case_transform == "lower":
            base_name = base_name.lower()
        elif case_transform == "upper":
            base_name = base_name.upper()
        elif case_transform == "title":
            base_name = base_name.title()

        # Add prefix and suffix
        p_clean = clean_filename_string(prefix or "")
        s_clean = clean_filename_string(suffix or "")
        final_base = f"{p_clean}{base_name}{s_clean}".strip(" _-")

        if not final_base:
            final_base = f"file_{sequence_index:03d}"

        # Extension handling
        if keep_extension and ext:
            final_ext = ext.lower() if case_transform == "lower" else ext
            return f"{final_base}.{final_ext}"
        return final_base

    async def _generate_ai_name_from_content(
        self,
        filename: str,
        category: str,
        content_snippet: str,
    ) -> Optional[str]:
        """Uses 9Router (with OpenRouter auto-fallback) to generate a concise, clean filename from OCR/content."""
        try:
            from backend.app.schemas.router_gateway import RouterChatMessage, RouterChatRequest
            from backend.app.services.router_gateway import RouterGatewayService

            gateway = RouterGatewayService(self.db)
            prompt = (
                f"Berdasarkan teks OCR hasil pembacaan berkas '{filename}' (kategori {category}) berikut:\n"
                f"\"\"\"\n{content_snippet}\n\"\"\"\n\n"
                f"Buat satu nama berkas baru yang sangat deskriptif, ringkas (maksimal 3-5 kata), "
                f"dan relevan dengan isi dokumen/gambar (misal: 'Invoice_Telkom_Oktober_2026', 'Struk_Kopi_Kenangan', 'KTP_Nama_Lengkap', 'Sertifikat_React').\n"
                f"HANYA kembalikan nama dasar (stem saja, TANPA ekstensi file, TANPA tanda kutip, TANPA penjelasan)."
            )

            res = await gateway.chat_completion(
                RouterChatRequest(
                    messages=[
                        RouterChatMessage(role="system", content="You generate concise, descriptive filenames without extensions."),
                        RouterChatMessage(role="user", content=prompt),
                    ],
                    temperature=0.2,
                    max_tokens=60,
                    timeout_seconds=20,
                )
            )

            raw_name = res.content.strip().split("\n")[0].strip("\"'` ")
            clean_name = clean_filename_string(raw_name)
            if "." in clean_name:
                clean_name = clean_name.rsplit(".", 1)[0]

            return clean_name if len(clean_name) >= 3 else None
        except Exception as e:
            logger.warning("AI filename generation failed, falling back to local heuristic: %s", e)
            words = [w for w in re.findall(r'[A-Za-z0-9]+', content_snippet) if len(w) >= 3 and not w.isdigit()][:4]
            if words:
                return "_".join(words)
            return None

    def _resolve_name_collision(
        self,
        proposed_name: str,
        existing_filenames: Set[str],
        planned_names: Set[str],
        orig_fn_lower: str,
    ) -> str:
        """Appends sequential numbers until collision is resolved."""
        p = Path(proposed_name)
        stem = p.stem
        suffix = p.suffix

        counter = 1
        while counter < 1000:
            candidate = f"{stem}_{counter:02d}{suffix}"
            c_lower = candidate.lower()
            is_disk = (c_lower in existing_filenames) and (c_lower != orig_fn_lower)
            is_batch = c_lower in planned_names
            if not is_disk and not is_batch:
                return candidate
            counter += 1

        return f"{stem}_{counter}{suffix}"

    async def analyze_item_with_ocr(self, plan_id: str, item_id: str) -> ItemOCRAnalyzeResponse:
        """Runs PaddleOCR and AI naming on a single plan item on demand."""
        plan = self.db.get(ChangePlan, plan_id)
        if not plan:
            raise ValueError(f"Change Plan '{plan_id}' not found")

        item = self.db.get(ChangePlanItem, item_id)
        if not item or item.change_plan_id != plan.id:
            raise ValueError(f"Change Plan Item '{item_id}' not found in plan '{plan_id}'")

        folder = self._get_managed_folder(plan.managed_folder_id)
        root_path = Path(folder.root_path).resolve()

        rel_src = item.source_relative_path or ""
        fpath = PathValidator.resolve_and_verify_scope(folder, rel_src)
        orig_name = fpath.name
        curr_dest = item.destination_relative_path or rel_src
        curr_proposed = curr_dest.split("/")[-1] if "/" in curr_dest else curr_dest

        if not fpath.exists() or not fpath.is_file():
            return ItemOCRAnalyzeResponse(
                item_id=item_id,
                plan_id=plan_id,
                source_relative_path=rel_src,
                original_name=orig_name,
                proposed_name=curr_proposed,
                destination_relative_path=curr_dest,
                status="conflict",
                conflict_reason="File no longer exists on disk",
                success=False,
                error_message="File does not exist",
            )

        cat = detect_file_category(fpath.name)
        ext = fpath.suffix.lstrip(".")
        is_image = cat == "image" or ext.lower() in ("png", "jpg", "jpeg", "webp", "bmp", "tiff")
        is_doc = cat == "document" or ext.lower() in ("pdf", "docx")

        extracted_text = ""
        if is_image or ext.lower() == "pdf":
            try:
                from backend.app.schemas.ocr import OCRExtractRequest
                from backend.app.services.ocr_service import PaddleOCRService
                ocr_svc = PaddleOCRService(self.db)
                ocr_res = ocr_svc.extract_text(
                    OCRExtractRequest(
                        folder_id=folder.id,
                        relative_path=rel_src,
                        max_pages=2,
                    )
                )
                if ocr_res.success and ocr_res.full_text:
                    extracted_text = ocr_res.full_text.strip()
            except Exception as e:
                logger.warning("PaddleOCR error for %s: %s", fpath.name, e)

        if not extracted_text:
            return ItemOCRAnalyzeResponse(
                item_id=item_id,
                plan_id=plan_id,
                source_relative_path=rel_src,
                original_name=orig_name,
                proposed_name=curr_proposed,
                destination_relative_path=curr_dest,
                extracted_text="",
                status=item.status,
                conflict_reason=item.conflict_reason,
                success=False,
                error_message="No readable text detected by OCR in this file",
            )

        ai_suggested = await self._generate_ai_name_from_content(
            filename=orig_name,
            category=cat,
            content_snippet=extracted_text[:800],
        )

        stem_res = ai_suggested or fpath.stem
        raw_proposed = f"{stem_res}.{ext}" if ext else stem_res

        # Collision detection in parent dir
        parent_rel = rel_src.rsplit("/", 1)[0] if "/" in rel_src else ""
        parent_dir = (root_path / parent_rel).resolve() if parent_rel else root_path

        existing_filenames: Set[str] = set()
        if parent_dir.exists():
            try:
                for entry in os.scandir(parent_dir):
                    existing_filenames.add(entry.name.lower())
            except OSError:
                pass

        sibling_names: Set[str] = set()
        for sib in plan.items:
            if sib.id != item.id and sib.destination_relative_path:
                sib_fn = sib.destination_relative_path.split("/")[-1]
                sibling_names.add(sib_fn.lower())

        resolved_name = self._resolve_name_collision(
            raw_proposed,
            existing_filenames,
            sibling_names,
            orig_name.lower(),
        )

        new_dest_rel = f"{parent_rel}/{resolved_name}" if parent_rel else resolved_name
        item.destination_relative_path = new_dest_rel
        item.status = "pending"
        item.conflict_reason = None
        self.db.commit()

        return ItemOCRAnalyzeResponse(
            item_id=item_id,
            plan_id=plan_id,
            source_relative_path=rel_src,
            original_name=orig_name,
            proposed_name=resolved_name,
            destination_relative_path=new_dest_rel,
            extracted_text=extracted_text[:200],
            status="ready",
            conflict_reason=None,
            success=True,
        )

    async def run_batch_ocr_background(self, plan_id: str) -> None:
        """Processes OCR and AI renaming on all eligible items in the plan sequentially in background."""
        BATCH_OCR_JOBS[plan_id] = {
            "plan_id": plan_id,
            "is_running": True,
            "total_items": 0,
            "processed_items": 0,
            "success_count": 0,
            "error_count": 0,
            "current_item_name": None,
            "message": "Memulai analisis OCR di latar belakang...",
        }
        try:
            plan = self.db.get(ChangePlan, plan_id)
            if not plan:
                BATCH_OCR_JOBS[plan_id]["is_running"] = False
                BATCH_OCR_JOBS[plan_id]["message"] = "Plan tidak ditemukan"
                return

            candidates = [
                it for it in plan.items
                if it.operation == "rename" and it.source_relative_path
                and Path(it.source_relative_path).suffix.lower() in (
                    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".pdf"
                )
            ]
            BATCH_OCR_JOBS[plan_id]["total_items"] = len(candidates)

            for it in candidates:
                orig_fn = it.source_relative_path.split("/")[-1]
                BATCH_OCR_JOBS[plan_id]["current_item_name"] = orig_fn
                try:
                    res = await self.analyze_item_with_ocr(plan_id, it.id)
                    if res.success:
                        BATCH_OCR_JOBS[plan_id]["success_count"] += 1
                    else:
                        BATCH_OCR_JOBS[plan_id]["error_count"] += 1
                except Exception as ex:
                    logger.warning("Batch OCR item failed: %s", ex)
                    BATCH_OCR_JOBS[plan_id]["error_count"] += 1

                BATCH_OCR_JOBS[plan_id]["processed_items"] += 1

            BATCH_OCR_JOBS[plan_id]["is_running"] = False
            BATCH_OCR_JOBS[plan_id]["current_item_name"] = None
            BATCH_OCR_JOBS[plan_id]["message"] = "Analisis OCR latar belakang selesai."
        except Exception as e:
            logger.error("Background batch OCR failed for plan %s: %s", plan_id, e)
            if plan_id in BATCH_OCR_JOBS:
                BATCH_OCR_JOBS[plan_id]["is_running"] = False
                BATCH_OCR_JOBS[plan_id]["message"] = f"Error: {str(e)}"

    def get_batch_ocr_status(self, plan_id: str) -> BatchOCRJobStatus:
        info = BATCH_OCR_JOBS.get(plan_id)
        if not info:
            return BatchOCRJobStatus(
                plan_id=plan_id,
                is_running=False,
                total_items=0,
                processed_items=0,
                success_count=0,
                error_count=0,
                message="Belum ada pekerjaan OCR untuk plan ini.",
            )
        return BatchOCRJobStatus(**info)

    async def quick_suggest_ocr_rename(self, folder_id: str, relative_path: str) -> QuickOCRRenameResponse:
        """Extracts OCR text from a file and suggests a descriptive new name using AI."""
        folder = self._get_managed_folder(folder_id)
        fpath = PathValidator.resolve_and_verify_scope(folder, relative_path)

        orig_name = fpath.name
        ext = fpath.suffix.lstrip(".")
        cat = detect_file_category(orig_name)

        if not fpath.exists() or not fpath.is_file():
            return QuickOCRRenameResponse(
                original_name=orig_name,
                proposed_name=orig_name,
                relative_path=relative_path,
                category=cat,
                success=False,
                error_message="Berkas tidak ditemukan pada disk.",
            )

        extracted_text = ""
        is_image = cat == "image" or ext.lower() in ("png", "jpg", "jpeg", "webp", "bmp", "tiff")
        is_pdf = ext.lower() == "pdf"

        if is_image or is_pdf:
            try:
                from backend.app.schemas.ocr import OCRExtractRequest
                from backend.app.services.ocr_service import PaddleOCRService
                ocr_svc = PaddleOCRService(self.db)
                ocr_res = ocr_svc.extract_text(
                    OCRExtractRequest(
                        folder_id=folder.id,
                        relative_path=relative_path,
                        max_pages=2,
                    )
                )
                if ocr_res.success and ocr_res.full_text:
                    extracted_text = ocr_res.full_text.strip()
            except Exception as e:
                logger.warning("OCR extraction error for %s: %s", orig_name, e)

        # Generate AI name from extracted text or fallback
        ai_stem = None
        if extracted_text:
            ai_stem = await self._generate_ai_name_from_content(
                filename=orig_name,
                category=cat,
                content_snippet=extracted_text[:800],
            )

        if not ai_stem:
            ai_stem = clean_filename_string(fpath.stem)
            if not ai_stem:
                ai_stem = "file"

        raw_proposed = f"{ai_stem}.{ext}" if ext else ai_stem

        # Resolve collision in parent directory
        parent_dir = fpath.parent
        existing_filenames: Set[str] = set()
        if parent_dir.exists():
            try:
                for entry in os.scandir(parent_dir):
                    existing_filenames.add(entry.name.lower())
            except OSError:
                pass

        resolved_name = self._resolve_name_collision(
            raw_proposed,
            existing_filenames,
            set(),
            orig_name.lower(),
        )

        return QuickOCRRenameResponse(
            original_name=orig_name,
            proposed_name=resolved_name,
            relative_path=relative_path,
            extracted_text=extracted_text[:300] if extracted_text else None,
            category=cat,
            success=True,
        )

