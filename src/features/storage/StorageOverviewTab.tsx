import React, { useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
} from "recharts";
import {
  Folder,
  TrendingUp,
  Sparkles,
  PieChart as PieChartIcon,
  ChevronRight,
  FolderTree,
} from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { StorageAnalysisResult } from "@/types";
import type { StorageTab } from "./StorageSummaryCards";

interface StorageOverviewTabProps {
  data: StorageAnalysisResult;
  onSelectTab: (tab: StorageTab, categoryFilter?: string) => void;
  onOpenFolderInFiles?: (folderId: string, relativePath: string) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  document: "#3b82f6",
  image: "#a855f7",
  video: "#f43f5e",
  audio: "#f59e0b",
  archive: "#ea580c",
  code: "#6366f1",
  other: "#94a3b8",
};

export const StorageOverviewTab: React.FC<StorageOverviewTabProps> = ({
  data,
  onSelectTab,
  onOpenFolderInFiles,
}) => {
  const [trendRange, setTrendRange] = useState<"7d" | "30d" | "90d" | "all">("7d");

  // Prepare chart data for Storage Distribution
  const pieData = data.category_distribution.map((cat) => ({
    name: cat.category.charAt(0).toUpperCase() + cat.category.slice(1),
    categoryKey: cat.category,
    value: cat.total_size_bytes,
    filesCount: cat.files_count,
    percentage: cat.percentage,
    color: CATEGORY_COLORS[cat.category.toLowerCase()] || "#94a3b8",
  }));

  // Filter trend points based on trendRange
  const trendPoints = [...(data.trend_points || [])].sort(
    (a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()
  );

  const filteredTrendData = trendPoints.slice(
    trendRange === "7d"
      ? -7
      : trendRange === "30d"
      ? -30
      : trendRange === "90d"
      ? -90
      : 0
  );

  return (
    <div className="space-y-6">
      {/* Top Grid: Storage Distribution (Donut) & Largest Folders */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Storage Distribution by File Type */}
        <div className="lg:col-span-6 p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div className="flex items-center gap-2">
              <PieChartIcon size={18} className="text-primary" />
              <h3 className="font-semibold text-sm">Storage Distribution by File Type</h3>
            </div>
            <span className="text-xs text-muted-foreground">
              {data.category_distribution.length} categories
            </span>
          </div>

          <div className="mt-4 flex flex-col sm:flex-row items-center gap-6">
            {/* Donut Chart with Center Label */}
            <div className="relative w-48 h-48 shrink-0 flex items-center justify-center">
              {pieData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={80}
                      paddingAngle={3}
                      dataKey="value"
                    >
                      {pieData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.color}
                          className="hover:opacity-80 cursor-pointer transition-opacity"
                          onClick={() => onSelectTab("file_types", entry.categoryKey)}
                        />
                      ))}
                    </Pie>
                    <RechartsTooltip
                      formatter={(val: any) => [formatBytes(Number(val) || 0), "Size"]}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="w-full h-full rounded-full border-4 border-dashed border-muted flex items-center justify-center text-xs text-muted-foreground">
                  No data
                </div>
              )}
              {/* Center text overlay */}
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
                <span className="text-[10px] uppercase font-semibold text-muted-foreground tracking-wider">
                  Total
                </span>
                <span className="text-sm font-bold text-foreground">
                  {formatBytes(data.total_storage_bytes)}
                </span>
              </div>
            </div>

            {/* Category breakdown table */}
            <div className="flex-1 w-full space-y-1.5 overflow-y-auto max-h-56 pr-1">
              {pieData.length === 0 ? (
                <p className="text-xs text-muted-foreground italic py-4 text-center">
                  No categorized files indexed yet.
                </p>
              ) : (
                pieData.map((cat) => (
                  <button
                    key={cat.categoryKey}
                    onClick={() => onSelectTab("file_types", cat.categoryKey)}
                    className="w-full flex items-center justify-between text-xs py-1.5 px-2 rounded-md hover:bg-muted/80 transition-colors text-left group"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span
                        className="w-2.5 h-2.5 rounded-full shrink-0"
                        style={{ backgroundColor: cat.color }}
                      />
                      <span className="font-medium text-foreground truncate group-hover:text-primary">
                        {cat.name}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        ({formatNumber(cat.filesCount)})
                      </span>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="font-medium text-foreground">
                        {formatBytes(cat.value)}
                      </span>
                      <span className="text-muted-foreground w-11 text-right">
                        {cat.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </button>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Largest Folders */}
        <div className="lg:col-span-6 p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div className="flex items-center gap-2">
              <FolderTree size={18} className="text-primary" />
              <h3 className="font-semibold text-sm">Largest Folders</h3>
            </div>
            <button
              onClick={() => onSelectTab("overview")}
              className="text-xs text-primary hover:underline font-medium"
            >
              Sorted by size
            </button>
          </div>

          <div className="mt-4 flex-1 space-y-3 overflow-y-auto max-h-56">
            {data.largest_folders.length === 0 ? (
              <div className="py-8 text-center text-xs text-muted-foreground">
                No subdirectories found in current scope.
              </div>
            ) : (
              data.largest_folders.slice(0, 5).map((folder) => (
                <div
                  key={folder.relative_path}
                  onClick={() => {
                    const targetFolderId = folder.managed_folder_id || data.managed_folder_id;
                    if (onOpenFolderInFiles && targetFolderId) {
                      onOpenFolderInFiles(targetFolderId, folder.relative_path);
                    }
                  }}
                  className="p-2.5 rounded-lg border border-border/60 bg-muted/20 hover:bg-muted/50 cursor-pointer transition-colors space-y-1.5"
                >
                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <Folder size={15} className="text-amber-500 fill-amber-500/20 shrink-0" />
                      <span className="font-semibold text-foreground truncate" title={folder.relative_path}>
                        {folder.name}
                      </span>
                      <span className="text-[11px] text-muted-foreground">
                        ({formatNumber(folder.files_count)} files)
                      </span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="font-bold text-foreground">
                        {formatBytes(folder.total_size_bytes)}
                      </span>
                      <span className="text-[11px] text-muted-foreground font-mono">
                        {folder.percentage.toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="w-full bg-muted rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-primary h-1.5 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(folder.percentage, 100)}%` }}
                    />
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Recommendations Cards */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex items-center gap-2 pb-3 border-b border-border/60">
          <Sparkles size={18} className="text-amber-500" />
          <h3 className="font-semibold text-sm">Storage Optimization Recommendations</h3>
          <span className="text-xs bg-amber-500/10 text-amber-600 dark:text-amber-400 px-2 py-0.5 rounded-full font-medium ml-auto">
            {data.recommendations.length} insights
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {data.recommendations.map((rec) => (
            <div
              key={rec.id}
              className="p-4 rounded-lg border border-border bg-muted/30 hover:border-primary/40 transition-all flex flex-col justify-between space-y-3"
            >
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-sm text-foreground">{rec.title}</h4>
                  {rec.impact_bytes > 0 && (
                    <span className="text-xs font-semibold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                      {formatBytes(rec.impact_bytes)}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {rec.description}
                </p>
              </div>

              <button
                onClick={() => onSelectTab(rec.target_tab as StorageTab)}
                className="inline-flex items-center justify-between w-full px-3 py-1.5 text-xs font-medium rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors group"
              >
                <span>View Details</span>
                <ChevronRight size={14} className="text-muted-foreground group-hover:translate-x-0.5 transition-transform" />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Storage Usage Trend */}
      <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/60">
          <div className="flex items-center gap-2">
            <TrendingUp size={18} className="text-primary" />
            <h3 className="font-semibold text-sm">Storage Usage Trend</h3>
            <span className="text-xs text-muted-foreground">Historical snapshots</span>
          </div>
          <div className="flex items-center gap-1 bg-muted p-0.5 rounded-lg text-xs">
            {(["7d", "30d", "90d", "all"] as const).map((range) => (
              <button
                key={range}
                onClick={() => setTrendRange(range)}
                className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                  trendRange === range
                    ? "bg-card text-foreground shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {range === "7d"
                  ? "Last 7 Days"
                  : range === "30d"
                  ? "Last 30 Days"
                  : range === "90d"
                  ? "Last 90 Days"
                  : "All Time"}
              </button>
            ))}
          </div>
        </div>

        <div className="h-64 w-full">
          {filteredTrendData.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-6 border border-dashed rounded-lg text-muted-foreground">
              <TrendingUp size={28} className="text-muted-foreground/40 mb-2" />
              <p className="text-xs font-medium">No storage history snapshots recorded yet.</p>
              <p className="text-[11px] text-muted-foreground/70 mt-1">
                Subsequent storage analyses will establish an ongoing trend graph over time.
              </p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={filteredTrendData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  stroke="#94a3b8"
                />
                <YAxis
                  tick={{ fontSize: 11 }}
                  tickLine={false}
                  stroke="#94a3b8"
                  tickFormatter={(val) => formatBytes(val, 0)}
                />
                <RechartsTooltip
                  formatter={(val: any) => [formatBytes(Number(val) || 0), "Total Storage"]}
                />
                <Line
                  type="monotone"
                  dataKey="total_size_bytes"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 4, fill: "#2563eb" }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>
    </div>
  );
};
