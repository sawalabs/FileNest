import React from "react";
import {
  Activity,
  CheckCircle2,
  Clock,
  AlertTriangle,
  RotateCw,
  Ban,
  PauseCircle,
} from "lucide-react";
import type { DashboardJobItemData } from "@/types";

interface JobStatusMonitorProps {
  jobs: DashboardJobItemData[];
  onRefreshJobs: () => void;
}

export const JobStatusMonitor: React.FC<JobStatusMonitorProps> = ({
  jobs,
  onRefreshJobs,
}) => {
  const isEmpty = jobs.length === 0;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "running":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-blue-500/15 text-blue-600 dark:text-blue-400">
            <RotateCw size={10} className="animate-spin" />
            <span>Berjalan</span>
          </span>
        );
      case "queued":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-amber-500/15 text-amber-600 dark:text-amber-400">
            <Clock size={10} />
            <span>Antrian</span>
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 size={10} />
            <span>Selesai</span>
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-destructive/15 text-destructive">
            <AlertTriangle size={10} />
            <span>Gagal</span>
          </span>
        );
      case "paused":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
            <PauseCircle size={10} />
            <span>Jeda</span>
          </span>
        );
      case "cancelled":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
            <Ban size={10} />
            <span>Dibatalkan</span>
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
            {status}
          </span>
        );
    }
  };

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Activity size={16} className="text-primary" />
            Status Pekerjaan Sistem
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Pekerjaan pemindaian dan transaksi background
          </p>
        </div>
        <button
          type="button"
          onClick={onRefreshJobs}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          title="Segarkan Pekerjaan"
        >
          <RotateCw size={13} />
        </button>
      </div>

      {isEmpty ? (
        <div className="py-10 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
            <CheckCircle2 size={18} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Tidak ada pekerjaan aktif</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Seluruh antrian pemindaian dan eksekusi selesai diproses.
          </p>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {jobs.map((job) => (
            <div
              key={job.id}
              className="p-3 rounded-lg border border-border/60 bg-background/50 text-xs space-y-2"
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <h4 className="font-semibold text-foreground truncate">
                    {job.job_name}
                  </h4>
                  {job.folder_name && (
                    <span className="text-[11px] text-muted-foreground truncate block">
                      Folder: {job.folder_name}
                    </span>
                  )}
                </div>
                <div className="flex-shrink-0">
                  {getStatusBadge(job.status)}
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-300 ${
                    job.status === "failed"
                      ? "bg-destructive"
                      : job.status === "completed"
                      ? "bg-emerald-500"
                      : "bg-primary animate-pulse"
                  }`}
                  style={{ width: `${Math.max(2, job.progress_percent)}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[10px] text-muted-foreground">
                <span>{job.progress_percent}% Selesai</span>
                {job.error_message ? (
                  <span className="text-destructive font-medium truncate max-w-[200px]" title={job.error_message}>
                    {job.error_message}
                  </span>
                ) : (
                  <span>Tipe: {job.job_type}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
