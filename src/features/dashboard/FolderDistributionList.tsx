import React from "react";
import { FolderTree, Folder, ArrowRight } from "lucide-react";
import type { DashboardFolderDistributionItemData } from "@/types";
import { formatBytes } from "@/lib/utils";

interface FolderDistributionListProps {
  folders: DashboardFolderDistributionItemData[];
  totalFoldersCount: number;
  onOpenFolder: (folderId: string) => void;
  onViewAll: () => void;
}

export const FolderDistributionList: React.FC<FolderDistributionListProps> = ({
  folders,
  totalFoldersCount,
  onOpenFolder,
  onViewAll,
}) => {
  const isEmpty = folders.length === 0;

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <FolderTree size={16} className="text-primary" />
            Distribusi Folder
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Folder terkelola dengan penggunaan terbesar
          </p>
        </div>
        {totalFoldersCount > 5 && (
          <button
            type="button"
            onClick={onViewAll}
            className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
          >
            <span>Lihat Semua ({totalFoldersCount})</span>
            <ArrowRight size={12} />
          </button>
        )}
      </div>

      {isEmpty ? (
        <div className="py-12 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
            <Folder size={22} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Belum ada folder terdaftar</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Daftarkan folder pertama Anda untuk memantau alokasi ruang penyimpanan.
          </p>
        </div>
      ) : (
        <div className="mt-4 space-y-4">
          {folders.map((f) => (
            <div
              key={f.id}
              role="button"
              tabIndex={0}
              onClick={() => onOpenFolder(f.id)}
              onKeyDown={(e) => e.key === "Enter" && onOpenFolder(f.id)}
              className="p-2.5 rounded-lg border border-transparent hover:border-border hover:bg-muted/50 transition-all cursor-pointer group"
            >
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 min-w-0 pr-2">
                  <Folder size={15} className="text-primary flex-shrink-0" />
                  <span className="font-semibold text-foreground truncate group-hover:text-primary transition-colors">
                    {f.name}
                  </span>
                  <span className="text-[11px] text-muted-foreground truncate hidden sm:inline" title={f.root_path}>
                    ({f.root_path})
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0 text-muted-foreground">
                  <span className="font-medium text-foreground">{formatBytes(f.size_bytes)}</span>
                  <span className="font-semibold w-9 text-right text-foreground/80">{f.percentage}%</span>
                </div>
              </div>

              {/* Progress bar */}
              <div className="w-full bg-muted rounded-full h-1.5 mt-2 overflow-hidden">
                <div
                  className="bg-primary h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(2, f.percentage))}%` }}
                />
              </div>

              <div className="flex items-center justify-between text-[11px] text-muted-foreground mt-1.5">
                <span>{f.files_count.toLocaleString()} file terindeks</span>
                <span className="text-primary group-hover:underline text-[10px]">Buka di Files &rarr;</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
