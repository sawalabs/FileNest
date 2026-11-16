import React from "react";
import {
  ChevronUp,
  ChevronDown,
  X,
  HardDrive,
  FilePenLine,
  FolderTree,
  ScanText,
  Layers,
} from "lucide-react";
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext";
import type { BackgroundJobItem, BackgroundJobType } from "@/types";

const getJobIcon = (type: BackgroundJobType) => {
  switch (type) {
    case "storage_analysis":
      return <HardDrive size={15} className="text-primary shrink-0" />;
    case "smart_rename_plan":
      return <FilePenLine size={15} className="text-blue-500 shrink-0" />;
    case "batch_ocr":
      return <ScanText size={15} className="text-amber-500 shrink-0" />;
    case "organization_plan":
      return <FolderTree size={15} className="text-emerald-500 shrink-0" />;
    default:
      return <Layers size={15} className="text-primary shrink-0" />;
  }
};

export const FloatingBottomProgressBar: React.FC = () => {
  const { activeJobs, isDrawerOpen, toggleDrawer, cancelJob } = useBackgroundTasks();

  if (activeJobs.length === 0) {
    return null;
  }

  // Primary active job to highlight on the bar
  const primaryJob: BackgroundJobItem = activeJobs[0];
  const otherCount = activeJobs.length - 1;

  const handleCancel = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (primaryJob) {
      cancelJob(primaryJob.id);
    }
  };

  return (
    <div
      role="region"
      aria-label="Proses Latar Belakang"
      className="fixed bottom-3 right-6 z-40 max-w-xl w-[92vw] sm:w-[480px] bg-card/95 backdrop-blur-md border border-border shadow-2xl rounded-xl overflow-hidden transition-all duration-300 ease-in-out hover:shadow-primary/5"
    >
      {/* Top micro progress line */}
      <div className="w-full bg-secondary h-1.5 overflow-hidden">
        <div
          className="bg-primary h-full transition-all duration-300 ease-out"
          style={{ width: `${Math.max(5, Math.min(100, primaryJob.progress))}%` }}
        />
      </div>

      {/* Main bar content */}
      <div
        onClick={toggleDrawer}
        className="px-3.5 py-2.5 flex items-center justify-between gap-3 cursor-pointer select-none hover:bg-accent/40 transition-colors"
      >
        <div className="flex items-center gap-2.5 min-w-0 flex-1">
          <div className="relative flex items-center justify-center w-6 h-6 rounded-md bg-secondary shrink-0">
            {getJobIcon(primaryJob.job_type)}
          </div>

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium text-xs text-foreground truncate">
                {primaryJob.title}
              </span>
              <span className="text-[11px] font-semibold text-primary shrink-0 tabular-nums">
                {primaryJob.progress}%
              </span>
              {otherCount > 0 && (
                <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-secondary text-secondary-foreground font-medium shrink-0">
                  +{otherCount} lainnya
                </span>
              )}
            </div>

            <p className="text-[11px] text-muted-foreground truncate leading-tight mt-0.5">
              {primaryJob.current_step || "Sedang memproses..."}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            title="Batalkan proses ini"
            onClick={handleCancel}
            className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
          >
            <X size={15} />
          </button>

          <button
            type="button"
            title={isDrawerOpen ? "Tutup panel detail" : "Buka panel detail proses"}
            onClick={(e) => {
              e.stopPropagation();
              toggleDrawer();
            }}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
          >
            {isDrawerOpen ? <ChevronDown size={16} /> : <ChevronUp size={16} />}
          </button>
        </div>
      </div>
    </div>
  );
};
