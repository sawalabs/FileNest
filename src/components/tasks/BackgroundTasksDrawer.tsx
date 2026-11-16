import React, { useState } from "react";
import {
  X,
  Loader2,
  CheckCircle2,
  CircleX,
  Ban,
  HardDrive,
  FilePenLine,
  FolderTree,
  ScanText,
  Layers,
  ArrowRight,
  Trash2,
  Clock,
} from "lucide-react";
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext";
import type { BackgroundJobItem, BackgroundJobType } from "@/types";

const getJobIcon = (type: BackgroundJobType) => {
  switch (type) {
    case "storage_analysis":
      return <HardDrive size={16} className="text-primary shrink-0" />;
    case "smart_rename_plan":
      return <FilePenLine size={16} className="text-blue-500 shrink-0" />;
    case "batch_ocr":
      return <ScanText size={16} className="text-amber-500 shrink-0" />;
    case "organization_plan":
      return <FolderTree size={16} className="text-emerald-500 shrink-0" />;
    default:
      return <Layers size={16} className="text-primary shrink-0" />;
  }
};

const getStatusBadge = (status: string) => {
  switch (status) {
    case "completed":
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-500 bg-emerald-500/10 px-2 py-0.5 rounded-full">
          <CheckCircle2 size={12} />
          Selesai
        </span>
      );
    case "failed":
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-destructive bg-destructive/10 px-2 py-0.5 rounded-full">
          <CircleX size={12} />
          Gagal
        </span>
      );
    case "cancelled":
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-full">
          <Ban size={12} />
          Dibatalkan
        </span>
      );
    case "running":
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-primary bg-primary/10 px-2 py-0.5 rounded-full">
          <Loader2 size={12} className="animate-spin" />
          Berjalan
        </span>
      );
    default:
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-muted-foreground bg-secondary px-2 py-0.5 rounded-full">
          <Clock size={12} />
          Antrean
        </span>
      );
  }
};

export const BackgroundTasksDrawer: React.FC = () => {
  const {
    activeJobs,
    recentJobs,
    isDrawerOpen,
    setIsDrawerOpen,
    cancelJob,
    dismissJob,
    navigateToJobResult,
  } = useBackgroundTasks();

  const [activeTab, setActiveTab] = useState<"active" | "recent">("active");
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  if (!isDrawerOpen) {
    return null;
  }

  const handleCancel = async (jobId: string) => {
    setCancellingId(jobId);
    try {
      await cancelJob(jobId);
    } finally {
      setCancellingId(null);
    }
  };

  const handleOpenResult = (job: BackgroundJobItem) => {
    setIsDrawerOpen(false);
    navigateToJobResult(job.id);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Panel Detail Pekerjaan Latar Belakang"
      className="fixed bottom-16 right-6 z-40 max-w-lg w-[94vw] sm:w-[480px] max-h-[75vh] flex flex-col bg-card/98 backdrop-blur-xl border border-border rounded-xl shadow-2xl overflow-hidden transition-all duration-300 animate-in fade-in slide-in-from-bottom-2"
    >
      {/* Header */}
      <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3 bg-secondary/30">
        <div className="flex items-center gap-2">
          <Layers size={18} className="text-primary" />
          <h2 className="text-sm font-semibold text-foreground">
            Pekerjaan Latar Belakang
          </h2>
          {activeJobs.length > 0 && (
            <span className="px-1.5 py-0.2 text-[10px] font-bold rounded-full bg-primary/20 text-primary">
              {activeJobs.length} aktif
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setIsDrawerOpen(false)}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          title="Tutup panel"
        >
          <X size={16} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center border-b border-border bg-secondary/15 px-4 pt-1 gap-4">
        <button
          type="button"
          onClick={() => setActiveTab("active")}
          className={`py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "active"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Sedang Berjalan ({activeJobs.length})
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("recent")}
          className={`py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
            activeTab === "recent"
              ? "border-primary text-primary"
              : "border-transparent text-muted-foreground hover:text-foreground"
          }`}
        >
          Riwayat ({recentJobs.length})
        </button>
      </div>

      {/* Body List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 divide-y divide-border/40">
        {activeTab === "active" ? (
          activeJobs.length === 0 ? (
            <div className="py-10 text-center text-xs text-muted-foreground space-y-1">
              <CheckCircle2 size={24} className="mx-auto text-emerald-500/60 mb-2" />
              <p className="font-medium text-foreground">Tidak ada proses yang sedang berjalan</p>
              <p>Semua pekerjaan latar belakang telah selesai.</p>
            </div>
          ) : (
            activeJobs.map((job) => (
              <div key={job.id} className="pt-3 first:pt-0 space-y-2">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    {getJobIcon(job.job_type)}
                    <span className="text-xs font-medium text-foreground truncate">
                      {job.title}
                    </span>
                  </div>
                  <button
                    type="button"
                    disabled={cancellingId === job.id}
                    onClick={() => handleCancel(job.id)}
                    className="text-xs font-medium text-muted-foreground hover:text-destructive px-2 py-0.5 rounded border border-border hover:border-destructive/30 transition-colors disabled:opacity-50"
                  >
                    {cancellingId === job.id ? (
                      <span className="flex items-center gap-1">
                        <Loader2 size={11} className="animate-spin" />
                        Membatalkan...
                      </span>
                    ) : (
                      "Batalkan"
                    )}
                  </button>
                </div>

                {/* Progress bar */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="truncate pr-2">{job.current_step}</span>
                    <span className="font-semibold text-primary tabular-nums shrink-0">
                      {job.progress}%
                    </span>
                  </div>
                  <div className="w-full bg-secondary h-2 rounded-full overflow-hidden">
                    <div
                      className="bg-primary h-full rounded-full transition-all duration-300 ease-out"
                      style={{ width: `${Math.max(4, Math.min(100, job.progress))}%` }}
                    />
                  </div>
                </div>

                {job.items_total > 0 && (
                  <div className="text-[10px] text-muted-foreground tabular-nums">
                    Item diproses: {job.items_processed} dari {job.items_total}
                  </div>
                )}
              </div>
            ))
          )
        ) : recentJobs.length === 0 ? (
          <div className="py-10 text-center text-xs text-muted-foreground space-y-1">
            <Clock size={24} className="mx-auto text-muted-foreground/40 mb-2" />
            <p className="font-medium text-foreground">Belum ada riwayat pekerjaan</p>
            <p>Pekerjaan yang telah selesai atau dibatalkan akan muncul di sini.</p>
          </div>
        ) : (
          recentJobs.map((job) => (
            <div key={job.id} className="pt-3 first:pt-0 space-y-2">
              <div className="flex items-start justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {getJobIcon(job.job_type)}
                  <span className="text-xs font-medium text-foreground truncate">
                    {job.title}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {getStatusBadge(job.status)}
                  <button
                    type="button"
                    onClick={() => dismissJob(job.id)}
                    title="Hapus dari daftar riwayat"
                    className="p-1 text-muted-foreground hover:text-foreground rounded hover:bg-secondary transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>

              {job.error_message && (
                <p className="text-[11px] text-destructive bg-destructive/10 p-2 rounded-md">
                  {job.error_message}
                </p>
              )}

              <div className="flex items-center justify-between text-[11px] text-muted-foreground pt-0.5">
                <span>{job.current_step}</span>
                {job.status === "completed" && job.result_payload && (
                  <button
                    type="button"
                    onClick={() => handleOpenResult(job)}
                    className="flex items-center gap-1 font-medium text-primary hover:underline hover:text-primary/80 transition-colors"
                  >
                    Buka Hasil
                    <ArrowRight size={12} />
                  </button>
                )}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
