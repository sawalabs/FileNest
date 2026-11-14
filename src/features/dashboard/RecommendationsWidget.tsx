import React from "react";
import {
  Sparkles,
  FolderTree,
  FilePenLine,
  Copy,
  ArrowRight,
  Info,
} from "lucide-react";
import type { DashboardRecommendationItemData, NavItem } from "@/types";

interface RecommendationsWidgetProps {
  recommendations: DashboardRecommendationItemData[];
  onNavigate: (tab: NavItem) => void;
}

export const RecommendationsWidget: React.FC<RecommendationsWidgetProps> = ({
  recommendations,
  onNavigate,
}) => {
  const isEmpty = recommendations.length === 0;

  const getRecommendationIcon = (type: string) => {
    switch (type) {
      case "organization":
        return <FolderTree size={16} className="text-blue-500" />;
      case "smart_rename":
        return <FilePenLine size={16} className="text-emerald-500" />;
      case "duplicates":
        return <Copy size={16} className="text-amber-500" />;
      default:
        return <Sparkles size={16} className="text-primary" />;
    }
  };

  const handleClick = (rec: DashboardRecommendationItemData) => {
    if (rec.type === "organization") {
      onNavigate("organization");
    } else if (rec.type === "smart_rename") {
      onNavigate("smart-rename");
    } else if (rec.type === "duplicates") {
      onNavigate("storage");
    } else {
      onNavigate("storage");
    }
  };

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Sparkles size={16} className="text-primary" />
            Rekomendasi Pengelolaan
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Saran penataan otomatis berbasis analisis file
          </p>
        </div>
        <span className="text-[11px] font-medium text-muted-foreground bg-muted px-2 py-0.5 rounded">
          {recommendations.length} Saran
        </span>
      </div>

      {isEmpty ? (
        <div className="py-10 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
            <Info size={18} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Belum ada rekomendasi baru</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Semua file terkelola sudah dalam kondisi rapi atau belum dianalisis.
          </p>
        </div>
      ) : (
        <div className="mt-3 space-y-3">
          {recommendations.map((rec) => (
            <div
              key={rec.id}
              role="button"
              tabIndex={0}
              onClick={() => handleClick(rec)}
              onKeyDown={(e) => e.key === "Enter" && handleClick(rec)}
              className="p-3 rounded-lg border border-border/60 hover:border-primary/50 bg-background/50 hover:bg-muted/40 transition-all cursor-pointer group flex items-start justify-between gap-3 text-xs"
            >
              <div className="flex items-start gap-2.5 min-w-0">
                <div className="p-1.5 rounded-md bg-muted flex-shrink-0 mt-0.5">
                  {getRecommendationIcon(rec.type)}
                </div>
                <div>
                  <h4 className="font-semibold text-foreground group-hover:text-primary transition-colors">
                    {rec.title}
                  </h4>
                  <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2">
                    {rec.description}
                  </p>
                  {rec.impact_count > 0 && (
                    <span className="inline-block text-[10px] text-primary font-medium mt-1">
                      {rec.impact_count.toLocaleString()} file terdampak
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center text-muted-foreground group-hover:text-primary transition-colors flex-shrink-0 mt-1">
                <ArrowRight size={14} />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
