import hashlib
import json
import os
import stat
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import utc_now_iso
from backend.app.db.models.analysis_run import AnalysisRun
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.scan_job import ScanJob
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.db.repositories.file import FileRepository
from backend.app.schemas.storage import (
    CategoryDistribution,
    DuplicateFileItem,
    DuplicateGroup,
    EmptyFolderItem,
    FileTypeStats,
    LargeFileItem,
    LargestFolderItem,
    StorageAnalysisResult,
    StorageCleanupPlanRequest,
    StorageCleanupPlanResponse,
    StorageRecommendation,
    StorageUsageTrendPoint,
)
from backend.app.services.filesystem import (
    detect_file_category,
    format_timestamp,
    is_hidden_item,
    is_reparse_point_or_symlink,
)
from backend.app.services.managed_folder import ManagedFolderException, PathValidator


class StorageException(Exception):
    """Custom exception for storage analyzer errors."""
    pass


def compute_file_sha256(path: Path) -> str:
    """Computes SHA-256 hash of a file in 64KB chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def read_file_header(path: Path, length: int = 4096) -> bytes:
    """Reads the first N bytes of a file for fast duplicate pre-filtering."""
    with open(path, "rb") as f:
        return f.read(length)


class StorageAnalyzerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_repo = AuditLogRepository(db)

    def _get_active_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.get(ManagedFolder, folder_id)
        if not folder:
            raise StorageException(f"Managed Folder '{folder_id}' not found")
        if not folder.is_enabled:
            raise StorageException(f"Managed Folder '{folder.name}' is currently disabled")
        return folder

    def get_latest_analysis(self, folder_id: Optional[str] = None) -> Optional[StorageAnalysisResult]:
        """Retrieves the latest stored storage analysis from the database without re-scanning."""
        stmt = select(AnalysisRun).where(
            AnalysisRun.analysis_type == "storage",
            AnalysisRun.status == "completed",
        ).order_by(desc(AnalysisRun.created_at))

        if folder_id:
            stmt = stmt.where(AnalysisRun.managed_folder_id == folder_id)

        run = self.db.execute(stmt).scalars().first()
        if not run or not run.result_json:
            return None

        try:
            data = json.loads(run.result_json)
            return StorageAnalysisResult.model_validate(data)
        except Exception as e:
            logger.error(f"Failed to deserialize stored analysis run {run.id}: {e}")
            return None

    def analyze_folder(
        self,
        folder_id: str,
        large_file_threshold_bytes: int = 100 * 1024 * 1024,
        calculate_hashes: bool = True,
    ) -> StorageAnalysisResult:
        """Performs a deep read-only storage analysis on a single Managed Folder."""
        folder = self._get_active_folder(folder_id)
        root_path = Path(folder.root_path).resolve()

        if not root_path.exists() or not root_path.is_dir():
            raise StorageException(f"Root folder does not exist on disk: {root_path}")

        # Start ScanJob record
        scan_job = ScanJob(
            managed_folder_id=folder.id,
            scan_type="deep",
            status="running",
            started_at=utc_now_iso(),
        )
        self.db.add(scan_job)
        self.db.commit()
        self.db.refresh(scan_job)

        try:
            result = self._scan_and_analyze_path(
                folder=folder,
                root_path=root_path,
                large_threshold=large_file_threshold_bytes,
                calculate_hashes=calculate_hashes,
                scan_job_id=scan_job.id,
            )

            # Mark scan job completed
            scan_job.status = "completed"
            scan_job.files_seen = result.total_files_count
            scan_job.folders_seen = result.total_folders_count
            scan_job.bytes_seen = result.total_storage_bytes
            scan_job.finished_at = utc_now_iso()
            folder.last_scanned_at = scan_job.finished_at

            # Save AnalysisRun record
            analysis_run = AnalysisRun(
                managed_folder_id=folder.id,
                scan_job_id=scan_job.id,
                analysis_type="storage",
                engine="local",
                status="completed",
                result_json=result.model_dump_json(),
                started_at=scan_job.started_at,
                finished_at=scan_job.finished_at,
            )
            self.db.add(analysis_run)
            self.db.commit()

            self.audit_repo.record(
                action="storage_analysis_completed",
                entity_type="managed_folder",
                entity_id=folder.id,
                actor_type="system",
                details={
                    "total_bytes": result.total_storage_bytes,
                    "total_files": result.total_files_count,
                    "large_files": result.large_files_count,
                    "duplicate_groups": result.duplicate_groups_count,
                },
            )

            return result

        except Exception as e:
            scan_job.status = "failed"
            scan_job.error_message = str(e)
            scan_job.finished_at = utc_now_iso()
            self.db.commit()
            logger.error(f"Storage analysis failed for folder {folder.name}: {e}")
            raise StorageException(f"Storage analysis failed: {e}")

    def analyze_all_folders(
        self,
        large_file_threshold_bytes: int = 100 * 1024 * 1024,
        calculate_hashes: bool = True,
    ) -> StorageAnalysisResult:
        """Performs storage analysis across all enabled Managed Folders."""
        folders = list(
            self.db.execute(
                select(ManagedFolder).where(ManagedFolder.is_enabled == 1)
            ).scalars().all()
        )

        if not folders:
            return StorageAnalysisResult(
                managed_folder_id=None,
                managed_folder_name="All Managed Folders",
                analyzed_at=utc_now_iso(),
            )

        individual_results: List[StorageAnalysisResult] = []
        for f in folders:
            if Path(f.root_path).exists():
                res = self.analyze_folder(
                    f.id,
                    large_file_threshold_bytes=large_file_threshold_bytes,
                    calculate_hashes=calculate_hashes,
                )
                individual_results.append(res)

        return self._aggregate_analysis_results(individual_results)

    def _scan_and_analyze_path(
        self,
        folder: ManagedFolder,
        root_path: Path,
        large_threshold: int,
        calculate_hashes: bool,
        scan_job_id: str,
    ) -> StorageAnalysisResult:
        """Recursive read-only traversal collecting size distributions, large files,
        empty folders, and candidate duplicates."""
        files_data: List[Dict[str, Any]] = []
        dirs_data: List[Dict[str, Any]] = []
        empty_folders: List[EmptyFolderItem] = []
        top_level_folder_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"size": 0, "files": 0}
        )

        total_bytes = 0
        total_files = 0
        total_folders = 0

        # Stack-based traversal to safely avoid symlinks & reparse points
        stack: List[Path] = [root_path]

        while stack:
            current_dir = stack.pop()
            rel_dir = current_dir.relative_to(root_path).as_posix()
            if rel_dir == ".":
                rel_dir = ""

            sub_items_count = 0

            try:
                with os.scandir(current_dir) as entries:
                    for entry in entries:
                        entry_path = Path(entry.path)

                        # Never follow symlinks, junctions, or reparse points
                        if is_reparse_point_or_symlink(entry_path):
                            continue

                        sub_items_count += 1
                        entry_rel = entry_path.relative_to(root_path).as_posix()

                        if entry.is_dir(follow_symlinks=False):
                            total_folders += 1
                            stack.append(entry_path)
                            try:
                                mtime = format_timestamp(entry_path.stat(follow_symlinks=False).st_mtime)
                            except Exception:
                                mtime = None
                            dirs_data.append({
                                "path": entry_path,
                                "name": entry.name,
                                "relative_path": entry_rel,
                                "modified_at": mtime,
                            })
                        elif entry.is_file(follow_symlinks=False):
                            try:
                                st = entry_path.stat(follow_symlinks=False)
                                size = st.st_size
                                mtime = format_timestamp(st.st_mtime)
                                ext = entry_path.suffix.lower().lstrip(".") if entry_path.suffix else None
                                cat = detect_file_category(entry.name)

                                total_files += 1
                                total_bytes += size

                                files_data.append({
                                    "path": entry_path,
                                    "name": entry.name,
                                    "relative_path": entry_rel,
                                    "size_bytes": size,
                                    "category": cat,
                                    "extension": ext,
                                    "modified_at": mtime,
                                })

                                # Aggregate top-level folder sizes
                                parts = entry_rel.split("/")
                                top_level = parts[0] if len(parts) > 1 else "(root)"
                                top_level_folder_stats[top_level]["size"] += size
                                top_level_folder_stats[top_level]["files"] += 1

                            except (PermissionError, OSError) as e:
                                logger.warning(f"Failed to read file {entry_path}: {e}")

            except (PermissionError, OSError) as err:
                logger.warning(f"Failed to scan directory {current_dir}: {err}")

            # Check if this directory is empty (excluding root itself)
            if current_dir != root_path and sub_items_count == 0:
                try:
                    mtime = format_timestamp(current_dir.stat(follow_symlinks=False).st_mtime)
                except Exception:
                    mtime = None
                empty_folders.append(
                    EmptyFolderItem(
                        managed_folder_id=folder.id,
                        name=current_dir.name,
                        relative_path=rel_dir,
                        modified_at=mtime,
                    )
                )

        # ---------------------------------------------------------------------
        # 1. Large Files
        # ---------------------------------------------------------------------
        large_files: List[LargeFileItem] = []
        large_files_bytes = 0

        for f in files_data:
            if f["size_bytes"] >= large_threshold:
                large_files.append(
                    LargeFileItem(
                        managed_folder_id=folder.id,
                        name=f["name"],
                        relative_path=f["relative_path"],
                        size_bytes=f["size_bytes"],
                        category=f["category"],
                        extension=f["extension"],
                        modified_at=f["modified_at"],
                    )
                )
                large_files_bytes += f["size_bytes"]

        large_files.sort(key=lambda x: x.size_bytes, reverse=True)
        large_files_pct = (
            round((large_files_bytes / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
        )

        # ---------------------------------------------------------------------
        # 2. Duplicate Detection (Progressive Hashing)
        # ---------------------------------------------------------------------
        duplicate_groups: List[DuplicateGroup] = []
        duplicate_files_count = 0
        potential_savings_bytes = 0

        # Group by exact size first
        size_buckets: Dict[int, List[Dict[str, Any]]] = defaultdict(list)
        for f in files_data:
            if f["size_bytes"] > 0:  # Ignore 0-byte files for duplicate content savings
                size_buckets[f["size_bytes"]].append(f)

        for size, candidates in size_buckets.items():
            if len(candidates) < 2:
                continue

            # Candidate group shares exact size -> pre-filter with 4KB header
            header_buckets: Dict[bytes, List[Dict[str, Any]]] = defaultdict(list)
            for c in candidates:
                try:
                    hdr = read_file_header(c["path"])
                    header_buckets[hdr].append(c)
                except Exception:
                    pass

            for hdr, hdr_candidates in header_buckets.items():
                if len(hdr_candidates) < 2:
                    continue

                # Full SHA-256 hash comparison if requested
                hash_buckets: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
                for c in hdr_candidates:
                    try:
                        sha = compute_file_sha256(c["path"]) if calculate_hashes else f"size_{size}"
                        hash_buckets[sha].append(c)
                    except Exception:
                        pass

                for sha, dupes in hash_buckets.items():
                    if len(dupes) >= 2:
                        group_files = [
                            DuplicateFileItem(
                                managed_folder_id=folder.id,
                                name=d["name"],
                                relative_path=d["relative_path"],
                                size_bytes=d["size_bytes"],
                                modified_at=d["modified_at"],
                            )
                            for d in dupes
                        ]
                        savings = (len(dupes) - 1) * size
                        duplicate_groups.append(
                            DuplicateGroup(
                                hash=sha[:16],
                                size_bytes=size,
                                files_count=len(dupes),
                                potential_savings_bytes=savings,
                                files=group_files,
                            )
                        )
                        duplicate_files_count += len(dupes)
                        potential_savings_bytes += savings

        duplicate_groups.sort(key=lambda x: x.potential_savings_bytes, reverse=True)

        # ---------------------------------------------------------------------
        # 3. Category & File Type Distributions
        # ---------------------------------------------------------------------
        cat_counts: Dict[str, int] = defaultdict(int)
        cat_bytes: Dict[str, int] = defaultdict(int)
        ext_stats: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
            lambda: {"files": 0, "bytes": 0}
        )

        for f in files_data:
            cat = f["category"]
            ext = f["extension"] or "unknown"
            size = f["size_bytes"]

            cat_counts[cat] += 1
            cat_bytes[cat] += size

            ext_stats[(cat, ext)]["files"] += 1
            ext_stats[(cat, ext)]["bytes"] += size

        category_dist: List[CategoryDistribution] = []
        for cat, count in sorted(cat_counts.items(), key=lambda x: cat_bytes[x[0]], reverse=True):
            b = cat_bytes[cat]
            pct = round((b / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
            category_dist.append(
                CategoryDistribution(
                    category=cat,
                    files_count=count,
                    total_size_bytes=b,
                    percentage=pct,
                )
            )

        file_types: List[FileTypeStats] = []
        for (cat, ext), data in sorted(ext_stats.items(), key=lambda x: x[1]["bytes"], reverse=True):
            b = data["bytes"]
            pct = round((b / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
            file_types.append(
                FileTypeStats(
                    category=cat,
                    extension=ext,
                    files_count=data["files"],
                    total_size_bytes=b,
                    percentage=pct,
                )
            )

        # ---------------------------------------------------------------------
        # 4. Largest Folders
        # ---------------------------------------------------------------------
        largest_folders: List[LargestFolderItem] = []
        for name, data in sorted(
            top_level_folder_stats.items(), key=lambda x: x[1]["size"], reverse=True
        ):
            if name == "(root)":
                continue
            b = data["size"]
            pct = round((b / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
            largest_folders.append(
                LargestFolderItem(
                    managed_folder_id=folder.id,
                    name=name,
                    relative_path=name,
                    total_size_bytes=b,
                    files_count=data["files"],
                    percentage=pct,
                )
            )

        # ---------------------------------------------------------------------
        # 5. Smart Storage Recommendations
        # ---------------------------------------------------------------------
        recommendations: List[StorageRecommendation] = []

        if large_files:
            mb_size = round(large_files_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_large_files",
                    title="Review large files",
                    description=f"{len(large_files)} files ({mb_size} MB) with size > {round(large_threshold / (1024*1024))} MB.",
                    target_tab="large_files",
                    impact_bytes=large_files_bytes,
                    count=len(large_files),
                )
            )

        if duplicate_groups:
            mb_savings = round(potential_savings_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_duplicates",
                    title="Manage duplicate files",
                    description=f"{len(duplicate_groups)} duplicate groups ({mb_savings} MB potential savings).",
                    target_tab="duplicates",
                    impact_bytes=potential_savings_bytes,
                    count=len(duplicate_groups),
                )
            )

        if empty_folders:
            recommendations.append(
                StorageRecommendation(
                    id="rec_empty_folders",
                    title="Remove empty folders",
                    description=f"{len(empty_folders)} empty folders found.",
                    target_tab="empty_folders",
                    impact_bytes=0,
                    count=len(empty_folders),
                )
            )

        if category_dist:
            top_cat = category_dist[0]
            mb_top = round(top_cat.total_size_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_file_types",
                    title="Review file types",
                    description=f"{top_cat.category.capitalize()} ({top_cat.percentage}%) uses {mb_top} MB.",
                    target_tab="file_types",
                    impact_bytes=top_cat.total_size_bytes,
                    count=top_cat.files_count,
                )
            )

        # Trend point for today
        now_date = datetime.now(timezone.utc).strftime("%d %b")
        trend_points = [
            StorageUsageTrendPoint(date=now_date, total_size_bytes=total_bytes)
        ]

        # Persist discovered files and folders into SQLite FileRecord and reconcile stale records
        try:
            file_repo = FileRepository(self.db)
            all_entries = files_data + [
                {
                    "relative_path": d["relative_path"],
                    "name": d["name"],
                    "item_type": "directory",
                    "size_bytes": 0,
                    "modified_at": d["modified_at"],
                }
                for d in dirs_data
            ]
            file_repo.bulk_sync_scan_results(folder.id, scan_job_id, all_entries)
        except Exception as e:
            logger.warning("Failed to bulk sync scan results for folder %s into FileRecord: %s", folder.id, e)

        return StorageAnalysisResult(
            managed_folder_id=folder.id,
            managed_folder_name=folder.name,
            analyzed_at=utc_now_iso(),
            total_storage_bytes=total_bytes,
            total_files_count=total_files,
            total_folders_count=total_folders,
            large_files_count=len(large_files),
            large_files_bytes=large_files_bytes,
            large_files_percentage=large_files_pct,
            duplicate_groups_count=len(duplicate_groups),
            duplicate_files_count=duplicate_files_count,
            potential_savings_bytes=potential_savings_bytes,
            empty_folders_count=len(empty_folders),
            category_distribution=category_dist,
            file_types=file_types,
            largest_folders=largest_folders,
            recommendations=recommendations,
            large_files=large_files,
            duplicate_groups=duplicate_groups,
            empty_folders=empty_folders,
            trend_points=trend_points,
        )

    def _aggregate_analysis_results(
        self, results: List[StorageAnalysisResult]
    ) -> StorageAnalysisResult:
        """Aggregates multiple individual folder analysis results into a single consolidated summary."""
        total_storage = sum(r.total_storage_bytes for r in results)
        total_files = sum(r.total_files_count for r in results)
        total_folders = sum(r.total_folders_count for r in results)
        large_files_bytes = sum(r.large_files_bytes for r in results)
        large_files_count = sum(r.large_files_count for r in results)
        dup_groups_count = sum(r.duplicate_groups_count for r in results)
        dup_files_count = sum(r.duplicate_files_count for r in results)
        savings_bytes = sum(r.potential_savings_bytes for r in results)
        empty_count = sum(r.empty_folders_count for r in results)

        large_files_pct = (
            round((large_files_bytes / total_storage) * 100, 1) if total_storage > 0 else 0.0
        )

        all_large_files: List[LargeFileItem] = []
        all_duplicate_groups: List[DuplicateGroup] = []
        all_empty_folders: List[EmptyFolderItem] = []
        all_largest_folders: List[LargestFolderItem] = []

        cat_counts: Dict[str, int] = defaultdict(int)
        cat_bytes: Dict[str, int] = defaultdict(int)
        ext_stats: Dict[Tuple[str, str], Dict[str, int]] = defaultdict(
            lambda: {"files": 0, "bytes": 0}
        )

        for r in results:
            all_large_files.extend(r.large_files)
            all_duplicate_groups.extend(r.duplicate_groups)
            all_empty_folders.extend(r.empty_folders)
            all_largest_folders.extend(r.largest_folders)

            for cd in r.category_distribution:
                cat_counts[cd.category] += cd.files_count
                cat_bytes[cd.category] += cd.total_size_bytes

            for ft in r.file_types:
                ext_stats[(ft.category, ft.extension)]["files"] += ft.files_count
                ext_stats[(ft.category, ft.extension)]["bytes"] += ft.total_size_bytes

        all_large_files.sort(key=lambda x: x.size_bytes, reverse=True)
        all_duplicate_groups.sort(key=lambda x: x.potential_savings_bytes, reverse=True)
        all_largest_folders.sort(key=lambda x: x.total_size_bytes, reverse=True)

        category_dist: List[CategoryDistribution] = []
        for cat, count in sorted(cat_counts.items(), key=lambda x: cat_bytes[x[0]], reverse=True):
            b = cat_bytes[cat]
            pct = round((b / total_storage) * 100, 1) if total_storage > 0 else 0.0
            category_dist.append(
                CategoryDistribution(
                    category=cat,
                    files_count=count,
                    total_size_bytes=b,
                    percentage=pct,
                )
            )

        file_types: List[FileTypeStats] = []
        for (cat, ext), data in sorted(ext_stats.items(), key=lambda x: x[1]["bytes"], reverse=True):
            b = data["bytes"]
            pct = round((b / total_storage) * 100, 1) if total_storage > 0 else 0.0
            file_types.append(
                FileTypeStats(
                    category=cat,
                    extension=ext,
                    files_count=data["files"],
                    total_size_bytes=b,
                    percentage=pct,
                )
            )

        recommendations: List[StorageRecommendation] = []
        if all_large_files:
            mb_size = round(large_files_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_large_files",
                    title="Review large files",
                    description=f"{len(all_large_files)} files ({mb_size} MB) with size > 100 MB.",
                    target_tab="large_files",
                    impact_bytes=large_files_bytes,
                    count=len(all_large_files),
                )
            )
        if all_duplicate_groups:
            mb_savings = round(savings_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_duplicates",
                    title="Manage duplicate files",
                    description=f"{len(all_duplicate_groups)} duplicate groups ({mb_savings} MB potential savings).",
                    target_tab="duplicates",
                    impact_bytes=savings_bytes,
                    count=len(all_duplicate_groups),
                )
            )
        if all_empty_folders:
            recommendations.append(
                StorageRecommendation(
                    id="rec_empty_folders",
                    title="Remove empty folders",
                    description=f"{len(all_empty_folders)} empty folders found.",
                    target_tab="empty_folders",
                    impact_bytes=0,
                    count=len(all_empty_folders),
                )
            )
        if category_dist:
            top_cat = category_dist[0]
            mb_top = round(top_cat.total_size_bytes / (1024 * 1024), 1)
            recommendations.append(
                StorageRecommendation(
                    id="rec_file_types",
                    title="Review file types",
                    description=f"{top_cat.category.capitalize()} ({top_cat.percentage}%) uses {mb_top} MB.",
                    target_tab="file_types",
                    impact_bytes=top_cat.total_size_bytes,
                    count=top_cat.files_count,
                )
            )

        now_date = datetime.now(timezone.utc).strftime("%d %b")
        trend_points = [
            StorageUsageTrendPoint(date=now_date, total_size_bytes=total_storage)
        ]

        return StorageAnalysisResult(
            managed_folder_id=None,
            managed_folder_name="All Managed Folders",
            analyzed_at=utc_now_iso(),
            total_storage_bytes=total_storage,
            total_files_count=total_files,
            total_folders_count=total_folders,
            large_files_count=large_files_count,
            large_files_bytes=large_files_bytes,
            large_files_percentage=large_files_pct,
            duplicate_groups_count=dup_groups_count,
            duplicate_files_count=dup_files_count,
            potential_savings_bytes=savings_bytes,
            empty_folders_count=empty_count,
            category_distribution=category_dist,
            file_types=file_types,
            largest_folders=all_largest_folders[:10],
            recommendations=recommendations,
            large_files=all_large_files[:100],
            duplicate_groups=all_duplicate_groups[:100],
            empty_folders=all_empty_folders[:100],
            trend_points=trend_points,
        )

    def create_cleanup_plan(
        self,
        payload: StorageCleanupPlanRequest,
        transaction_service: Any,
    ) -> StorageCleanupPlanResponse:
        """Creates reviewable Change Plans (delete_to_recycle_bin) for Storage Analyzer cleanup targets."""
        from backend.app.schemas.transaction import (
            ChangePlanCreate,
            ChangePlanItemCreate,
            OperationType,
            PlanType,
        )

        grouped: Dict[str, List[Any]] = defaultdict(list)
        seen_keys: Set[Tuple[str, str]] = set()
        for item in payload.items:
            clean_rel = item.relative_path.strip().replace("\\", "/").lstrip("/")
            key = (item.managed_folder_id, clean_rel)
            if not clean_rel or key in seen_keys:
                continue
            seen_keys.add(key)
            grouped[item.managed_folder_id].append(item)

        if not grouped:
            raise StorageException("No valid cleanup targets provided.")

        label_map = {
            "duplicates": "Duplicate Files Cleanup",
            "large_files": "Large Files Cleanup",
            "empty_folders": "Empty Folders Cleanup",
        }
        base_title = payload.title or label_map.get(payload.cleanup_type, "Storage Cleanup")

        created_plan_ids: List[str] = []
        total_queued = 0

        for folder_id, folder_items in grouped.items():
            folder = self._get_active_folder(folder_id)
            plan_items: List[ChangePlanItemCreate] = []
            for idx, it in enumerate(folder_items, start=1):
                clean_rel = it.relative_path.strip().replace("\\", "/").lstrip("/")
                try:
                    PathValidator.resolve_and_verify_scope(folder, clean_rel)
                except ManagedFolderException as e:
                    raise StorageException(f"Invalid target path '{clean_rel}': {str(e)}")

                plan_items.append(
                    ChangePlanItemCreate(
                        operation=OperationType.DELETE_TO_RECYCLE_BIN,
                        source_relative_path=clean_rel,
                        sequence_no=idx,
                    )
                )

            plan = transaction_service.create_plan(
                ChangePlanCreate(
                    managed_folder_id=folder.id,
                    title=f"{base_title} ({folder.name})",
                    plan_type=PlanType.MANUAL,
                    items=plan_items,
                ),
                created_by="user",
            )
            transaction_service.submit_plan(plan.id)
            created_plan_ids.append(plan.id)
            total_queued += len(plan_items)

        return StorageCleanupPlanResponse(
            created_plan_ids=created_plan_ids,
            total_items_queued=total_queued,
            message=f"Queued {total_queued} item(s) across {len(created_plan_ids)} change plan(s) in Review Changes.",
        )
