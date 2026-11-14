import React from "react";
import {
  FileText,
  FolderPlus,
  ArrowRightLeft,
  HardDrive,
  AlertTriangle,
} from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { OrganizationPlanResult } from "@/types";

interface OrganizationSummaryCardsProps {
  data: OrganizationPlanResult;
}

export const OrganizationSummaryCards: React.FC<OrganizationSummaryCardsProps> = ({
  data,
}) => {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 gap-3">
      {/* 1. Files Analyzed */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">Analyzed</span>
          <FileText size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.files_analyzed_count)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">Files inspected</p>
      </div>

      {/* 2. Suggested Folders */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">New Folders</span>
          <FolderPlus size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.folders_to_create_count)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">Directories to create</p>
      </div>

      {/* 3. Files to Move */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">To Relocate</span>
          <ArrowRightLeft size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.files_to_move_count)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">Files to organize</p>
      </div>

      {/* 4. Total Size */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">Total Size</span>
          <HardDrive size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatBytes(data.total_size_bytes)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">Involved data</p>
      </div>

      {/* 5. Potential Conflicts */}
      <div
        className={`p-3.5 rounded-xl border shadow-xs space-y-1 col-span-2 sm:col-span-1 ${
          data.conflicts_count > 0
            ? "border-destructive/40 bg-destructive/5 text-destructive"
            : "border-border bg-card text-muted-foreground"
        }`}
      >
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-semibold uppercase tracking-wider">Conflicts</span>
          <AlertTriangle
            size={15}
            className={data.conflicts_count > 0 ? "text-destructive" : "text-muted-foreground"}
          />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.conflicts_count)}
        </div>
        <p className="text-[11px] truncate">
          {data.conflicts_count > 0 ? "Collision detected" : "Zero conflicts"}
        </p>
      </div>
    </div>
  );
};

