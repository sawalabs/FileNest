import React from "react";
import {
  FileText,
  FilePenLine,
  CheckCircle,
  AlertTriangle,
  HardDrive,
} from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { SmartRenamePlanResult } from "@/types";

interface SmartRenameSummaryCardsProps {
  data: SmartRenamePlanResult;
}

export const SmartRenameSummaryCards: React.FC<SmartRenameSummaryCardsProps> = ({
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
        <p className="text-[11px] text-muted-foreground truncate">Files scanned</p>
      </div>

      {/* 2. To Rename */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">To Rename</span>
          <FilePenLine size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.files_to_rename_count)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">New names generated</p>
      </div>

      {/* 3. Unchanged */}
      <div className="p-3.5 rounded-xl border border-border bg-card shadow-xs space-y-1">
        <div className="flex items-center justify-between text-muted-foreground">
          <span className="text-[10px] font-semibold uppercase tracking-wider">Compliant</span>
          <CheckCircle size={15} className="text-muted-foreground" />
        </div>
        <div className="text-xl font-bold text-foreground">
          {formatNumber(data.files_unchanged_count)}
        </div>
        <p className="text-[11px] text-muted-foreground truncate">Already matching</p>
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
        <p className="text-[11px] text-muted-foreground truncate">Involved files</p>
      </div>

      {/* 5. Conflicts */}
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

