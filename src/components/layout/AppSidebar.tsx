import React, { useState, useEffect } from "react";
import {
  LayoutDashboard,
  Folder,
  HardDrive,
  FolderTree,
  FilePenLine,
  Activity,
  History,
  Settings,
  ShieldCheck,
  CircleAlert,
  Loader2,
  ClipboardCheck,
  Sparkles,
  ChevronDown,
  ChevronRight,
  Plus,
  Trash2,
  Search,
  type LucideIcon,
} from "lucide-react";
import type { NavItem, BackendHealth, ManagedFolder } from "@/types";
import { ApiService } from "@/services/api";
import { cn } from "@/lib/utils";
import { UnregisterFolderModal } from "@/features/files/UnregisterFolderModal";

interface AppSidebarProps {
  activeItem: NavItem;
  onNavigate: (item: NavItem) => void;
  backendHealth: BackendHealth;
  onToggleAssistant?: () => void;
}

const mainNavItems: { id: NavItem; label: string; icon: LucideIcon }[] = [
  { id: "dashboard", label: "Overview", icon: LayoutDashboard },
  { id: "files", label: "Files", icon: Folder },
  { id: "storage", label: "Storage", icon: HardDrive },
  { id: "organization", label: "Organization", icon: FolderTree },
  { id: "smart-rename", label: "Smart Rename", icon: FilePenLine },
  { id: "review-changes", label: "Review Changes", icon: ClipboardCheck },
  { id: "monitoring", label: "Monitoring", icon: Activity },
  { id: "history", label: "History", icon: History },
];

export const AppSidebar: React.FC<AppSidebarProps> = ({
  activeItem,
  onNavigate,
  backendHealth,
  onToggleAssistant,
}) => {
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [isFoldersOpen, setIsFoldersOpen] = useState(true);
  const [folderToUnregister, setFolderToUnregister] = useState<ManagedFolder | null>(null);

  useEffect(() => {
    loadFolders();
    const handleFoldersChanged = () => {
      loadFolders();
    };
    window.addEventListener("folders-changed", handleFoldersChanged);
    return () => {
      window.removeEventListener("folders-changed", handleFoldersChanged);
    };
  }, [activeItem]);

  const loadFolders = async () => {
    try {
      const list = await ApiService.listFolders(true);
      setFolders(list);
    } catch {
      // Ignored if backend is offline or connecting
    }
  };

  const handleUnregisterFolder = async (folder: ManagedFolder, permanent: boolean = true) => {
    try {
      await ApiService.unregisterFolder(folder.id, permanent);
      await loadFolders();
      window.dispatchEvent(new Event("folders-changed"));
    } catch (err: unknown) {
      console.error("Failed to unregister folder:", err);
    }
  };

  const handleAddFolder = async () => {
    try {
      let selectedPath: string | null = null;
      try {
        const { open } = await import("@tauri-apps/plugin-dialog");
        const result = await open({
          directory: true,
          multiple: false,
          title: "Select Folder to Manage",
        });
        if (typeof result === "string") {
          selectedPath = result;
        }
      } catch {
        selectedPath = window.prompt("Enter absolute Windows folder path:");
      }

      if (!selectedPath) return;

      const folderName = selectedPath.split(/[\\/]/).filter(Boolean).pop() || "New Folder";
      const created = await ApiService.registerFolder({
        name: folderName,
        root_path: selectedPath,
      });

      await loadFolders();
      window.dispatchEvent(new Event("folders-changed"));
      window.dispatchEvent(
        new CustomEvent("select-managed-folder", { detail: { folderId: created.id } })
      );
      onNavigate("files");
    } catch (err: unknown) {
      console.error("Failed to add folder:", err);
    }
  };

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col h-screen select-none shrink-0">
      {/* App Brand — FileNest Storage Manager */}
      <div className="h-14 border-b border-border flex items-center px-4 gap-2.5">
        <div className="w-8 h-8 rounded-lg bg-blue-600 text-white flex items-center justify-center shadow-sm shrink-0">
          <Folder className="fill-white/20 text-white" size={18} />
        </div>
        <div className="min-w-0">
          <h1 className="font-bold text-sm tracking-tight text-foreground leading-tight truncate">
            FileNest
          </h1>
          <p className="text-[11px] text-muted-foreground font-medium truncate">
            Storage Manager
          </p>
        </div>
      </div>

      {/* Quick Global Search Trigger (Ctrl+K) */}
      <div className="px-3 pt-3 pb-1">
        <button
          type="button"
          onClick={() => window.dispatchEvent(new Event("open-command-palette"))}
          className="w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg border border-border bg-muted/40 hover:bg-muted text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <span className="inline-flex items-center gap-2 truncate">
            <Search size={13} className="shrink-0" />
            <span className="truncate">Quick Search...</span>
          </span>
          <kbd className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-background border border-border text-muted-foreground shrink-0">
            Ctrl+K
          </kbd>
        </button>
      </div>

      {/* Navigation Links & Managed Folders Section */}
      <div className="flex-1 px-3 py-3 space-y-4 overflow-y-auto">
        {/* Main Navigation */}
        <nav className="space-y-1">
          {mainNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = activeItem === item.id;
            return (
              <button
                key={item.id}
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors text-left",
                  isActive
                    ? "bg-primary text-primary-foreground shadow-sm"
                    : "text-foreground/80 hover:bg-muted hover:text-foreground"
                )}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Collapsible Managed Folders Section */}
        <div className="pt-2 border-t border-border/60">
          <button
            type="button"
            onClick={() => setIsFoldersOpen((prev) => !prev)}
            className="w-full flex items-center justify-between px-2.5 py-1 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors uppercase tracking-wider"
          >
            <div className="flex items-center gap-1.5">
              <Folder size={14} className="text-muted-foreground" />
              <span>Managed Folders</span>
            </div>
            {isFoldersOpen ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </button>

          {isFoldersOpen && (
            <div className="mt-1 space-y-0.5 pl-1 animate-in fade-in-50 duration-150">
              {folders.map((f) => (
                <div
                  key={f.id}
                  className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-md text-xs font-medium text-foreground/80 hover:bg-muted hover:text-foreground transition-colors group"
                >
                  <button
                    type="button"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent("select-managed-folder", { detail: { folderId: f.id } })
                      );
                      onNavigate("files");
                    }}
                    title={`${f.name} (${f.root_path})`}
                    className="flex items-center gap-2 min-w-0 flex-1 text-left"
                  >
                    <Folder
                      size={14}
                      className="text-amber-500 fill-amber-500/20 shrink-0 group-hover:scale-105 transition-transform"
                    />
                    <span className="truncate">{f.name || f.root_path}</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setFolderToUnregister(f);
                    }}
                    title="Hapus dari daftar Managed Folders"
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0 ml-1"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}

              <button
                type="button"
                onClick={handleAddFolder}
                className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-md text-xs font-medium text-primary hover:bg-primary/10 transition-colors text-left mt-1"
              >
                <Plus size={14} />
                <span>Add Folder</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* AI Assistant Trigger Button */}
      {onToggleAssistant && (
        <div className="px-3 pb-2">
          <button
            onClick={onToggleAssistant}
            className="w-full flex items-center justify-between px-3 py-2 rounded-md bg-primary/10 hover:bg-primary/20 text-primary text-xs font-semibold border border-primary/20 transition-colors shadow-sm"
          >
            <div className="flex items-center gap-2">
              <Sparkles size={16} />
              <span>AI Assistant</span>
            </div>
            <span className="text-[10px] bg-primary text-primary-foreground px-1.5 py-0.5 rounded-full font-medium">
              Contextual
            </span>
          </button>
        </div>
      )}

      {/* Pinned Settings Row */}
      <div className="px-3 pb-2 pt-1 border-t border-border">
        <button
          onClick={() => onNavigate("settings")}
          className={cn(
            "w-full flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors text-left",
            activeItem === "settings"
              ? "bg-primary text-primary-foreground shadow-sm"
              : "text-foreground/80 hover:bg-muted hover:text-foreground"
          )}
        >
          <Settings size={18} />
          <span>Settings</span>
        </button>
      </div>

      {/* Backend Status Footer */}
      <div className="p-3 border-t border-border bg-muted/40">
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground font-medium">Backend API</span>
          <div className="flex items-center gap-1.5">
            {backendHealth.status === "ok" && (
              <>
                <ShieldCheck size={14} className="text-emerald-600" />
                <span className="text-emerald-700 dark:text-emerald-400 font-medium">Connected</span>
              </>
            )}
            {backendHealth.status === "connecting" && (
              <>
                <Loader2 size={14} className="animate-spin text-amber-600" />
                <span className="text-amber-700 dark:text-amber-400 font-medium">Connecting...</span>
              </>
            )}
            {backendHealth.status === "error" && (
              <>
                <CircleAlert size={14} className="text-rose-600" />
                <span className="text-rose-700 dark:text-rose-400 font-medium">Offline</span>
              </>
            )}
          </div>
        </div>
        {backendHealth.version && (
          <div className="text-[11px] text-muted-foreground mt-1">
            v{backendHealth.version} ({backendHealth.environment})
          </div>
        )}
      </div>

      <UnregisterFolderModal
        isOpen={Boolean(folderToUnregister)}
        onClose={() => setFolderToUnregister(null)}
        folder={folderToUnregister}
        onConfirm={handleUnregisterFolder}
      />
    </aside>
  );
};
