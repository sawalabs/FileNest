import React from "react";
import { Folder, FileText, HardDrive, CheckCircle2 } from "lucide-react";
import type { DashboardSummaryCardsData, NavItem } from "@/types";
import { formatBytes } from "@/lib/utils";

interface DashboardSummaryCardsProps {
  cards: DashboardSummaryCardsData;
  onNavigate: (tab: NavItem) => void;
}

export const DashboardSummaryCards: React.FC<DashboardSummaryCardsProps> = ({
  cards,
  onNavigate,
}) => {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Managed Folders Card */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onNavigate("managed-folders")}
        onKeyDown={(e) => e.key === "Enter" && onNavigate("managed-folders")}
        className="group relative p-4 rounded-xl border border-border bg-card shadow-xs hover:border-amber-500/50 hover:shadow-sm transition-all cursor-pointer select-none flex items-center gap-3.5"
      >
        <div className="p-3 rounded-xl bg-amber-500/10 text-amber-500 border border-amber-500/20 shrink-0 group-hover:scale-105 transition-transform">
          <Folder size={24} className="fill-amber-500/20" />
        </div>
        <div className="min-w-0">
          <div className="text-2xl font-bold tracking-tight text-foreground leading-tight">
            {cards.managed_folders_count}
          </div>
          <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate">
            Folder Dikelola
          </p>
        </div>
      </div>

      {/* 2. Total Files Card */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onNavigate("files")}
        onKeyDown={(e) => e.key === "Enter" && onNavigate("files")}
        className="group relative p-4 rounded-xl border border-border bg-card shadow-xs hover:border-blue-500/50 hover:shadow-sm transition-all cursor-pointer select-none flex items-center gap-3.5"
      >
        <div className="p-3 rounded-xl bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20 shrink-0 group-hover:scale-105 transition-transform">
          <FileText size={24} />
        </div>
        <div className="min-w-0">
          <div className="text-2xl font-bold tracking-tight text-foreground leading-tight">
            {cards.total_files_count.toLocaleString()}
          </div>
          <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate">
            Total File
          </p>
        </div>
      </div>

      {/* 3. Total Storage Card */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onNavigate("storage")}
        onKeyDown={(e) => e.key === "Enter" && onNavigate("storage")}
        className="group relative p-4 rounded-xl border border-border bg-card shadow-xs hover:border-primary/50 hover:shadow-sm transition-all cursor-pointer select-none flex items-center gap-3.5"
      >
        <div className="p-3 rounded-xl bg-primary/10 text-primary border border-primary/20 shrink-0 group-hover:scale-105 transition-transform">
          <HardDrive size={24} />
        </div>
        <div className="min-w-0">
          <div className="text-2xl font-bold tracking-tight text-foreground leading-tight">
            {formatBytes(cards.total_size_bytes)}
          </div>
          <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate">
            Total Ukuran
          </p>
        </div>
      </div>

      {/* 4. Pending Changes Card */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => onNavigate("review-changes")}
        onKeyDown={(e) => e.key === "Enter" && onNavigate("review-changes")}
        className="group relative p-4 rounded-xl border border-border bg-card shadow-xs hover:border-emerald-500/50 hover:shadow-sm transition-all cursor-pointer select-none flex items-center gap-3.5"
      >
        <div className="p-3 rounded-xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 shrink-0 group-hover:scale-105 transition-transform">
          <CheckCircle2 size={24} />
        </div>
        <div className="min-w-0">
          <div className="text-2xl font-bold tracking-tight text-foreground leading-tight flex items-center gap-2">
            <span>{cards.pending_changes_count}</span>
            {cards.pending_changes_count > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] font-semibold uppercase rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300">
                Tertunda
              </span>
            )}
          </div>
          <p className="text-xs text-muted-foreground font-medium mt-0.5 truncate">
            Perubahan Tertunda
          </p>
        </div>
      </div>
    </div>
  );
};