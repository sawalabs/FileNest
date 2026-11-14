import React from "react";
import {
  History,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  FileText,
  Clock,
  Sparkles,
  RefreshCw,
} from "lucide-react";
import type { DashboardRecentActivityItemData } from "@/types";

interface RecentActivitiesFeedProps {
  activities: DashboardRecentActivityItemData[];
  onViewAll: () => void;
  onSelectActivity?: (activity: DashboardRecentActivityItemData) => void;
}

export const RecentActivitiesFeed: React.FC<RecentActivitiesFeedProps> = ({
  activities,
  onViewAll,
  onSelectActivity,
}) => {
  const isEmpty = activities.length === 0;

  const getActivityIcon = (action: string, status: string) => {
    if (status === "failed") {
      return <AlertCircle size={14} className="text-destructive flex-shrink-0" />;
    }
    const lower = action.toLowerCase();
    if (lower.includes("scan")) {
      return <RefreshCw size={14} className="text-blue-500 flex-shrink-0" />;
    }
    if (lower.includes("ai") || lower.includes("analys")) {
      return <Sparkles size={14} className="text-primary flex-shrink-0" />;
    }
    if (lower.includes("plan") || lower.includes("organize") || lower.includes("rename")) {
      return <FileText size={14} className="text-amber-500 flex-shrink-0" />;
    }
    return <CheckCircle2 size={14} className="text-emerald-500 flex-shrink-0" />;
  };

  const formatActivityTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <History size={16} className="text-primary" />
            Aktivitas Terbaru
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Log tindakan dan peristiwa sistem terbaru
          </p>
        </div>
        <button
          type="button"
          onClick={onViewAll}
          className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
        >
          <span>Lihat Semua</span>
          <ArrowRight size={12} />
        </button>
      </div>

      {isEmpty ? (
        <div className="py-10 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
            <Clock size={18} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Belum ada aktivitas tercatat</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Aktivitas pemindaian, perubahan, dan audit sistem akan muncul di sini.
          </p>
        </div>
      ) : (
        <div className="mt-3 divide-y divide-border/40">
          {activities.map((act) => (
            <div
              key={act.id}
              role="button"
              tabIndex={0}
              onClick={() => onSelectActivity?.(act)}
              onKeyDown={(e) => e.key === "Enter" && onSelectActivity?.(act)}
              className="py-2.5 px-2 rounded-lg hover:bg-muted/50 transition-colors cursor-pointer group flex items-start justify-between gap-3 text-xs"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <div className="mt-0.5 p-1 rounded-md bg-muted">
                  {getActivityIcon(act.action, act.status)}
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                      {act.action}
                    </span>
                    <span className="text-[10px] uppercase font-bold px-1.5 py-0.2 rounded bg-muted text-muted-foreground">
                      {act.actor_type}
                    </span>
                  </div>
                  {act.details && (
                    <p className="text-[11px] text-muted-foreground truncate max-w-xs xl:max-w-md mt-0.5">
                      {act.details}
                    </p>
                  )}
                  {act.location && (
                    <span className="text-[10px] text-primary/80 block mt-0.5 truncate">
                      {act.location}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-1.5 text-muted-foreground flex-shrink-0 text-[11px]">
                <Clock size={11} />
                <span>{formatActivityTime(act.timestamp)}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
