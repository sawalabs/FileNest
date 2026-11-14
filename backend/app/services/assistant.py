import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.app.core.logging import logger
from backend.app.db.base import generate_uuid, utc_now_iso
from backend.app.db.models.managed_folder import ManagedFolder
from backend.app.db.repositories.audit import AuditLogRepository
from backend.app.schemas.assistant import (
    AssistantActionProposal,
    AssistantExplainRequest,
    AssistantExplainResponse,
    AssistantSuggestPlanRequest,
    AssistantSuggestPlanResponse,
    AssistantTargetType,
    QuickPromptItem,
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


class AssistantException(Exception):
    """Raised for errors or security violations in the contextual assistant."""
    pass


class ContextualAssistantService:
    """Provides bounded, contextual AI explanations and safe action proposals.
    
    Guarantees:
    1. Context is strictly confined to the selected Managed Folder.
    2. Zero direct filesystem mutations.
    3. Action proposals are strictly routed to Review Changes as draft Change Plans.
    """

    def __init__(self, db: Session):
        self.db = db
        self.settings_service = SettingsService(db)
        self.storage_service = StorageAnalyzerService(db)
        self.transaction_service = TransactionManagerService(db)
        self.router_service = RouterGatewayService(db)
        self.audit_repo = AuditLogRepository(db)

    # -------------------------------------------------------------------------
    # Managed Folder Verification & Confinement
    # -------------------------------------------------------------------------

    def _get_managed_folder(self, folder_id: str) -> ManagedFolder:
        folder = self.db.query(ManagedFolder).filter(ManagedFolder.id == folder_id).first()
        if not folder:
            raise AssistantException(f"Managed folder '{folder_id}' not found")
        if not folder.is_enabled:
            raise AssistantException(f"Managed folder '{folder.name}' is disabled")
        return folder

    # -------------------------------------------------------------------------
    # AI Model Gateway Invocation (Hermes / 9Router / OpenRouter)
    # -------------------------------------------------------------------------

    async def _ask_ai_model(self, system_prompt: str, user_prompt: str) -> Optional[str]:
        """Queries 9Router / Hermes gateway with automatic fallback to OpenRouter or heuristic."""
        try:
            from backend.app.schemas.router_gateway import RouterChatMessage, RouterChatRequest

            res = await self.router_service.chat_completion(
                RouterChatRequest(
                    messages=[
                        RouterChatMessage(role="system", content=system_prompt),
                        RouterChatMessage(role="user", content=user_prompt),
                    ],
                    temperature=0.3,
                    max_tokens=600,
                    timeout_seconds=20,
                )
            )
            if res and res.content and res.content.strip():
                return res.content.strip()
        except Exception as e:
            logger.debug(f"AI Router call in assistant fell back to heuristic: {e}")
        return None

    # -------------------------------------------------------------------------
    # Contextual Explanation
    # -------------------------------------------------------------------------

    async def explain_entity(self, request: AssistantExplainRequest) -> AssistantExplainResponse:
        """Generates a bounded contextual explanation for the target entity."""
        folder = self._get_managed_folder(request.managed_folder_id)

        if request.target_type == "file":
            return await self._explain_file(folder, request)
        elif request.target_type == "folder":
            return await self._explain_folder(folder, request)
        elif request.target_type == "plan":
            return await self._explain_plan(folder, request)
        elif request.target_type == "analysis":
            return await self._explain_analysis(folder, request)
        elif request.target_type == "general":
            return await self._explain_general(folder, request)
        else:
            raise AssistantException(f"Unsupported target_type '{request.target_type}'")

    # -------------------------------------------------------------------------
    # File Explanation
    # -------------------------------------------------------------------------

    async def _explain_file(
        self, folder: ManagedFolder, request: AssistantExplainRequest
    ) -> AssistantExplainResponse:
        rel_path = request.relative_path
        if not rel_path:
            raise AssistantException("relative_path is required for file explanation")

        # Confinement check
        abs_path = PathValidator.resolve_and_verify_scope(folder, rel_path)
        if not abs_path.exists():
            raise AssistantException(f"Target file does not exist: {rel_path}")
        if not abs_path.is_file():
            raise AssistantException(f"Target is not a regular file: {rel_path}")
        if is_reparse_point_or_symlink(abs_path):
            raise AssistantException("Symlinks and junctions cannot be analyzed")

        st = abs_path.stat()
        ext = abs_path.suffix.lower().lstrip(".")
        category = detect_file_category(ext)
        size_bytes = st.st_size
        modified_at = format_timestamp(st.st_mtime)

        # Build insights
        insights = [
            f"Kategori berkas: {category.title()} (ekstensi .{ext or 'tanpa ekstensi'})",
            f"Ukuran berkas: {self._format_bytes(size_bytes)}",
            f"Terakhir dimodifikasi: {modified_at}",
        ]

        if is_hidden_item(abs_path):
            insights.append("Berkas ini memiliki atribut hidden/tersembunyi.")

        # Safety evaluation
        safety = (
            "Aman untuk dipindahkan atau diorganisasi. Berkas berada dalam batas aman Managed Folder. "
            "Setiap mutasi akan diproses melalui Transaction Manager dengan jaminan rollback dan Recycle Bin."
        )

        # Suggested actions
        suggested_actions: List[AssistantActionProposal] = []
        parent_rel = Path(rel_path).parent.as_posix()

        # Suggest organization if file is loose in root
        if parent_rel in (".", ""):
            target_subfolder = f"{category.title()}s"
            dest_rel = f"{target_subfolder}/{abs_path.name}"
            suggested_actions.append(
                AssistantActionProposal(
                    proposal_id=generate_uuid(),
                    title=f"Pindahkan ke folder {target_subfolder}",
                    description=f"Kelompokkan berkas ini ke dalam folder kategori '{target_subfolder}' agar root folder tetap rapi.",
                    plan_type=PlanType.ORGANIZE,
                    items=[
                        ChangePlanItemCreate(
                            operation=OperationType.MOVE,
                            source_relative_path=rel_path,
                            destination_relative_path=dest_rel,
                            sequence_no=1,
                        )
                    ],
                )
            )

        # Suggest smart rename if name contains messy characters
        stem = abs_path.stem
        if " " in stem or "-" in stem or "_" in stem or any(c.isupper() for c in stem):
            clean_stem = stem.replace(" ", "_").lower()
            if clean_stem != stem.lower():
                new_filename = f"{clean_stem}.{ext}" if ext else clean_stem
                new_rel = f"{parent_rel}/{new_filename}" if parent_rel not in (".", "") else new_filename
                suggested_actions.append(
                    AssistantActionProposal(
                        proposal_id=generate_uuid(),
                        title="Normalisasi nama berkas",
                        description=f"Ubah nama berkas menjadi format standar snake_case: '{new_filename}'.",
                        plan_type=PlanType.RENAME,
                        items=[
                            ChangePlanItemCreate(
                                operation=OperationType.RENAME,
                                source_relative_path=rel_path,
                                destination_relative_path=new_rel,
                                sequence_no=1,
                            )
                        ],
                    )
                )

        summary = (
            f"Berkas '{abs_path.name}' adalah dokumen berjenis {category} "
            f"dengan ukuran {self._format_bytes(size_bytes)} yang tersimpan di '{rel_path}'."
        )

        if request.user_query:
            ai_file_resp = await self._ask_ai_model(
                system_prompt="Anda adalah Asisten Kontekstual FileNest. Jelaskan berkas pengguna secara aman dan solutif dalam bahasa Indonesia.",
                user_prompt=(
                    f"Konteks Berkas: '{abs_path.name}' di folder '{folder.name}' ({rel_path})\n"
                    f"Kategori: {category}, Ukuran: {self._format_bytes(size_bytes)}, Ekstensi: .{ext}, Dimodifikasi: {modified_at}\n\n"
                    f"Pertanyaan Pengguna: {request.user_query}"
                ),
            )
            if ai_file_resp:
                summary = f"{summary}\n\n{ai_file_resp}"

        return AssistantExplainResponse(
            managed_folder_id=folder.id,
            target_type="file",
            target_name=abs_path.name,
            relative_path=rel_path,
            title=f"Analisis Berkas: {abs_path.name}",
            summary=summary,
            key_insights=insights,
            metadata={
                "name": abs_path.name,
                "size_bytes": size_bytes,
                "category": category,
                "extension": ext,
                "modified_at": modified_at,
                "relative_path": rel_path,
            },
            safety_assessment=safety,
            suggested_actions=suggested_actions,
            timestamp=utc_now_iso(),
        )

    # -------------------------------------------------------------------------
    # Folder Explanation
    # -------------------------------------------------------------------------

    async def _explain_folder(
        self, folder: ManagedFolder, request: AssistantExplainRequest
    ) -> AssistantExplainResponse:
        rel_path = request.relative_path or ""
        abs_path = PathValidator.resolve_and_verify_scope(folder, rel_path)

        if not abs_path.exists():
            raise AssistantException(f"Target directory does not exist: {rel_path}")
        if not abs_path.is_dir():
            raise AssistantException(f"Target is not a directory: {rel_path}")
        if is_reparse_point_or_symlink(abs_path):
            raise AssistantException("Symlinks and junctions cannot be analyzed")

        # Scan folder summary
        total_size = 0
        file_count = 0
        dir_count = 0
        categories: Dict[str, int] = {}
        loose_files: List[Path] = []

        try:
            for entry in abs_path.iterdir():
                if entry.is_dir():
                    dir_count += 1
                elif entry.is_file():
                    file_count += 1
                    try:
                        sz = entry.stat().st_size
                        total_size += sz
                    except OSError:
                        pass
                    ext = entry.suffix.lower().lstrip(".")
                    cat = detect_file_category(ext)
                    categories[cat] = categories.get(cat, 0) + 1
                    loose_files.append(entry)
        except PermissionError:
            raise AssistantException("Izin akses ditolak saat membaca folder")

        insights = [
            f"Jumlah berkas: {file_count} berkas",
            f"Jumlah subfolder: {dir_count} subfolder",
            f"Total ukuran berkas langsung: {self._format_bytes(total_size)}",
        ]

        if categories:
            cat_breakdown = ", ".join(f"{k.title()}: {v}" for k, v in sorted(categories.items()))
            insights.append(f"Distribusi tipe: {cat_breakdown}")

        suggested_actions: List[AssistantActionProposal] = []

        # Suggest cleanup proposal if there are loose files in folder
        if file_count > 0:
            items: List[ChangePlanItemCreate] = []
            seq = 1
            for f in loose_files[:15]:
                ext = f.suffix.lower().lstrip(".")
                cat = detect_file_category(ext)
                f_rel = (
                    f"{rel_path}/{f.name}" if rel_path and rel_path not in (".", "") else f.name
                )
                target_sub = f"{cat.title()}s"
                dest_rel = (
                    f"{rel_path}/{target_sub}/{f.name}"
                    if rel_path and rel_path not in (".", "")
                    else f"{target_sub}/{f.name}"
                )
                items.append(
                    ChangePlanItemCreate(
                        operation=OperationType.MOVE,
                        source_relative_path=f_rel,
                        destination_relative_path=dest_rel,
                        sequence_no=seq,
                    )
                )
                seq += 1

            suggested_actions.append(
                AssistantActionProposal(
                    proposal_id=generate_uuid(),
                    title=f"Kategorisasi {len(items)} berkas lepas",
                    description=f"Kelompokkan {len(items)} berkas langsung ke dalam subfolder berdasarkan kategori (Dokumen, Gambar, dll.).",
                    plan_type=PlanType.ORGANIZE,
                    items=items,
                )
            )

        summary = (
            f"Folder '{abs_path.name or folder.name}' berisi {file_count} berkas dan {dir_count} subfolder, "
            f"dengan total kapasitas berkas sebesar {self._format_bytes(total_size)}."
        )

        if request.user_query:
            ai_folder_resp = await self._ask_ai_model(
                system_prompt="Anda adalah Asisten Kontekstual FileNest. Jelaskan subfolder pengguna secara aman dan solutif dalam bahasa Indonesia.",
                user_prompt=(
                    f"Konteks Subfolder: '{abs_path.name or folder.name}' di folder '{folder.name}' ({rel_path})\n"
                    f"Jumlah Berkas: {file_count}, Subfolder: {dir_count}, Total Ukuran: {self._format_bytes(total_size)}\n"
                    f"Kategori Berkas: {categories}\n\n"
                    f"Pertanyaan Pengguna: {request.user_query}"
                ),
            )
            if ai_folder_resp:
                summary = f"{summary}\n\n{ai_folder_resp}"

        safety = (
            "Aman untuk ditata. Asisten tidak dapat menghapus folder atau berkas secara langsung; "
            "setiap rekomendasi harus disetujui dalam menu Review Changes."
        )

        return AssistantExplainResponse(
            managed_folder_id=folder.id,
            target_type="folder",
            target_name=abs_path.name or folder.name,
            relative_path=rel_path,
            title=f"Analisis Folder: {abs_path.name or folder.name}",
            summary=summary,
            key_insights=insights,
            metadata={
                "name": abs_path.name or folder.name,
                "total_size_bytes": total_size,
                "file_count": file_count,
                "dir_count": dir_count,
                "categories": categories,
                "relative_path": rel_path,
            },
            safety_assessment=safety,
            suggested_actions=suggested_actions,
            timestamp=utc_now_iso(),
        )

    # -------------------------------------------------------------------------
    # Change Plan Explanation
    # -------------------------------------------------------------------------

    async def _explain_plan(
        self, folder: ManagedFolder, request: AssistantExplainRequest
    ) -> AssistantExplainResponse:
        plan_id = request.entity_id
        if not plan_id:
            raise AssistantException("entity_id (plan_id) is required for plan explanation")

        plan = self.transaction_service.get_plan(plan_id)
        if plan.managed_folder_id != folder.id:
            raise AssistantException("Change Plan does not belong to the selected Managed Folder")

        validation = self.transaction_service.validate_plan(plan.id)
        conflicts_count = sum(1 for i in validation.issues if i.issue_type == "conflict")

        insights = [
            f"Tipe Rencana: {plan.plan_type.upper()}",
            f"Status Rencana: {plan.status.upper()}",
            f"Dibuat oleh: {plan.created_by.upper()}",
            f"Total Operasi: {len(plan.items)} tindakan",
        ]

        if conflicts_count > 0:
            insights.append(
                f"Peringatan Konflik: {conflicts_count} tabrakan tujuan terdeteksi (eksekusi diblokir hingga diperbaiki)."
            )
        else:
            insights.append("Validasi Integritas: Tidak ada konflik nama atau path ditemukan. Siap dieksekusi setelah persetujuan.")

        ops_summary: Dict[str, int] = {}
        for item in plan.items:
            ops_summary[item.operation] = ops_summary.get(item.operation, 0) + 1

        ops_str = ", ".join(f"{k}: {v}" for k, v in ops_summary.items())
        insights.append(f"Rincian Operasi: {ops_str or 'Kosong'}")

        safety = (
            "Rencana ini dilindungi oleh Transaction Manager. Jika disetujui dan dijalankan, setiap langkah "
            "diverifikasi ulang sebelum eksekusi. Jika terjadi interupsi atau galat di tengah jalan, sistem akan "
            "melakukan rollback otomatis ke kondisi semula."
        )

        summary = (
            f"Rencana perubahan '{plan.title}' memuat {len(plan.items)} operasi "
            f"dengan status saat ini '{plan.status}'. Rencana ini belum memutasi berkas apapun di disk."
        )

        if request.user_query:
            ai_plan_resp = await self._ask_ai_model(
                system_prompt="Anda adalah Asisten Kontekstual FileNest. Jelaskan rencana perubahan filesystem secara aman dan solutif dalam bahasa Indonesia.",
                user_prompt=(
                    f"Rencana: '{plan.title}' ({plan.plan_type}), Status: {plan.status}, Operasi: {len(plan.items)}\n"
                    f"Konflik: {conflicts_count}, Operasi Rincian: {ops_str}\n\n"
                    f"Pertanyaan Pengguna: {request.user_query}"
                ),
            )
            if ai_plan_resp:
                summary = f"{summary}\n\n{ai_plan_resp}"

        return AssistantExplainResponse(
            managed_folder_id=folder.id,
            target_type="plan",
            target_name=plan.title,
            title=f"Analisis Rencana: {plan.title}",
            summary=summary,
            key_insights=insights,
            metadata={
                "plan_id": plan.id,
                "status": plan.status,
                "plan_type": plan.plan_type,
                "items_count": len(plan.items),
                "is_valid": validation.is_valid,
                "conflicts_count": conflicts_count,
            },
            safety_assessment=safety,
            suggested_actions=[],
            timestamp=utc_now_iso(),
        )

    # -------------------------------------------------------------------------
    # Analysis & General Explanations
    # -------------------------------------------------------------------------

    async def _explain_analysis(
        self, folder: ManagedFolder, request: AssistantExplainRequest
    ) -> AssistantExplainResponse:
        summary = (
            f"Ringkasan analitik penyimpanan untuk folder terkelola '{folder.name}'. "
            "Asisten dapat membantu mengidentifikasi berkas duplikat, file berukuran besar, dan potensi penghematan ruang."
        )

        insights = [
            f"Managed Folder: {folder.name}",
            f"Lokasi Path: {folder.root_path}",
            "Pembersihan disarankan menggunakan Review Changes untuk memindahkan berkas duplikat ke Recycle Bin.",
        ]

        if request.user_query:
            ai_ana_resp = await self._ask_ai_model(
                system_prompt="Anda adalah Asisten Kontekstual FileNest. Jelaskan analitik penyimpanan dalam bahasa Indonesia.",
                user_prompt=f"Folder: '{folder.name}' ({folder.root_path})\nPertanyaan Pengguna: {request.user_query}",
            )
            if ai_ana_resp:
                summary = f"{summary}\n\n{ai_ana_resp}"

        safety = (
            "Semua aksi analisis bersifat read-only. Rekomendasi tidak akan mengubah sistem file secara langsung."
        )

        return AssistantExplainResponse(
            managed_folder_id=folder.id,
            target_type="analysis",
            target_name="Storage & Health Analysis",
            title=f"Analisis Penyimpanan: {folder.name}",
            summary=summary,
            key_insights=insights,
            metadata={"folder_id": folder.id, "name": folder.name, "path": folder.root_path},
            safety_assessment=safety,
            suggested_actions=[],
            timestamp=utc_now_iso(),
        )

    async def _explain_general(
        self, folder: ManagedFolder, request: AssistantExplainRequest
    ) -> AssistantExplainResponse:
        abs_root = Path(folder.root_path)
        file_count = 0
        dir_count = 0
        total_size = 0
        categories: Dict[str, int] = {}
        loose_files: List[Path] = []

        if abs_root.exists() and abs_root.is_dir():
            try:
                for entry in abs_root.iterdir():
                    if entry.is_dir():
                        dir_count += 1
                    elif entry.is_file():
                        file_count += 1
                        try:
                            total_size += entry.stat().st_size
                        except OSError:
                            pass
                        ext = entry.suffix.lower().lstrip(".")
                        cat = detect_file_category(ext)
                        categories[cat] = categories.get(cat, 0) + 1
                        loose_files.append(entry)
            except (PermissionError, OSError):
                pass

        cat_breakdown = ", ".join(f"{k.title()}: {v}" for k, v in sorted(categories.items())) if categories else "Belum ada berkas"

        user_q = (request.user_query or "").strip()
        summary: str = ""
        insights: List[str] = []

        if user_q:
            ai_resp = await self._ask_ai_model(
                system_prompt=(
                    "Anda adalah Asisten Kontekstual AI FileNest yang bertugas membantu pengguna mengelola, "
                    "menganalisis struktur file/folder, dan memberikan rekomendasi penataan yang aman. "
                    "Jawab dalam bahasa Indonesia dengan jelas, ramah, dan solutif. "
                    "Sebutkan kondisi nyata folder pengguna, potensi risiko, dan rekomendasi langkah penataan. "
                    "Ingatkan bahwa setiap perubahan aman dan harus disetujui di Review Changes sebelum dieksekusi."
                ),
                user_prompt=(
                    f"Konteks Folder Terkelola: '{folder.name}' ({folder.root_path})\n"
                    f"Statistik Root: {file_count} berkas lepas, {dir_count} subfolder, Total Ukuran: {self._format_bytes(total_size)}\n"
                    f"Distribusi Kategori: {cat_breakdown}\n"
                    f"Contoh berkas: {[f.name for f in loose_files[:8]]}\n\n"
                    f"Pertanyaan Pengguna: {user_q}"
                ),
            )
            if ai_resp:
                summary = ai_resp
                insights = [
                    f"Folder Terkelola: {folder.name}",
                    f"Total Berkas Lepas: {file_count} berkas ({self._format_bytes(total_size)})",
                    f"Kategori Terdeteksi: {cat_breakdown}",
                    "Semua rekomendasi penataan dilindungi oleh Transaction Manager.",
                ]
            else:
                q_lower = user_q.lower()
                if any(w in q_lower for w in ["rapi", "organis", "organize", "tata", "kategori"]):
                    summary = (
                        f"Berdasarkan analisis folder '{folder.name}', terdapat {file_count} berkas lepas di root folder "
                        f"dan {dir_count} subfolder dengan total ukuran {self._format_bytes(total_size)}. "
                        f"Rekomendasi terbaik adalah mengelompokkan berkas-berkas lepas tersebut ke dalam subfolder sesuai kategori "
                        f"({cat_breakdown}) agar direktori utama tetap terstruktur rapi."
                    )
                elif any(w in q_lower for w in ["rename", "nama", "format"]):
                    summary = (
                        f"Untuk folder '{folder.name}', asisten dapat membantu menstandarkan format penamaan berkas. "
                        f"Penamaan yang rapi dan konsisten (misalnya penambahan tanggal atau penghapusan karakter acak) "
                        f"mempermudah pencarian berkas di kemudian hari."
                    )
                elif any(w in q_lower for w in ["duplikat", "duplicate", "bersih", "hapus", "sampah"]):
                    summary = (
                        f"Pembersihan folder '{folder.name}' dapat dilakukan secara aman. "
                        f"Sistem FileNest tidak pernah menghapus berkas secara permanen secara otomatis; "
                        f"setiap penghapusan dialihkan ke Recycle Bin/Karantina lokal dan wajib melewati persetujuan Anda di Review Changes."
                    )
                elif any(w in q_lower for w in ["ruang", "kapasitas", "ukuran", "size", "storage", "penyimpanan"]):
                    summary = (
                        f"Folder '{folder.name}' saat ini menggunakan total {self._format_bytes(total_size)} "
                        f"untuk {file_count} berkas langsung. Distribusi kategori: {cat_breakdown}."
                    )
                else:
                    summary = (
                        f"Menanggapi pertanyaan Anda '{user_q}': "
                        f"Folder '{folder.name}' memiliki {file_count} berkas lepas dan {dir_count} subfolder ({self._format_bytes(total_size)}). "
                        f"Anda dapat memilih berkas spesifik untuk dianalisis lebih mendalam, atau membuat rencana penataan otomatis di bawah ini."
                    )

                insights = [
                    f"Jumlah Berkas di Root: {file_count} berkas",
                    f"Subfolder Terdaftar: {dir_count} subfolder",
                    f"Distribusi Berkas: {cat_breakdown}",
                    "Perlindungan Mutasi: Dikelola penuh oleh Transaction Manager.",
                ]
        else:
            summary = (
                f"Asisten Kontekstual siap membantu Anda mengelola '{folder.name}'. "
                f"Folder ini memiliki {file_count} berkas lepas dan {dir_count} subfolder ({self._format_bytes(total_size)}). "
                f"Pilih salah satu chip prompt rekomendasi atau ajukan pertanyaan untuk menata berkas secara aman."
            )
            insights = [
                f"Total Berkas di Root: {file_count} berkas ({self._format_bytes(total_size)})",
                f"Kategori Berkas: {cat_breakdown}",
                "Pilih berkas atau folder spesifik untuk analisis detail dan periksa jaminan keamanan.",
            ]

        safety = (
            "Asisten tidak memiliki izin untuk memodifikasi berkas secara langsung. "
            "Setiap proposal tindakan wajib disetujui di menu Review Changes sebelum Transaction Manager mengeksekusinya."
        )

        suggested_actions: List[AssistantActionProposal] = []
        if loose_files:
            items: List[ChangePlanItemCreate] = []
            seq = 1
            for f in loose_files[:20]:
                ext = f.suffix.lower().lstrip(".")
                cat = detect_file_category(ext)
                target_sub = f"{cat.title()}s"
                items.append(
                    ChangePlanItemCreate(
                        operation=OperationType.MOVE,
                        source_relative_path=f.name,
                        destination_relative_path=f"{target_sub}/{f.name}",
                        sequence_no=seq,
                    )
                )
                seq += 1

            suggested_actions.append(
                AssistantActionProposal(
                    proposal_id=generate_uuid(),
                    title=f"Kategorisasi {len(items)} berkas lepas ke subfolder",
                    description=f"Pindahkan {len(items)} berkas di root '{folder.name}' ke subfolder kategori ({cat_breakdown}) agar terstruktur rapi.",
                    plan_type=PlanType.ORGANIZE,
                    items=items,
                )
            )

        return AssistantExplainResponse(
            managed_folder_id=folder.id,
            target_type="general",
            target_name=folder.name,
            title=f"Asisten Kontekstual: {folder.name}",
            summary=summary,
            key_insights=insights,
            metadata={
                "folder_id": folder.id,
                "name": folder.name,
                "file_count": file_count,
                "dir_count": dir_count,
                "total_size_bytes": total_size,
                "categories": categories,
            },
            safety_assessment=safety,
            suggested_actions=suggested_actions,
            timestamp=utc_now_iso(),
        )

    # -------------------------------------------------------------------------
    # Safe Plan Proposal Creation (Routes strictly to Review Changes)
    # -------------------------------------------------------------------------

    def create_proposed_plan(
        self, request: AssistantSuggestPlanRequest
    ) -> AssistantSuggestPlanResponse:
        """Creates a safe draft Change Plan in Review Changes from an assistant proposal.
        
        Guarantees:
        - created_by is strictly 'ai'
        - status is strictly 'pending_review'
        - All operations are validated before saving
        - NO direct filesystem mutation occurs
        """
        folder = self._get_managed_folder(request.managed_folder_id)

        # Validate that all items are within the managed folder scope
        for item in request.items:
            if item.source_relative_path:
                PathValidator.resolve_and_verify_scope(folder, item.source_relative_path)
            if item.destination_relative_path:
                PathValidator.resolve_and_verify_scope(folder, item.destination_relative_path)

        create_payload = ChangePlanCreate(
            managed_folder_id=folder.id,
            title=request.title,
            plan_type=request.plan_type,
            items=request.items,
        )

        # Create plan strictly with created_by='ai' -> lands in pending_review
        plan = self.transaction_service.create_plan(create_payload, created_by="ai")

        self.audit_repo.record(
            actor_type="ai",
            action="assistant_proposed_plan",
            entity_type="change_plan",
            entity_id=plan.id,
            details={
                "folder_id": folder.id,
                "title": plan.title,
                "items_count": len(plan.items),
            },
        )

        return AssistantSuggestPlanResponse(
            plan_id=plan.id,
            title=plan.title,
            plan_type=plan.plan_type,
            status=plan.status,
            items_count=len(plan.items),
            message="Rencana perubahan berhasil diajukan dan dialihkan ke Review Changes untuk persetujuan pengguna.",
            created_at=plan.created_at,
        )

    # -------------------------------------------------------------------------
    # Quick Prompts
    # -------------------------------------------------------------------------

    def get_quick_prompts(self, target_type: AssistantTargetType) -> List[QuickPromptItem]:
        """Returns contextual quick questions based on the active selection."""
        if target_type == "file":
            return [
                QuickPromptItem(
                    label="Jelaskan Berkas",
                    prompt="Apa jenis berkas ini dan mengapa tersimpan di sini?",
                    target_type="file",
                ),
                QuickPromptItem(
                    label="Evaluasi Keamanan",
                    prompt="Apakah berkas ini aman untuk dipindahkan atau dihapus?",
                    target_type="file",
                ),
                QuickPromptItem(
                    label="Saran Organisasi",
                    prompt="Bagaimana struktur folder atau penamaan yang ideal untuk berkas ini?",
                    target_type="file",
                ),
            ]
        elif target_type == "folder":
            return [
                QuickPromptItem(
                    label="Jelaskan Folder",
                    prompt="Bagaimana ringkasan isi dan pemakaian ruang folder ini?",
                    target_type="folder",
                ),
                QuickPromptItem(
                    label="Kategorikan Berkas Lepas",
                    prompt="Bagaimana menata berkas yang berserakan di dalam folder ini?",
                    target_type="folder",
                ),
                QuickPromptItem(
                    label="Saran Pembersihan",
                    prompt="Apakah ada subfolder kosong atau berkas lama yang perlu dibersihkan?",
                    target_type="folder",
                ),
            ]
        elif target_type == "plan":
            return [
                QuickPromptItem(
                    label="Jelaskan Rencana",
                    prompt="Apa saja dampak dan berkas yang akan berubah dari rencana ini?",
                    target_type="plan",
                ),
                QuickPromptItem(
                    label="Analisis Risiko",
                    prompt="Apakah ada risiko tabrakan nama atau potensi kehilangan data?",
                    target_type="plan",
                ),
                QuickPromptItem(
                    label="Jaminan Rollback",
                    prompt="Bagaimana mekanisme pemulihan jika terjadi kegagalan eksekusi?",
                    target_type="plan",
                ),
            ]
        else:
            return [
                QuickPromptItem(
                    label="Analisis Ruang",
                    prompt="Bagaimana kondisi kesehatan penyimpanan folder terkelola ini?",
                    target_type="general",
                ),
                QuickPromptItem(
                    label="Rekomendasi Penataan",
                    prompt="Apa langkah penataan terbaik untuk folder ini saat ini?",
                    target_type="general",
                ),
            ]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _format_bytes(bytes_count: int) -> str:
        if bytes_count < 1024:
            return f"{bytes_count} B"
        elif bytes_count < 1024 * 1024:
            return f"{bytes_count / 1024:.1f} KB"
        elif bytes_count < 1024 * 1024 * 1024:
            return f"{bytes_count / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"
