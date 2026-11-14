import React from "react";
import {
  FolderCheck,
  Activity,
  FilePlus,
  FilePenLine,
  Trash2,
  HardDrive,
} from "lucide-react";
import type { MonitoringSummaryStats } from "@/types";
import { cn } from "@/lib/utils";

interface MonitoringSummaryCardsProps {
  stats: MonitoringSummaryStats;
  activeFilter?: string;
  onFilterClick?: (filterKey: string) => void;
}

export const MonitoringSummaryCards: React.FC<MonitoringSummaryCardsProps> = ({
  stats,
  activeFilter,
  onFilterClick,
}) => {
  const cards = [
    {
      key: "all",
      title: "Monitored Folders",
      count: `${stats.active_watchers_count} / ${stats.monitored_folders_count}`,
      description: "Active watchers",
      icon: FolderCheck,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
      borderColor: "border-blue-500/20",
    },
    {
      key: "24h",
      title: "Total Changes (24h)",
      count: stats.total_events_24h,
      description: "Detected events",
      icon: Activity,
      color: "text-foreground",
      bgColor: "bg-secondary",
      borderColor: "border-border",
    },
    {
      key: "created",
      title: "Files Created",
      count: stats.files_created_count,
      description: "Added to folders",
      icon: FilePlus,
      color: "text-emerald-500",
      bgColor: "bg-emerald-500/10",
      borderColor: "border-emerald-500/20",
    },
    {
      key: "modified",
      title: "Files Modified",
      count: stats.files_modified_count,
      description: "Content updates",
      icon: FilePenLine,
      color: "text-amber-500",
      bgColor: "bg-amber-500/10",
      borderColor: "border-amber-500/20",
    },
    {
      key: "deleted",
      title: "Files Deleted",
      count: stats.files_deleted_count,
      description: "Removed items",
      icon: Trash2,
      color: "text-rose-500",
      bgColor: "bg-rose-500/10",
      borderColor: "border-rose-500/20",
    },
    {
      key: "size",
      title: "Total Change Size",
      count:
        stats.total_change_size_bytes > 0
          ? `${(stats.total_change_size_bytes / (1024 * 1024)).toFixed(1)} MB`
          : "—",
      description: "Monitored event payload",
      icon: HardDrive,
      color: "text-foreground",
      bgColor: "bg-secondary",
      borderColor: "border-border",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((card) => {
        const Icon = card.icon;
        const isSelected = activeFilter === card.key;
        return (
          <button
            key={card.key}
            type="button"
            onClick={() => onFilterClick && onFilterClick(card.key)}
            className={cn(
              "text-left p-3.5 rounded-lg border bg-card transition-all cursor-pointer relative",
              isSelected
                ? "ring-2 ring-primary border-transparent shadow-xs"
                : "border-border hover:border-primary/50 hover:bg-muted/30"
            )}
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground truncate">{card.title}</span>
              <div className={cn("p-1.5 rounded-md shrink-0", card.bgColor, card.color)}>
                <Icon size={16} />
              </div>
            </div>
            <div className="mt-2 flex items-baseline gap-1.5">
              <span className="text-xl font-bold tracking-tight">{card.count}</span>
            </div>
            <span className="text-[11px] text-muted-foreground block truncate mt-0.5">
              {card.description}
            </span>
          </button>
        );
      })}
    </div>
  );
};

