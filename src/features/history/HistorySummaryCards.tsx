import React from "react";
import { Activity, FileCheck, CheckCircle2, RotateCcw } from "lucide-react";
import type { HistorySummaryStats } from "@/types";

interface HistorySummaryCardsProps {
  stats: HistorySummaryStats;
}

export const HistorySummaryCards: React.FC<HistorySummaryCardsProps> = ({ stats }) => {
  const cards = [
    {
      title: "Total Activities",
      count: stats.total_activities,
      description: "Recorded audit logs",
      icon: Activity,
      color: "text-blue-500",
      bgColor: "bg-blue-500/10",
      borderColor: "border-blue-500/20",
    },
    {
      title: "Files Affected",
      count: stats.file_changes_count,
      description: "Operations completed",
      icon: FileCheck,
      color: "text-emerald-500",
      bgColor: "bg-emerald-500/10",
      borderColor: "border-emerald-500/20",
    },
    {
      title: "Executions Succeeded",
      count: stats.executions_succeeded,
      description: "Jobs finished cleanly",
      icon: CheckCircle2,
      color: "text-indigo-500",
      bgColor: "bg-indigo-500/10",
      borderColor: "border-indigo-500/20",
    },
    {
      title: "Rollbacks & Failures",
      count: stats.rollbacks_count + stats.executions_failed,
      description: `${stats.rollbacks_count} restored, ${stats.executions_failed} errors`,
      icon: RotateCcw,
      color: stats.rollbacks_count + stats.executions_failed > 0 ? "text-amber-500" : "text-muted-foreground",
      bgColor: stats.rollbacks_count + stats.executions_failed > 0 ? "bg-amber-500/10" : "bg-muted",
      borderColor: stats.rollbacks_count + stats.executions_failed > 0 ? "border-amber-500/20" : "border-border",
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {cards.map((card, idx) => {
        const Icon = card.icon;
        return (
          <div
            key={idx}
            className="p-3.5 rounded-lg border border-border bg-card shadow-xs relative overflow-hidden"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">{card.title}</span>
              <div className={`p-1.5 rounded-md ${card.bgColor} ${card.color}`}>
                <Icon size={16} />
              </div>
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-bold tracking-tight">{card.count}</span>
              <span className="text-[11px] text-muted-foreground truncate">{card.description}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
};

