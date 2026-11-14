import React from "react";
import {
  Clock,
  FolderInput,
  FilePenLine,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ReviewSummaryCardsProps {
  pendingCount: number;
  moveCount: number;
  renameCount: number;
  deleteCount: number;
  conflictCount: number;
  activeFilter?: string;
  onFilterClick?: (filterKey: string) => void;
}

export const ReviewSummaryCards: React.FC<ReviewSummaryCardsProps> = ({
  pendingCount,
  moveCount,
  renameCount,
  deleteCount,
  conflictCount,
  activeFilter,
  onFilterClick,
}) => {
  const cards = [
    {
      key: "pending",
      title: "Pending Changes",
      count: pendingCount,
      description: "Awaiting approval",
      icon: Clock,
      color: "text-amber-500",
      bgColor: "bg-amber-500/10",
      borderColor: "border-amber-500/20",
    },
    {
      key: "move",
      title: "Move Operations",
      count: moveCount,
      description: "Relocating files",
      icon: FolderInput,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
      borderColor: "border-blue-500/20",
    },
    {
      key: "rename",
      title: "Rename Operations",
      count: renameCount,
      description: "Renaming files",
      icon: FilePenLine,
      color: "text-indigo-500",
      bgColor: "bg-indigo-500/10",
      borderColor: "border-indigo-500/20",
    },
    {
      key: "delete",
      title: "Delete Operations",
      count: deleteCount,
      description: "Recycle bin",
      icon: Trash2,
      color: "text-rose-500",
      bgColor: "bg-rose-500/10",
      borderColor: "border-rose-500/20",
    },
    {
      key: "conflict",
      title: "Potential Conflicts",
      count: conflictCount,
      description: "Validation blockers",
      icon: AlertTriangle,
      color: conflictCount > 0 ? "text-rose-600 dark:text-rose-400" : "text-emerald-500",
      bgColor: conflictCount > 0 ? "bg-rose-500/10" : "bg-emerald-500/10",
      borderColor: conflictCount > 0 ? "border-rose-500/30" : "border-emerald-500/20",
    },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2.5">
      {cards.map((card) => {
        const Icon = card.icon;
        const isSelected = activeFilter === card.key;
        return (
          <button
            key={card.key}
            type="button"
            onClick={() => onFilterClick && onFilterClick(card.key)}
            className={cn(
              "text-left p-2.5 sm:p-3 rounded-lg border bg-card transition-all cursor-pointer relative",
              isSelected
                ? "ring-2 ring-primary border-transparent shadow-xs"
                : "border-border hover:border-primary/50 hover:bg-muted/30"
            )}
          >
            <div className="flex items-center justify-between gap-1">
              <span className="text-[11px] sm:text-xs font-medium text-muted-foreground truncate">{card.title}</span>
              <div className={cn("p-1 sm:p-1.5 rounded-md shrink-0", card.bgColor, card.color)}>
                <Icon size={14} />
              </div>
            </div>
            <div className="mt-1 sm:mt-1.5 flex items-baseline gap-1.5">
              <span className="text-xl sm:text-2xl font-bold tracking-tight">{card.count}</span>
              <span className="text-[10px] sm:text-[11px] text-muted-foreground truncate">{card.description}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
};

