import json
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.db.models.audit import AuditLog
from backend.app.db.models.change_plan import ChangePlan
from backend.app.db.models.execution import ExecutionJob
from backend.app.db.models.file import FileRecord
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.models.scan_job import ScanJob
from backend.app.db.models.analysis_run import AnalysisRun
from backend.app.schemas.dashboard import (
    DashboardAnalyzeRequest,
    DashboardCategoryItem,
    DashboardFolderDistributionItem,
    DashboardJobItem,
    DashboardManagedFolderItem,
    DashboardOverviewResponse,
    DashboardRecentActivityItem,
    DashboardRecommendationItem,
    DashboardStorageTrendPoint,
    DashboardSummaryCards,
)
from backend.app.services.filesystem import detect_file_category, FilesystemService
from backend.app.services.storage import StorageAnalyzerService


class DashboardService:
    def __init__(self, db: Session):
        self.db = db

    def get_overview(self) -> DashboardOverviewResponse:
        """Loads persisted metrics, storage breakdowns, activity, and jobs without scanning disk."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Managed Folders
        folders = (
            self.db.query(ManagedFolder)
            .filter(ManagedFolder.is_enabled == 1)
            .all()
        )
        total_folders = len(folders)

        # 2. Files and Sizes
        total_files = (
            self.db.query(func.count(FileRecord.id))
            .filter(FileRecord.item_type == "file", FileRecord.is_deleted == 0)
            .scalar()
            or 0
        )
        total_bytes = (
            self.db.query(func.sum(FileRecord.size_bytes))
            .filter(FileRecord.item_type == "file", FileRecord.is_deleted == 0)
            .scalar()
            or 0
        )

        storage_service = StorageAnalyzerService(self.db)
        latest_analysis = storage_service.get_latest_analysis()
        if latest_analysis:
            if latest_analysis.total_files_count > total_files:
                total_files = latest_analysis.total_files_count
            if latest_analysis.total_storage_bytes > total_bytes:
                total_bytes = latest_analysis.total_storage_bytes

        # 3. Pending Changes
        pending_changes = (
            self.db.query(func.count(ChangePlan.id))
            .filter(ChangePlan.status.in_(["pending_review", "pending", "draft"]))
            .scalar()
            or 0
        )

        summary_cards = DashboardSummaryCards(
            managed_folders_count=total_folders,
            total_files_count=total_files,
            total_size_bytes=total_bytes,
            pending_changes_count=pending_changes,
        )
        categories: List[DashboardCategoryItem] = []

        if latest_analysis and latest_analysis.category_distribution:
            for cd in latest_analysis.category_distribution:
                categories.append(
                    DashboardCategoryItem(
                        category=cd.category,
                        files_count=cd.files_count,
                        total_size_bytes=cd.total_size_bytes,
                        percentage=cd.percentage,
                    )
                )
        else:
            # On-the-fly categorization from indexed FileRecord database
            files = (
                self.db.query(FileRecord.name, FileRecord.size_bytes)
                .filter(FileRecord.item_type == "file", FileRecord.is_deleted == 0)
                .all()
            )
            cat_counts: Dict[str, int] = defaultdict(int)
            cat_bytes: Dict[str, int] = defaultdict(int)
            for f_name, f_size in files:
                cat = detect_file_category(f_name)
                cat_counts[cat] += 1
                cat_bytes[cat] += f_size or 0

            for cat, count in sorted(cat_counts.items(), key=lambda x: cat_bytes[x[0]], reverse=True):
                b = cat_bytes[cat]
                pct = round((b / total_bytes) * 100, 1) if total_bytes > 0 else 0.0
                categories.append(
                    DashboardCategoryItem(
                        category=cat,
                        files_count=count,
                        total_size_bytes=b,
                        percentage=pct,
                    )
                )

        # Ensure default standard categories exist if empty
        if not categories:
            for cat in ["Dokumen", "Gambar", "Video", "Arsip", "Lainnya"]:
                categories.append(
                    DashboardCategoryItem(
                        category=cat,
                        files_count=0,
                        total_size_bytes=0,
                        percentage=0.0,
                    )
                )

        # 5. Folder Distribution & Managed Folders List
        folder_dist: List[DashboardFolderDistributionItem] = []
        managed_folder_items: List[DashboardManagedFolderItem] = []

        for f in folders:
            # Calculate folder size and file count from FileRecord
            f_files = (
                self.db.query(func.count(FileRecord.id))
                .filter(
                    FileRecord.managed_folder_id == f.id,
                    FileRecord.item_type == "file",
                    FileRecord.is_deleted == 0,
                )
                .scalar()
                or 0
            )
            f_bytes = (
                self.db.query(func.sum(FileRecord.size_bytes))
                .filter(
                    FileRecord.managed_folder_id == f.id,
                    FileRecord.item_type == "file",
                    FileRecord.is_deleted == 0,
                )
                .scalar()
                or 0
            )
            f_analysis = storage_service.get_latest_analysis(folder_id=f.id)
            if f_analysis:
                if f_analysis.total_files_count > f_files:
                    f_files = f_analysis.total_files_count
                if f_analysis.total_storage_bytes > f_bytes:
                    f_bytes = f_analysis.total_storage_bytes

            pct = round((f_bytes / total_bytes) * 100, 1) if total_bytes > 0 else 0.0

            # Accessibility check
            is_acc = Path(f.root_path).exists() if f.root_path else False

            dist_item = DashboardFolderDistributionItem(
                id=f.id,
                name=f.name,
                root_path=f.root_path,
                size_bytes=f_bytes,
                files_count=f_files,
                percentage=pct,
            )
            folder_dist.append(dist_item)

            managed_folder_items.append(
                DashboardManagedFolderItem(
                    id=f.id,
                    name=f.name,
                    root_path=f.root_path,
                    size_bytes=f_bytes,
                    files_count=f_files,
                    is_monitoring_active=bool(f.monitoring_enabled),
                    is_accessible=is_acc,
                    last_scanned_at=f.last_scanned_at,
                )
            )

        folder_dist.sort(key=lambda x: x.size_bytes, reverse=True)
        top_folder_dist = folder_dist[:5]

        # 6. Recent Activities from Audit Logs
        recent_logs = (
            self.db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(5)
            .all()
        )
        recent_activities: List[DashboardRecentActivityItem] = []
        for log in recent_logs:
            loc = None
            details_str = None
            if log.details_json:
                try:
                    d = json.loads(log.details_json)
                    loc = d.get("location") or d.get("path") or d.get("folder_name")
                    details_str = d.get("summary") or d.get("description") or log.details_json[:80]
                except Exception:
                    details_str = log.details_json[:80]

            recent_activities.append(
                DashboardRecentActivityItem(
                    id=log.id,
                    timestamp=log.created_at,
                    action=log.action,
                    actor_type=log.actor_type or "system",
                    entity_type=log.entity_type or "file",
                    entity_id=log.entity_id,
                    location=loc,
                    details=details_str,
                    status="success" if "fail" not in log.action.lower() and "error" not in log.action.lower() else "failed",
                )
            )

        # 7. Recommendations
        recommendations: List[DashboardRecommendationItem] = []
        if latest_analysis and latest_analysis.recommendations:
            for rec in latest_analysis.recommendations:
                rec_type = "duplicates" if "duplicate" in rec.id else "general"
                target = "/storage"
                if rec_type == "duplicates":
                    target = "/storage"
                recommendations.append(
                    DashboardRecommendationItem(
                        id=rec.id,
                        title=rec.title,
                        description=rec.description,
                        type=rec_type,
                        target_route=target,
                        impact_count=rec.count,
                        impact_bytes=rec.impact_bytes,
                    )
                )

        # Add structure & rename recommendations only if actual files exist in managed folders
        if total_files > 0 and len(recommendations) < 3:
            recommendations.append(
                DashboardRecommendationItem(
                    id="rec_org_1",
                    title="Rapikan Struktur Folder",
                    description="Kelompokkan file berdasarkan tanggal atau kategori dokumen secara otomatis.",
                    type="organization",
                    target_route="/organization",
                    impact_count=total_files,
                    impact_bytes=0,
                )
            )
            recommendations.append(
                DashboardRecommendationItem(
                    id="rec_rename_1",
                    title="Standardisasi Nama File",
                    description="Terapkan pola penamaan bersih kebab-case atau tanggal pada file yang tidak rapi.",
                    type="smart_rename",
                    target_route="/smart-rename",
                    impact_count=total_files,
                    impact_bytes=0,
                )
            )

        # 8. Background Jobs (Scan Jobs + Execution Jobs + Analysis Runs)
        jobs: List[DashboardJobItem] = []

        scan_jobs = (
            self.db.query(ScanJob)
            .order_by(ScanJob.created_at.desc())
            .limit(3)
            .all()
        )
        for sj in scan_jobs:
            fname = sj.managed_folder.name if sj.managed_folder else None
            pct = 100 if sj.status == "completed" else 50 if sj.status == "running" else 0
            jobs.append(
                DashboardJobItem(
                    id=sj.id,
                    job_name=f"Pemindaian {fname or 'Folder'}",
                    job_type="scan",
                    status=sj.status,
                    progress_percent=pct,
                    folder_name=fname,
                    started_at=sj.started_at,
                    finished_at=sj.finished_at,
                    error_message=sj.error_message,
                )
            )

        exec_jobs = (
            self.db.query(ExecutionJob)
            .order_by(ExecutionJob.created_at.desc())
            .limit(3)
            .all()
        )
        for ej in exec_jobs:
            pct = 100 if ej.status == "completed" else 50 if ej.status == "running" else 0
            jobs.append(
                DashboardJobItem(
                    id=ej.id,
                    job_name=f"Eksekusi Rencana #{ej.change_plan_id[:8]}",
                    job_type="transaction",
                    status=ej.status,
                    progress_percent=pct,
                    folder_name=None,
                    started_at=ej.started_at,
                    finished_at=ej.finished_at,
                    error_message=ej.error_message,
                )
            )

        analysis_jobs = (
            self.db.query(AnalysisRun)
            .order_by(AnalysisRun.created_at.desc())
            .limit(3)
            .all()
        )
        for aj in analysis_jobs:
            fname = aj.managed_folder.name if aj.managed_folder else None
            pct = 100 if aj.status == "completed" else 50 if aj.status == "running" else 0
            jobs.append(
                DashboardJobItem(
                    id=aj.id,
                    job_name=f"Analisis Penyimpanan ({aj.analysis_type})",
                    job_type="analysis",
                    status=aj.status,
                    progress_percent=pct,
                    folder_name=fname,
                    started_at=aj.started_at,
                    finished_at=aj.finished_at,
                    error_message=aj.error_message,
                )
            )

        # Sort jobs by started_at / id and limit to 5
        jobs.sort(key=lambda x: x.started_at or "", reverse=True)
        jobs = jobs[:5]

        # 9. Storage Trend from actual persisted history and indexed data
        storage_history: List[DashboardStorageTrendPoint] = []
        past_runs = (
            self.db.query(AnalysisRun)
            .filter(AnalysisRun.status == "completed", AnalysisRun.analysis_type == "storage")
            .order_by(AnalysisRun.created_at.asc())
            .all()
        )
        date_points: Dict[str, DashboardStorageTrendPoint] = {}
        for r in past_runs:
            if not r.created_at:
                continue
            d_str = r.created_at[:10]  # YYYY-MM-DD
            b_val = 0
            f_val = 0
            if r.result_json:
                try:
                    res_obj = json.loads(r.result_json)
                    b_val = res_obj.get("total_storage_bytes", 0)
                    f_val = res_obj.get("total_files_count", 0)
                except Exception:
                    pass
            date_points[d_str] = DashboardStorageTrendPoint(
                date=d_str,
                total_size_bytes=b_val,
                files_count=f_val,
                files_added=0,
                files_modified=0,
                files_deleted=0,
            )

        # If there are indexed files and today is not yet in the points, add today's point
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if total_files > 0 and today_str not in date_points:
            date_points[today_str] = DashboardStorageTrendPoint(
                date=today_str,
                total_size_bytes=total_bytes,
                files_count=total_files,
                files_added=0,
                files_modified=0,
                files_deleted=0,
            )

        storage_history = sorted(date_points.values(), key=lambda p: p.date)

        # Determine if data is stale (e.g., registered folders exist with files that have never been scanned)
        is_stale = False
        if folders:
            for f in folders:
                if not f.last_scanned_at and total_files == 0:
                    is_stale = True
                    break

        return DashboardOverviewResponse(
            summary_cards=summary_cards,
            storage_categories=categories,
            folder_distribution=top_folder_dist,
            managed_folders=managed_folder_items,
            recent_activities=recent_activities,
            recommendations=recommendations,
            jobs=jobs,
            storage_history=storage_history,
            is_stale=is_stale,
            last_refreshed_at=now_iso,
        )

    def trigger_analysis(self, payload: DashboardAnalyzeRequest) -> DashboardJobItem:
        """Triggers a background analysis or scan job based on the mode requested."""
        now_iso = datetime.now(timezone.utc).isoformat()
        if payload.folder_id:
            folder = self.db.query(ManagedFolder).filter(ManagedFolder.id == payload.folder_id).first()
            folder_name = folder.name if folder else None
        else:
            folder_name = "Semua Folder"

        storage_service = StorageAnalyzerService(self.db)
        if payload.mode == "deep":
            if payload.folder_id:
                storage_service.analyze_folder(folder_id=payload.folder_id, calculate_hashes=True)
            else:
                storage_service.analyze_all_folders(calculate_hashes=True)
            job_name = f"Analisis Mendalam {folder_name}"
            job_type = "analysis"
        else:
            # Metadata scan without heavy hash computation
            if payload.folder_id:
                storage_service.analyze_folder(folder_id=payload.folder_id, calculate_hashes=False)
            else:
                storage_service.analyze_all_folders(calculate_hashes=False)
            job_name = f"Pemindaian Metadata {folder_name}"
            job_type = "scan"

        latest_scan = (
            self.db.query(ScanJob)
            .order_by(ScanJob.created_at.desc())
            .first()
        )
        job_id = latest_scan.id if latest_scan else f"job_{int(datetime.now().timestamp())}"
        started_at = latest_scan.started_at if latest_scan and latest_scan.started_at else now_iso
        finished_at = latest_scan.finished_at if latest_scan and latest_scan.finished_at else datetime.now(timezone.utc).isoformat()

        return DashboardJobItem(
            id=job_id,
            job_name=job_name,
            job_type=job_type,
            status="completed",
            progress_percent=100,
            folder_name=folder_name,
            started_at=started_at,
            finished_at=finished_at,
        )
