import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import generate_uuid, utc_now_iso
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.specialists import (
    DiskAnalystRequest,
    DiskAnalystResult,
    DuplicateAnalystRequest,
    DuplicateAnalystResult,
    DuplicateClusterItem,
    FolderArchitectMoveItem,
    FolderArchitectRequest,
    FolderArchitectResult,
    RenameMappingItem,
    RenameSpecialistRequest,
    RenameSpecialistResult,
    ReviewAgentRequest,
    ReviewAgentResult,
    ReviewRiskItem,
    SpecialistRunRequest,
    SpecialistType,
    WasteSourceItem,
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
from backend.app.services.router_gateway import RouterGatewayService
from backend.app.services.settings_service import SettingsService
from backend.app.services.storage import StorageAnalyzerService
from backend.app.services.transaction import (
    TransactionException,
    TransactionManagerService,
)


class SpecialistException(Exception):
    """Raised for errors in AI specialist execution."""
    pass


INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str) -> str:
    """Replaces invalid Windows filename characters with underscores."""
    sanitized = INVALID_WIN_CHARS.sub("_", name).strip()
    return sanitized or "unnamed_file"


class SpecialistService:
    """Coordinates the 5 specialized AI analysis workflows via 9Router gateway."""

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)
        self.storage_service = StorageAnalyzerService(db)
        self.transaction_service = TransactionManagerService(db)
        self.router_service = RouterGatewayService(db)
        self.audit_repo = AuditLogRepository(db)

    def _get_active_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise SpecialistException(f"Managed Folder '{folder_id}' tidak ditemukan.")
        if not folder.is_enabled:
            raise SpecialistException(f"Managed Folder '{folder.name}' sedang dinonaktifkan.")
        return folder

    # =========================================================================
    # 1. Disk Analyst Specialist
    # =========================================================================

    async def run_disk_analyst(self, request: DiskAnalystRequest) -> DiskAnalystResult:
        """Evaluates storage consumption across categories, detects anomalous growth,
        identifies large files, and produces structured recommendations."""
        start_time = time.perf_counter()
        folder = self._get_active_folder(request.managed_folder_id)

        # 1. Gather Storage Metrics
        threshold_bytes = request.large_file_threshold_mb * 1024 * 1024
        analysis = self.storage_service.analyze_folder(
            folder.id, large_file_threshold_bytes=threshold_bytes
        )

        total_bytes = analysis.total_storage_bytes
        total_files = analysis.total_files_count
        categories = analysis.category_distribution
        duplicates = analysis.duplicate_groups
        large_files = analysis.large_files

        largest_cat = "other"
        max_cat_bytes = 0
        for cat in categories:
            if cat.total_size_bytes > max_cat_bytes:
                max_cat_bytes = cat.total_size_bytes
                largest_cat = cat.category

        # 2. Identify Waste Sources
        waste_sources: List[WasteSourceItem] = []
        dup_savings = sum(d.potential_savings_bytes for d in duplicates)
        if dup_savings > 0:
            waste_sources.append(
                WasteSourceItem(
                    category="duplicates",
                    description=f"{len(duplicates)} kelompok berkas duplikat terdeteksi.",
                    size_bytes=dup_savings,
                    count=sum(len(d.files) for d in duplicates),
                    recommendation="Jalankan Duplicate Analyst untuk memangkas salinan redundan.",
                )
            )

        threshold_bytes = request.large_file_threshold_mb * 1024 * 1024
        huge_files = [lf for lf in large_files if lf.size_bytes >= threshold_bytes]
        if huge_files:
            huge_total = sum(hf.size_bytes for hf in huge_files)
            waste_sources.append(
                WasteSourceItem(
                    category="large_files",
                    description=f"{len(huge_files)} berkas berukuran di atas {request.large_file_threshold_mb}MB.",
                    size_bytes=huge_total,
                    count=len(huge_files),
                    recommendation="Tinjau berkas berukuran masif untuk pengarsipan atau kompresi eksternal.",
                )
            )

        # 3. Calculate Health Score (100 base, deductions for waste/duplication)
        health_score = 100
        if total_bytes > 0:
            dup_ratio = dup_savings / total_bytes
            health_score -= min(35, int(dup_ratio * 70))
        if len(huge_files) > 5:
            health_score -= 10
        if total_files > 500:
            health_score -= 5
        health_score = max(10, min(100, health_score))

        # 4. Generate Recommendations
        recommendations = [
            f"Kategori penyimpanan terbesar adalah '{largest_cat}' ({max_cat_bytes // (1024*1024)} MB).",
        ]
        if dup_savings > 0:
            recommendations.append(
                f"Terdapat potensi penghematan {dup_savings // (1024*1024)} MB dari pembersihan duplikat."
            )
        if huge_files:
            recommendations.append(
                f"{len(huge_files)} berkas besar terdeteksi. Pertimbangkan memindahkan berkas arsip ke media cadangan."
            )
        if health_score < 70:
            recommendations.append("Kerapian penyimpanan tergolong sedang. Disarankan melakukan penataan folder berkala.")
        else:
            recommendations.append("Kondisi penyimpanan terkelola secara optimal dan efisien.")

        summary = (
            f"Disk Analyst telah mengevaluasi folder '{folder.name}': {total_files} berkas "
            f"({total_bytes // (1024*1024)} MB) dianalisis. Skor kesehatan penyimpanan: {health_score}/100."
        )

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        self._record_audit(
            action="specialist_disk_analyst",
            folder_id=folder.id,
            details={"health_score": health_score, "savings_bytes": dup_savings},
        )

        return DiskAnalystResult(
            managed_folder_id=folder.id,
            total_storage_bytes=total_bytes,
            total_files=total_files,
            largest_category=largest_cat,
            health_score=health_score,
            potential_savings_bytes=dup_savings,
            waste_sources=waste_sources,
            actionable_recommendations=recommendations,
            summary=summary,
            execution_time_ms=latency,
        )

    # =========================================================================
    # 2. Folder Architect Specialist
    # =========================================================================

    async def run_folder_architect(self, request: FolderArchitectRequest) -> FolderArchitectResult:
        """Analyzes disorganized files and proposes an intelligent folder structure and change plan."""
        start_time = time.perf_counter()
        folder = self._get_active_folder(request.managed_folder_id)
        root = Path(folder.root_path).resolve()

        # 1. Discover loose or disorganized files
        target_dir = root
        if request.target_relative_path:
            target_dir = PathValidator.resolve_and_verify_scope(folder, request.target_relative_path)

        loose_files: List[Path] = []
        with os.scandir(target_dir) as it:
            for entry in it:
                p = Path(entry.path)
                if not entry.is_dir(follow_symlinks=False) and not is_hidden_item(p) and not is_reparse_point_or_symlink(p):
                    loose_files.append(p)

        # 2. Plan Proposed Organization
        strategy = request.organization_style or "category"
        proposed_structure: Set[str] = set()
        proposed_moves: List[FolderArchitectMoveItem] = []

        for fpath in loose_files:
            rel_src = fpath.relative_to(root).as_posix()
            ext = fpath.suffix.lower().lstrip(".")
            cat = detect_file_category(ext).capitalize()

            if strategy == "date":
                st = fpath.stat(follow_symlinks=False)
                year_month = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m")
                target_folder = f"{cat}/{year_month}"
            else:
                target_folder = cat

            proposed_structure.add(target_folder)
            dest_rel = f"{target_folder}/{fpath.name}"
            # Ensure not identical
            if rel_src != dest_rel:
                proposed_moves.append(
                    FolderArchitectMoveItem(
                        source_relative_path=rel_src,
                        destination_relative_path=dest_rel,
                        reason=f"Mengelompokkan berkas {cat} ke subfolder '{target_folder}'.",
                    )
                )

        # 3. Create Draft Plan via Transaction Manager (if requested)
        plan_id = None
        plan_status = None
        if request.create_draft_plan and proposed_moves:
            plan_items: List[ChangePlanItemCreate] = []

            # Add directory creations first
            for idx, folder_path in enumerate(sorted(proposed_structure), start=1):
                plan_items.append(
                    ChangePlanItemCreate(
                        operation=OperationType.CREATE_DIRECTORY,
                        destination_relative_path=folder_path,
                        sequence_no=idx,
                    )
                )

            # Add move operations
            base_seq = len(plan_items)
            for idx, move in enumerate(proposed_moves, start=1):
                # Backend path validation
                PathValidator.resolve_and_verify_scope(folder, move.source_relative_path)
                PathValidator.resolve_and_verify_scope(folder, move.destination_relative_path)

                plan_items.append(
                    ChangePlanItemCreate(
                        operation=OperationType.MOVE,
                        source_relative_path=move.source_relative_path,
                        destination_relative_path=move.destination_relative_path,
                        sequence_no=base_seq + idx,
                    )
                )

            create_payload = ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Arsitektur Folder: Penataan Berkas ({strategy.capitalize()})",
                plan_type=PlanType.ORGANIZE,
                items=plan_items,
            )
            created_plan = self.transaction_service.create_plan(create_payload, created_by="ai")
            plan_id = created_plan.id
            plan_status = created_plan.status

        summary = (
            f"Folder Architect merancang {len(proposed_structure)} struktur folder baru "
            f"dengan {len(proposed_moves)} berkas yang diusulkan untuk dipindahkan. "
            f"Rencana telah dialihkan ke Review Changes untuk disetujui."
        )

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        self._record_audit(
            action="specialist_folder_architect",
            folder_id=folder.id,
            details={"strategy": strategy, "moves_count": len(proposed_moves), "plan_id": plan_id},
        )

        return FolderArchitectResult(
            managed_folder_id=folder.id,
            strategy_used=strategy,
            proposed_structure=sorted(list(proposed_structure)),
            proposed_moves=proposed_moves,
            moves_count=len(proposed_moves),
            plan_id=plan_id,
            plan_status=plan_status,
            requires_approval=True,
            summary=summary,
            execution_time_ms=latency,
        )

    # =========================================================================
    # 3. Rename Specialist
    # =========================================================================

    async def run_rename_specialist(self, request: RenameSpecialistRequest) -> RenameSpecialistResult:
        """Analyzes messy or inconsistent filenames and proposes semantic, standardized names."""
        start_time = time.perf_counter()
        folder = self._get_active_folder(request.managed_folder_id)
        root = Path(folder.root_path).resolve()

        target_dir = root
        if request.target_relative_path:
            target_dir = PathValidator.resolve_and_verify_scope(folder, request.target_relative_path)

        candidates: List[Path] = []
        with os.scandir(target_dir) as it:
            for entry in it:
                p = Path(entry.path)
                if not entry.is_dir(follow_symlinks=False) and not is_hidden_item(p) and not is_reparse_point_or_symlink(p):
                    candidates.append(p)

        convention = request.naming_convention or "standard"
        renames: List[RenameMappingItem] = []

        for fpath in candidates:
            orig_name = fpath.name
            stem = fpath.stem
            ext = fpath.suffix

            # Determine improved name based on convention
            if convention == "date_prefix":
                st = fpath.stat(follow_symlinks=False)
                date_prefix = datetime.fromtimestamp(st.st_mtime).strftime("%Y%m%d")
                if not stem.startswith(date_prefix):
                    clean_stem = re.sub(r"[\s\-_]+", "_", stem).strip("_")
                    proposed_name = f"{date_prefix}_{clean_stem}{ext}"
                else:
                    proposed_name = orig_name
            elif convention == "kebab_case":
                clean_stem = re.sub(r"[\s_]+", "-", stem).lower().strip("-")
                proposed_name = f"{clean_stem}{ext}"
            else:  # standard clean
                clean_stem = re.sub(r"\s+", "_", stem).strip()
                clean_stem = re.sub(r"_+", "_", clean_stem)
                proposed_name = f"{clean_stem}{ext}"

            proposed_name = sanitize_filename(proposed_name)

            if proposed_name != orig_name:
                rel_src = fpath.relative_to(root).as_posix()
                renames.append(
                    RenameMappingItem(
                        source_relative_path=rel_src,
                        original_name=orig_name,
                        proposed_name=proposed_name,
                        reason=f"Menstandarisasi nama berkas sesuai aturan '{convention}'.",
                    )
                )

        # Create Draft Plan via Transaction Manager
        plan_id = None
        plan_status = None
        if request.create_draft_plan and renames:
            plan_items = []
            for idx, r in enumerate(renames, start=1):
                parent = Path(r.source_relative_path).parent.as_posix()
                dest_rel = r.proposed_name if parent in (".", "") else f"{parent}/{r.proposed_name}"

                # Backend validation
                PathValidator.resolve_and_verify_scope(folder, r.source_relative_path)
                PathValidator.resolve_and_verify_scope(folder, dest_rel)

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
                title=f"Smart Rename: Standarisasi Nama Berkas ({convention})",
                plan_type=PlanType.RENAME,
                items=plan_items,
            )
            created_plan = self.transaction_service.create_plan(create_payload, created_by="ai")
            plan_id = created_plan.id
            plan_status = created_plan.status

        summary = (
            f"Rename Specialist menemukan {len(renames)} berkas yang membutuhkan standarisasi nama. "
            f"Rencana rename draft telah dibuat dan dialihkan ke Review Changes."
        )

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        self._record_audit(
            action="specialist_rename",
            folder_id=folder.id,
            details={"convention": convention, "renames_count": len(renames), "plan_id": plan_id},
        )

        return RenameSpecialistResult(
            managed_folder_id=folder.id,
            strategy_used=convention,
            renames=renames,
            renames_count=len(renames),
            plan_id=plan_id,
            plan_status=plan_status,
            requires_approval=True,
            summary=summary,
            execution_time_ms=latency,
        )

    # =========================================================================
    # 4. Duplicate Analyst Specialist
    # =========================================================================

    async def run_duplicate_analyst(self, request: DuplicateAnalystRequest) -> DuplicateAnalystResult:
        """Clusters duplicate files, evaluates optimal retention, and proposes cleanup plans."""
        start_time = time.perf_counter()
        folder = self._get_active_folder(request.managed_folder_id)

        analysis = self.storage_service.get_latest_analysis(folder.id)
        if not analysis:
            analysis = self.storage_service.analyze_folder(folder.id)

        clusters: List[DuplicateClusterItem] = []
        strategy = request.retention_strategy or "keep_oldest"

        for group in analysis.duplicate_groups:
            if group.size_bytes < request.min_size_bytes or len(group.files) < 2:
                continue

            # Evaluate retention file
            if strategy == "keep_newest":
                sorted_files = sorted(group.files, key=lambda f: f.modified_at or "", reverse=True)
            elif strategy == "keep_shortest_path":
                sorted_files = sorted(group.files, key=lambda f: len(f.relative_path))
            else:  # keep_oldest
                sorted_files = sorted(group.files, key=lambda f: f.modified_at or "")

            keep_file = sorted_files[0].relative_path
            cleanup_candidates = [f.relative_path for f in sorted_files[1:]]

            clusters.append(
                DuplicateClusterItem(
                    hash=group.hash,
                    size_bytes=group.size_bytes,
                    wasted_bytes=group.potential_savings_bytes,
                    keep_file=keep_file,
                    cleanup_candidates=cleanup_candidates,
                    retention_reason=f"Menyimpan berkas primer berdasarkan strategi '{strategy}'.",
                )
            )

        total_savings = sum(c.wasted_bytes for c in clusters)
        total_dup_files = sum(len(c.cleanup_candidates) + 1 for c in clusters)

        # Create Cleanup Plan if requested (STRICTLY routes to recycle bin as draft)
        plan_id = None
        plan_status = None
        if request.create_cleanup_plan and clusters:
            plan_items = []
            seq = 1
            for cluster in clusters:
                for candidate in cluster.cleanup_candidates:
                    PathValidator.resolve_and_verify_scope(folder, candidate)
                    plan_items.append(
                        ChangePlanItemCreate(
                            operation=OperationType.DELETE_TO_RECYCLE_BIN,
                            source_relative_path=candidate,
                            sequence_no=seq,
                        )
                    )
                    seq += 1

            create_payload = ChangePlanCreate(
                managed_folder_id=folder.id,
                title=f"Pembersihan Berkas Duplikat ({len(plan_items)} berkas ke Recycle Bin)",
                plan_type=PlanType.MANUAL,
                items=plan_items,
            )
            created_plan = self.transaction_service.create_plan(create_payload, created_by="ai")
            plan_id = created_plan.id
            plan_status = created_plan.status

        summary = (
            f"Duplicate Analyst menemukan {len(clusters)} kelompok duplikat dengan "
            f"potensi penghematan ruang {total_savings // (1024*1024)} MB. "
            f"Strategi retensi '{strategy}' diterapkan."
        )

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        self._record_audit(
            action="specialist_duplicate_analyst",
            folder_id=folder.id,
            details={"clusters_count": len(clusters), "savings_bytes": total_savings, "plan_id": plan_id},
        )

        return DuplicateAnalystResult(
            managed_folder_id=folder.id,
            total_clusters=len(clusters),
            total_duplicate_files=total_dup_files,
            potential_savings_bytes=total_savings,
            clusters=clusters,
            plan_id=plan_id,
            plan_status=plan_status,
            requires_approval=True,
            summary=summary,
            execution_time_ms=latency,
        )

    # =========================================================================
    # 5. Review Agent Specialist
    # =========================================================================

    async def run_review_agent(self, request: ReviewAgentRequest) -> ReviewAgentResult:
        """Inspects proposed change plans, detects collision/loss risks, and produces safety verdicts."""
        start_time = time.perf_counter()
        try:
            plan = self.transaction_service.get_plan(request.plan_id)
        except TransactionException as e:
            raise SpecialistException(f"Change Plan tidak ditemukan: {str(e)}")
        folder = self._get_active_folder(plan.managed_folder_id)
        root = Path(folder.root_path).resolve()

        risks: List[ReviewRiskItem] = []
        destructive_count = 0

        # Scan each item in the plan
        for item in plan.items:
            op = item.operation

            # 1. Check for Destructive Operations
            if op in ("delete", "delete_to_recycle_bin"):
                destructive_count += 1
                risks.append(
                    ReviewRiskItem(
                        severity="MEDIUM",
                        category="DATA_LOSS",
                        item_path=item.source_relative_path or "",
                        details="Operasi penghapusan ke Recycle Bin terdeteksi. Pastikan berkas tidak diperlukan.",
                    )
                )

            # 2. Check Source Path Still Exists
            if item.source_relative_path and op != "create_directory":
                try:
                    src_full = PathValidator.resolve_and_verify_scope(folder, item.source_relative_path)
                    if not src_full.exists():
                        risks.append(
                            ReviewRiskItem(
                                severity="HIGH",
                                category="STALE_SOURCE",
                                item_path=item.source_relative_path,
                                details="Berkas sumber sudah tidak ditemukan di disk. Rencana mungkin telah basi.",
                            )
                        )
                except Exception as e:
                    risks.append(
                        ReviewRiskItem(
                            severity="HIGH",
                            category="PATH_ESCAPE",
                            item_path=item.source_relative_path,
                            details=f"Path sumber melanggar batas direktori: {str(e)}",
                        )
                    )

            # 3. Check Destination Collision
            if item.destination_relative_path and op in ("move", "rename", "copy"):
                try:
                    dest_full = PathValidator.resolve_and_verify_scope(folder, item.destination_relative_path)
                    if dest_full.exists():
                        risks.append(
                            ReviewRiskItem(
                                severity="HIGH",
                                category="COLLISION",
                                item_path=item.destination_relative_path,
                                details="Berkas tujuan sudah ada. Memindahkan ke sini dapat menimpa data.",
                            )
                        )
                except Exception as e:
                    risks.append(
                        ReviewRiskItem(
                            severity="HIGH",
                            category="PATH_ESCAPE",
                            item_path=item.destination_relative_path,
                            details=f"Path tujuan melanggar batas direktori: {str(e)}",
                        )
                    )

        # Determine Risk Level & Safety Verdict
        high_risks = [r for r in risks if r.severity == "HIGH"]
        if high_risks:
            risk_level = "HIGH"
            verdict = "BLOCKED_HIGH_RISK"
            can_execute = False
            summary = (
                f"Peringatan Keamanan: Terdeteksi {len(high_risks)} risiko kritis "
                f"(collision atau stale path). Eksekusi rencana disarankan ditunda hingga konflik diselesaikan."
            )
        elif destructive_count > 0 or len(risks) > 0:
            risk_level = "MEDIUM"
            verdict = "PROCEED_WITH_CAUTION"
            can_execute = True
            summary = (
                f"Rencana perubahan aman, namun memiliki {destructive_count} operasi destruktif "
                "ke Recycle Bin. Harap periksa daftar berkas sebelum menyetujui."
            )
        else:
            risk_level = "LOW"
            verdict = "APPROVED_RECOMMENDED"
            can_execute = True
            summary = "Semua operasi dalam Change Plan telah divalidasi aman, tanpa risiko collision atau kebocoran path."

        latency = round((time.perf_counter() - start_time) * 1000, 2)
        self._record_audit(
            action="specialist_review_agent",
            folder_id=folder.id,
            details={"plan_id": plan.id, "risk_level": risk_level, "verdict": verdict},
        )

        return ReviewAgentResult(
            plan_id=plan.id,
            plan_title=plan.title,
            plan_type=plan.plan_type,
            plan_status=plan.status,
            risk_level=risk_level,
            total_operations=len(plan.items),
            destructive_operations_count=destructive_count,
            risks=risks,
            safety_verdict=verdict,
            review_summary=summary,
            can_safely_execute=can_execute,
            execution_time_ms=latency,
        )

    # =========================================================================
    # General Dispatcher
    # =========================================================================

    async def run_specialist(self, request: SpecialistRunRequest) -> Dict[str, Any]:
        """Dispatches to the requested specialist runner."""
        if request.specialist == SpecialistType.DISK_ANALYST:
            res = await self.run_disk_analyst(
                DiskAnalystRequest(
                    managed_folder_id=request.managed_folder_id,
                    user_instructions=request.user_instructions,
                    model=request.model,
                )
            )
            return res.model_dump()
        elif request.specialist == SpecialistType.FOLDER_ARCHITECT:
            res = await self.run_folder_architect(
                FolderArchitectRequest(
                    managed_folder_id=request.managed_folder_id,
                    user_instructions=request.user_instructions,
                    target_relative_path=request.target_relative_path or "",
                    model=request.model,
                )
            )
            return res.model_dump()
        elif request.specialist == SpecialistType.RENAME_SPECIALIST:
            res = await self.run_rename_specialist(
                RenameSpecialistRequest(
                    managed_folder_id=request.managed_folder_id,
                    user_instructions=request.user_instructions,
                    target_relative_path=request.target_relative_path or "",
                    model=request.model,
                )
            )
            return res.model_dump()
        elif request.specialist == SpecialistType.DUPLICATE_ANALYST:
            res = await self.run_duplicate_analyst(
                DuplicateAnalystRequest(
                    managed_folder_id=request.managed_folder_id,
                    user_instructions=request.user_instructions,
                    model=request.model,
                )
            )
            return res.model_dump()
        elif request.specialist == SpecialistType.REVIEW_AGENT:
            plan_id = request.options.get("plan_id")
            if not plan_id:
                raise SpecialistException("Parameter 'plan_id' diperlukan untuk menjalankan Review Agent.")
            res = await self.run_review_agent(
                ReviewAgentRequest(
                    plan_id=plan_id,
                    user_instructions=request.user_instructions,
                    model=request.model,
                )
            )
            return res.model_dump()
        else:
            raise SpecialistException(f"Specialist '{request.specialist}' tidak dikenali.")

    def _record_audit(self, action: str, folder_id: str, details: Dict[str, Any]) -> None:
        try:
            self.audit_repo.record(
                actor_type="ai",
                action=action,
                entity_type="managed_folder",
                entity_id=folder_id,
                details=details,
            )
        except Exception as e:
            logger.warning(f"Failed to record specialist audit log: {e}")
