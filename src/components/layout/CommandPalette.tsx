import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Search,
  X,
  LayoutDashboard,
  Folder,
  HardDrive,
  FolderTree,
  FilePenLine,
  ClipboardCheck,
  Activity,
  History,
  Settings,
  FolderPlus,
  Sparkles,
  FileText,
  CornerDownLeft,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { formatBytes } from "@/lib/utils";
import type { GlobalSearchHit, NavItem } from "@/types";

interface CommandPaletteProps {
  onNavigate: (item: NavItem) => void;
  onNavigateToFile: (folderId: string, relativePath: string) => void;
  onToggleAssistant: () => void;
}

interface NavCommand {
  id: NavItem;
  label: string;
  description: string;
  icon: LucideIcon;
}

const NAV_COMMANDS: NavCommand[] = [
  { id: "dashboard", label: "Overview", description: "Executive storage & activity summary", icon: LayoutDashboard },
  { id: "files", label: "Files", description: "Browse & inspect Managed Folders", icon: Folder },
  { id: "storage", label: "Storage Analyzer", description: "Analyze duplicates, large files, and empty folders", icon: HardDrive },
  { id: "organization", label: "Organization", description: "Create plans and manage automation rules", icon: FolderTree },
  { id: "smart-rename", label: "Smart Rename", description: "Batch rename files with pattern previews", icon: FilePenLine },
  { id: "review-changes", label: "Review Changes", description: "Approve and execute pending change plans", icon: ClipboardCheck },
  { id: "monitoring", label: "Monitoring", description: "Watchdogs and filesystem event telemetry", icon: Activity },
  { id: "history", label: "History", description: "Execution jobs, audit logs, and manual undo", icon: History },
  { id: "managed-folders", label: "Managed Folders", description: "Register or configure workspace boundaries", icon: FolderPlus },
  { id: "settings", label: "Settings", description: "AI gateway, privacy, security, and appearance", icon: Settings },
];

export const CommandPalette: React.FC<CommandPaletteProps> = ({
  onNavigate,
  onNavigateToFile,
  onToggleAssistant,
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [fileHits, setFileHits] = useState<GlobalSearchHit[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsOpen((prev) => !prev);
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        setIsOpen(false);
      }
    };

    const handleOpenEvent = () => setIsOpen(true);

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("open-command-palette", handleOpenEvent);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("open-command-palette", handleOpenEvent);
    };
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setFileHits([]);
      setSearchError(null);
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 20);
    }
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setFileHits([]);
      setSearchError(null);
      setIsSearching(false);
      return;
    }

    let cancelled = false;
    setIsSearching(true);
    setSearchError(null);

    const timer = setTimeout(async () => {
      try {
        const res = await ApiService.searchFiles(trimmed, 20);
        if (!cancelled) {
          setFileHits(res.hits);
        }
      } catch (err: unknown) {
        if (!cancelled) {
          setSearchError(
            err instanceof Error ? err.message : "Failed to search files"
          );
          setFileHits([]);
        }
      } finally {
        if (!cancelled) {
          setIsSearching(false);
        }
      }
    }, 220);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [query, isOpen]);

  const filteredNav = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return NAV_COMMANDS;
    return NAV_COMMANDS.filter(
      (cmd) =>
        cmd.label.toLowerCase().includes(q) ||
        cmd.description.toLowerCase().includes(q)
    );
  }, [query]);

  type PaletteEntry =
    | { kind: "nav"; cmd: NavCommand }
    | { kind: "assistant" }
    | { kind: "file"; hit: GlobalSearchHit };

  const entries: PaletteEntry[] = useMemo(() => {
    const list: PaletteEntry[] = [];
    for (const hit of fileHits) {
      list.push({ kind: "file", hit });
    }
    for (const cmd of filteredNav) {
      list.push({ kind: "nav", cmd });
    }
    if (!query.trim() || "ai assistant".includes(query.trim().toLowerCase())) {
      list.push({ kind: "assistant" });
    }
    return list;
  }, [fileHits, filteredNav, query]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [entries.length]);

  const executeEntry = (entry: PaletteEntry) => {
    if (entry.kind === "nav") {
      onNavigate(entry.cmd.id);
    } else if (entry.kind === "assistant") {
      onToggleAssistant();
    } else {
      onNavigateToFile(entry.hit.managed_folder_id, entry.hit.relative_path);
    }
    setIsOpen(false);
  };

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (entries.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % entries.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + entries.length) % entries.length);
    } else if (e.key === "Enter") {
      e.preventDefault();
      const entry = entries[selectedIndex];
      if (entry) executeEntry(entry);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex items-start justify-center pt-[12vh] px-4"
      onClick={() => setIsOpen(false)}
    >
      <div
        className="w-full max-w-2xl rounded-xl border border-border bg-card shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input Header */}
        <div className="flex items-center gap-2.5 px-4 py-3 border-b border-border bg-muted/20">
          {isSearching ? (
            <Loader2 size={17} className="text-primary animate-spin shrink-0" />
          ) : (
            <Search size={17} className="text-muted-foreground shrink-0" />
          )}
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Search files across all Managed Folders or jump to a section..."
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
          />
          <button
            type="button"
            onClick={() => setIsOpen(false)}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
            title="Close (Esc)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Results Container */}
        <div className="max-h-[60vh] overflow-y-auto p-2 space-y-2">
          {searchError && (
            <div className="px-3 py-2 text-xs text-destructive bg-destructive/10 rounded-lg">
              {searchError}
            </div>
          )}

          {entries.length === 0 ? (
            <div className="py-10 text-center text-xs text-muted-foreground">
              No matching files or sections found.
            </div>
          ) : (
            entries.map((entry, idx) => {
              const isSelected = idx === selectedIndex;

              if (entry.kind === "file") {
                const { hit } = entry;
                const Icon = hit.item_type === "directory" ? Folder : FileText;
                return (
                  <button
                    key={`file-${hit.managed_folder_id}-${hit.relative_path}`}
                    type="button"
                    onClick={() => executeEntry(entry)}
                    className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
                      isSelected
                        ? "bg-primary/10 text-foreground"
                        : "hover:bg-muted/50 text-foreground"
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <Icon size={15} className="text-primary shrink-0" />
                      <div className="min-w-0">
                        <p className="font-semibold truncate">{hit.name}</p>
                        <p className="text-[11px] font-mono text-muted-foreground truncate">
                          {hit.managed_folder_name}/{hit.relative_path}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 text-[11px] text-muted-foreground">
                      {hit.item_type === "file" && <span>{formatBytes(hit.size_bytes)}</span>}
                      {isSelected && <CornerDownLeft size={13} className="text-primary" />}
                    </div>
                  </button>
                );
              }

              if (entry.kind === "assistant") {
                return (
                  <button
                    key="quick-assistant"
                    type="button"
                    onClick={() => executeEntry(entry)}
                    className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
                      isSelected
                        ? "bg-primary/10 text-foreground"
                        : "hover:bg-muted/50 text-foreground"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Sparkles size={15} className="text-primary shrink-0" />
                      <div>
                        <p className="font-semibold">Toggle AI Assistant</p>
                        <p className="text-[11px] text-muted-foreground">
                          Open contextual workspace intelligence panel
                        </p>
                      </div>
                    </div>
                    {isSelected && <CornerDownLeft size={13} className="text-primary" />}
                  </button>
                );
              }

              const Icon = entry.cmd.icon;
              return (
                <button
                  key={`nav-${entry.cmd.id}`}
                  type="button"
                  onClick={() => executeEntry(entry)}
                  className={`w-full flex items-center justify-between gap-3 px-3 py-2 rounded-lg text-left text-xs transition-colors ${
                    isSelected
                      ? "bg-primary/10 text-foreground"
                      : "hover:bg-muted/50 text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon size={15} className="text-muted-foreground shrink-0" />
                    <div className="min-w-0">
                      <p className="font-semibold">{entry.cmd.label}</p>
                      <p className="text-[11px] text-muted-foreground truncate">
                        {entry.cmd.description}
                      </p>
                    </div>
                  </div>
                  {isSelected && <CornerDownLeft size={13} className="text-primary shrink-0" />}
                </button>
              );
            })
          )}
        </div>

        {/* Footer Hints */}
        <div className="px-4 py-2 border-t border-border bg-muted/20 flex items-center justify-between text-[11px] text-muted-foreground">
          <span>Type at least 2 characters to search Managed Folders</span>
          <span className="font-mono">↑↓ Navigate · Enter Open · Esc Close</span>
        </div>
      </div>
    </div>
  );
};
