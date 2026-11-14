import React from "react";
import { HardDrive, FileWarning, Copy, FolderX, ArrowUpRight } from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { StorageAnalysisResult } from "@/types";

export type StorageTab = "overview" | "large_files" | "duplicates" | "file_types" | "empty_folders";

interface StorageSummaryCardsProps {
  data: StorageAnalysisResult | null;
  activeTab: StorageTab;
  onSelectTab: (tab: StorageTab) => void;
}

export const StorageSummaryCards: React.FC<StorageSummaryCardsProps> = ({
  data,
  activeTab,
  onSelectTab,
}) => {
  const totalStorage = data?.total_storage_bytes || 0;
  const totalFiles = data?.total_files_count || 0;

  const largeFilesCount = data?.large_files_count || 0;
  const largeFilesBytes = data?.large_files_bytes || 0;
  const largeFilesPct = data?.large_files_percentage || 0;

  const duplicateGroups = data?.duplicate_groups_count || 0;
  const potentialSavings = data?.potential_savings_bytes || 0;

  const emptyFoldersCount = data?.empty_folders_count || 0;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Total Storage */}
      <div
        onClick={() => onSelectTab("overview")}
        className={`p-4 rounded-xl border bg-card shadow-xs cursor-pointer transition-all ${
          activeTab === "overview"
            ? "ring-2 ring-primary/20 border-primary"
            : "border-border hover:border-border/80 hover:bg-muted/20"
        }`}
      >
        <div className="flex items-center justify-between text-muted-foreground mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider">Total Storage</span>
          <div className="p-2 rounded-lg bg-secondary text-secondary-foreground border border-border/50">
            <HardDrive size={18} />
          </div>
        </div>
        <div className="space-y-1">
          <h3 className="text-2xl font-bold tracking-tight text-foreground">
            {formatBytes(totalStorage)}
          </h3>
          <p className="text-xs text-muted-foreground">
            {formatNumber(totalFiles)} files indexed
          </p>
        </div>
      </div>

      {/* 2. Large Files */}
      <div
        onClick={() => onSelectTab("large_files")}
        className={`p-4 rounded-xl border bg-card shadow-xs cursor-pointer transition-all ${
          activeTab === "large_files"
            ? "ring-2 ring-primary/20 border-primary"
            : "border-border hover:border-border/80 hover:bg-muted/20"
        }`}
      >
        <div className="flex items-center justify-between text-muted-foreground mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider">Large Files</span>
          <div className="p-2 rounded-lg bg-secondary text-secondary-foreground border border-border/50">
            <FileWarning size={18} />
          </div>
        </div>
        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatNumber(largeFilesCount)}
            </h3>
            <span className="text-xs font-medium text-muted-foreground hover:text-foreground flex items-center gap-0.5">
              <span>View</span>
              <ArrowUpRight size={13} />
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {formatBytes(largeFilesBytes)} ({largeFilesPct.toFixed(1)}% of total)
          </p>
        </div>
      </div>

      {/* 3. Duplicate Files */}
      <div
        onClick={() => onSelectTab("duplicates")}
        className={`p-4 rounded-xl border bg-card shadow-xs cursor-pointer transition-all ${
          activeTab === "duplicates"
            ? "ring-2 ring-primary/20 border-primary"
            : "border-border hover:border-border/80 hover:bg-muted/20"
        }`}
      >
        <div className="flex items-center justify-between text-muted-foreground mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider">Duplicate Files</span>
          <div className="p-2 rounded-lg bg-secondary text-secondary-foreground border border-border/50">
            <Copy size={18} />
          </div>
        </div>
        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatNumber(duplicateGroups)} <span className="text-sm font-normal text-muted-foreground">groups</span>
            </h3>
            <span className="text-xs font-medium text-muted-foreground hover:text-foreground flex items-center gap-0.5">
              <span>View</span>
              <ArrowUpRight size={13} />
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {formatBytes(potentialSavings)} potential savings
          </p>
        </div>
      </div>

      {/* 4. Empty Folders */}
      <div
        onClick={() => onSelectTab("empty_folders")}
        className={`p-4 rounded-xl border bg-card shadow-xs cursor-pointer transition-all ${
          activeTab === "empty_folders"
            ? "ring-2 ring-primary/20 border-primary"
            : "border-border hover:border-border/80 hover:bg-muted/20"
        }`}
      >
        <div className="flex items-center justify-between text-muted-foreground mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider">Empty Folders</span>
          <div className="p-2 rounded-lg bg-secondary text-secondary-foreground border border-border/50">
            <FolderX size={18} />
          </div>
        </div>
        <div className="space-y-1">
          <div className="flex items-baseline justify-between">
            <h3 className="text-2xl font-bold tracking-tight text-foreground">
              {formatNumber(emptyFoldersCount)} <span className="text-sm font-normal text-muted-foreground">folders</span>
            </h3>
            <span className="text-xs font-medium text-muted-foreground hover:text-foreground flex items-center gap-0.5">
              <span>View</span>
              <ArrowUpRight size={13} />
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            Zero files and subdirectories
          </p>
        </div>
      </div>
    </div>
  );
};
