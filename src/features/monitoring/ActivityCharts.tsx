import React from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Play, Pause, FolderCheck, CheckCircle2, AlertCircle } from "lucide-react";
import type { ActivityChartPoint, DistributionItem, WatcherItem } from "@/types";

interface ActivityChartsProps {
  chartPoints: ActivityChartPoint[];
  distribution: DistributionItem[];
  watchers?: WatcherItem[];
  timeRange: string;
  onTimeRangeChange: (range: string) => void;
  onCategoryClick?: (category: string) => void;
  onPauseWatcher?: (folderId: string) => void;
  onResumeWatcher?: (folderId: string) => void;
  onStartWatcher?: (folderId: string) => void;
  onManageWatchers?: () => void;
}

const EVENT_COLORS: Record<string, string> = {
  created: "#10b981",
  modified: "#3b82f6",
  deleted: "#ef4444",
  moved: "#8b5cf6",
};

export const ActivityCharts: React.FC<ActivityChartsProps> = ({
  chartPoints,
  distribution,
  watchers = [],
  timeRange,
  onTimeRangeChange,
  onCategoryClick,
  onPauseWatcher,
  onResumeWatcher,
  onStartWatcher,
  onManageWatchers,
}) => {
  const totalEvents = distribution.reduce((acc, curr) => acc + curr.count, 0);

  const getWatcherStatusPill = (status: string) => {
    switch (status) {
      case "watching":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={10} />
            Active
          </span>
        );
      case "paused":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Pause size={10} />
            Paused
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground border border-border">
            <AlertCircle size={10} />
            Idle
          </span>
        );
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-stretch">
      {/* 1. Kolom 1 (5 cols): Stacked Bar Chart: Change Activity */}
      <div className="lg:col-span-5 p-4 rounded-lg border border-border bg-card flex flex-col justify-between shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-2">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Change Activity (Last 24 Hours)
            </h4>
            <p className="text-[11px] text-muted-foreground">
              Event frequency distribution over time
            </p>
          </div>

          {/* Time Range Switcher */}
          <div className="flex items-center gap-1 bg-muted p-0.5 rounded-md text-[10px]">
            {[
              { id: "last_hour", label: "1h" },
              { id: "last_24h", label: "24h" },
              { id: "last_7d", label: "7d" },
              { id: "last_30d", label: "30d" },
            ].map((btn) => (
              <button
                key={btn.id}
                type="button"
                onClick={() => onTimeRangeChange(btn.id)}
                className={`px-1.5 py-0.5 rounded transition-colors ${
                  timeRange === btn.id
                    ? "bg-card text-foreground font-semibold shadow-xs"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {btn.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-44 w-full pt-1">
          {chartPoints.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              No activity records in this time range
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartPoints} margin={{ top: 5, right: 10, left: -25, bottom: 0 }}>
                <XAxis dataKey="timestamp" tick={{ fontSize: 9 }} stroke="#888888" />
                <YAxis tick={{ fontSize: 9 }} stroke="#888888" allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    borderColor: "hsl(var(--border))",
                    borderRadius: "0.5rem",
                    fontSize: "11px",
                  }}
                />
                <Legend wrapperStyle={{ fontSize: "10px", paddingTop: "4px" }} />
                <Bar dataKey="created" name="Created" stackId="a" fill="#10b981" radius={[0, 0, 0, 0]} />
                <Bar dataKey="modified" name="Modified" stackId="a" fill="#3b82f6" radius={[0, 0, 0, 0]} />
                <Bar dataKey="deleted" name="Deleted" stackId="a" fill="#ef4444" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 2. Kolom 2 (3 cols): Donut Chart: Event Distribution */}
      <div className="lg:col-span-3 p-4 rounded-lg border border-border bg-card flex flex-col justify-between shadow-xs">
        <div>
          <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Change Distribution
          </h4>
          <p className="text-[11px] text-muted-foreground">
            24h breakdown by category
          </p>
        </div>

        <div className="h-32 w-full relative my-auto">
          {totalEvents === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-muted-foreground">
              No events recorded (24h)
            </div>
          ) : (
            <>
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={distribution}
                    dataKey="count"
                    nameKey="event_type"
                    cx="50%"
                    cy="50%"
                    innerRadius={36}
                    outerRadius={52}
                    paddingAngle={3}
                  >
                    {distribution.map((entry) => (
                      <Cell
                        key={entry.event_type}
                        fill={EVENT_COLORS[entry.event_type] || "#888888"}
                        className="cursor-pointer outline-none"
                        onClick={() => onCategoryClick && onCategoryClick(entry.event_type)}
                      />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      borderColor: "hsl(var(--border))",
                      borderRadius: "0.5rem",
                      fontSize: "11px",
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
                <span className="text-base font-bold">{totalEvents}</span>
                <span className="text-[9px] text-muted-foreground">Events</span>
              </div>
            </>
          )}
        </div>

        {/* Legend List */}
        <div className="grid grid-cols-2 gap-1.5 pt-2 border-t border-border text-xs">
          {distribution.map((d) => (
            <button
              key={d.event_type}
              type="button"
              onClick={() => onCategoryClick && onCategoryClick(d.event_type)}
              className="flex items-center justify-between p-1 rounded hover:bg-muted/50 text-left cursor-pointer"
            >
              <div className="flex items-center gap-1.5 truncate">
                <span
                  className="w-2 h-2 rounded-full shrink-0"
                  style={{ backgroundColor: EVENT_COLORS[d.event_type] || "#888888" }}
                />
                <span className="capitalize truncate text-[10px] text-muted-foreground">
                  {d.event_type}
                </span>
              </div>
              <span className="font-semibold text-[10px] ml-1">{d.count}</span>
            </button>
          ))}
        </div>
      </div>

      {/* 3. Kolom 3 (4 cols): Monitored Folders Watcher Status List */}
      <div className="lg:col-span-4 p-4 rounded-lg border border-border bg-card flex flex-col justify-between shadow-xs">
        <div className="flex items-center justify-between mb-2">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Monitored Folders
            </h4>
            <p className="text-[11px] text-muted-foreground">
              Real-time filesystem watchers
            </p>
          </div>
          {onManageWatchers && (
            <button
              type="button"
              onClick={onManageWatchers}
              className="text-[11px] text-primary hover:underline font-medium"
            >
              Manage →
            </button>
          )}
        </div>

        <div className="space-y-2 overflow-y-auto max-h-[170px] pr-1">
          {watchers.length === 0 ? (
            <div className="py-8 text-center text-xs text-muted-foreground">
              <FolderCheck size={28} className="mx-auto mb-1.5 opacity-40" />
              <span>No active watchers registered</span>
            </div>
          ) : (
            watchers.map((w) => (
              <div
                key={w.folder_id}
                className="p-2 rounded-md border border-border bg-muted/20 flex items-center justify-between gap-2"
              >
                <div className="min-w-0 flex-1">
                  <span className="font-semibold text-xs text-foreground block truncate" title={w.folder_name}>
                    {w.folder_name}
                  </span>
                  <span className="text-[10px] text-muted-foreground font-mono block truncate" title={w.root_path}>
                    {w.root_path}
                  </span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0">
                  {getWatcherStatusPill(w.status)}
                  {w.status === "watching" && onPauseWatcher && (
                    <button
                      type="button"
                      onClick={() => onPauseWatcher(w.folder_id)}
                      title="Pause watcher"
                      className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
                    >
                      <Pause size={12} />
                    </button>
                  )}
                  {w.status === "paused" && onResumeWatcher && (
                    <button
                      type="button"
                      onClick={() => onResumeWatcher(w.folder_id)}
                      title="Resume watcher"
                      className="p-1 rounded text-emerald-600 hover:bg-emerald-500/10"
                    >
                      <Play size={12} />
                    </button>
                  )}
                  {w.status === "stopped" && onStartWatcher && (
                    <button
                      type="button"
                      onClick={() => onStartWatcher(w.folder_id)}
                      title="Start watcher"
                      className="p-1 rounded text-primary hover:bg-primary/10"
                    >
                      <Play size={12} />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        <div className="pt-2 border-t border-border flex items-center justify-between text-[11px] text-muted-foreground">
          <span>Active: {watchers.filter((w) => w.status === "watching").length}</span>
          <span>Total: {watchers.length} Watchers</span>
        </div>
      </div>
    </div>
  );
};
