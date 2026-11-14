import React, { useState } from "react";
import {
  Folder,
  FolderPlus,
  MoreHorizontal,
  ExternalLink,
  RefreshCw,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import type { DashboardManagedFolderItemData, NavItem } from "@/types";
import { formatBytes } from "@/lib/utils";
import { cn } from "@/lib/utils";
import { usePreferences } from "@/contexts/PreferencesContext";

interface DashboardManagedFoldersTableProps {
  folders: DashboardManagedFolderItemData[];
  onAddFolder: () => void;
  onOpenFolderInFiles: (folderId: string) => void;
  onOpenFolderInExplorer: (rootPath: string) => void;
  onScanFolder: (folderId: string) => void;
  onToggleMonitoring: (folderId: string, currentStatus: boolean) => void;
  onRemoveFolder: (folderId: string, folderName: string) => void;
  onNavigate: (tab: NavItem) => void;
}

export const DashboardManagedFoldersTable: React.FC<DashboardManagedFoldersTableProps> = ({
  folders,
  onAddFolder,
  onOpenFolderInFiles,
  onOpenFolderInExplorer,
  onScanFolder,
  onToggleMonitoring,
  onRemoveFolder,
  onNavigate,
}) => {
  const { defaultTableDensity } = usePreferences();
  const isCompact = defaultTableDensity === "compact";
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <Folder size={16} className="text-amber-500 fill-amber-500/20" />
            Folder Dikelola
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Daftar folder terdaftar
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => onNavigate("managed-folders")}
            className="text-xs font-semibold text-primary hover:underline"
          >
            Kelola
          </button>
        </div>
      </div>

      {folders.length === 0 ? (
        <div className="py-8 flex flex-col items-center justify-center text-center text-muted-foreground my-auto">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
            <FolderPlus size={18} className="text-muted-foreground/60" />
          </div>
          <p className="text-xs font-medium text-foreground">Belum ada folder</p>
          <button
            type="button"
            onClick={onAddFolder}
            className="mt-3 inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
          >
            <FolderPlus size={13} />
            <span>Tambah Folder</span>
          </button>
        </div>
      ) : (
        <div className="mt-3 space-y-2.5 my-auto">
          {folders.slice(0, 4).map((f) => (
            <div
              key={f.id}
              className={`${isCompact ? "p-1.5" : "p-2.5"} rounded-lg border border-border/60 hover:border-border bg-background/50 hover:bg-muted/40 transition-all flex items-center justify-between gap-3 text-xs group`}
            >
              {/* Folder Details */}
              <div
                role="button"
                tabIndex={0}
                onClick={() => onOpenFolderInFiles(f.id)}
                onKeyDown={(e) => e.key === "Enter" && onOpenFolderInFiles(f.id)}
                className="flex items-center gap-2.5 min-w-0 flex-1 cursor-pointer"
              >
                <Folder
                  size={18}
                  className="text-amber-500 fill-amber-500/20 shrink-0 group-hover:scale-105 transition-transform"
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="font-semibold text-foreground group-hover:text-primary transition-colors truncate">
                      {f.name}
                    </span>
                    {!f.is_accessible && (
                      <span title="Path tidak dapat diakses">
                        <AlertTriangle size={11} className="text-amber-500 shrink-0" />
                      </span>
                    )}
                  </div>
                  <p className="text-[10px] text-muted-foreground truncate" title={f.root_path}>
                    {f.root_path}
                  </p>
                </div>
              </div>

              {/* Size & Files */}
              <div className="text-right shrink-0">
                <span className="font-bold text-foreground text-xs block">
                  {formatBytes(f.size_bytes)}
                </span>
                <span className="text-[10px] text-muted-foreground block">
                  {f.files_count.toLocaleString()} file
                </span>
              </div>

              {/* iOS / Windows Modern Toggle Switch */}
              <button
                type="button"
                onClick={() => onToggleMonitoring(f.id, f.is_monitoring_active)}
                title={f.is_monitoring_active ? "Monitoring aktif (klik untuk matikan)" : "Monitoring mati (klik untuk aktifkan)"}
                className={cn(
                  "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none",
                  f.is_monitoring_active ? "bg-emerald-500" : "bg-muted-foreground/30"
                )}
              >
                <span
                  className={cn(
                    "pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out",
                    f.is_monitoring_active ? "translate-x-4" : "translate-x-0"
                  )}
                />
              </button>

              {/* Context Menu */}
              <div className="relative shrink-0">
                <button
                  type="button"
                  onClick={() => setOpenMenuId(openMenuId === f.id ? null : f.id)}
                  className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  title="Opsi"
                >
                  <MoreHorizontal size={15} />
                </button>

                {openMenuId === f.id && (
                  <>
                    <div
                      className="fixed inset-0 z-20"
                      onClick={() => setOpenMenuId(null)}
                    />
                    <div className="absolute right-0 mt-1 w-44 rounded-lg border border-border bg-popover shadow-lg py-1 z-30 text-left text-xs animate-in fade-in-50 zoom-in-95">
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null);
                          onOpenFolderInExplorer(f.root_path);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-muted text-popover-foreground transition-colors"
                      >
                        <ExternalLink size={13} />
                        <span>Buka di Explorer</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null);
                          onScanFolder(f.id);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-muted text-popover-foreground transition-colors"
                      >
                        <RefreshCw size={13} />
                        <span>Pindai Sekarang</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setOpenMenuId(null);
                          onRemoveFolder(f.id, f.name);
                        }}
                        className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-destructive/10 text-destructive transition-colors border-t border-border/50"
                      >
                        <Trash2 size={13} />
                        <span>Hapus dari Kelolaan</span>
                      </button>
                    </div>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {folders.length > 4 && (
        <div className="pt-2 text-center border-t border-border/40 mt-2">
          <button
            type="button"
            onClick={() => onNavigate("managed-folders")}
            className="text-[11px] text-muted-foreground hover:text-primary transition-colors font-medium"
          >
            Lihat semua {folders.length} folder &rarr;
          </button>
        </div>
      )}
    </div>
  );
};