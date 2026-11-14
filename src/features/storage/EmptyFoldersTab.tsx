import React, { useState, useMemo, useEffect } from "react";
import {
  FolderX,
  Search,
  Copy,
  Check,
  ShieldCheck,
  Folder,
  Trash2,
  ArrowRight,
  CheckCircle2,
  CircleX,
} from "lucide-react";
import { formatDate } from "@/lib/utils";
import { ApiService } from "@/services/api";
import type { EmptyFolderItem, StorageCleanupItemInput } from "@/types";

interface EmptyFoldersTabProps {
  folders: EmptyFolderItem[];
  managedFolderId?: string;
  onOpenFolder?: (relativePath: string, folderId?: string) => void;
  onNavigateToReviewChanges?: () => void;
}

export const EmptyFoldersTab: React.FC<EmptyFoldersTabProps> = ({
  folders,
  managedFolderId,
  onOpenFolder,
  onNavigateToReviewChanges,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());
  const [submittedKeys, setSubmittedKeys] = useState<Set<string>>(new Set());
  const [isCreatingPlan, setIsCreatingPlan] = useState(false);
  const [planFeedback, setPlanFeedback] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  const getFolderKey = (folder: EmptyFolderItem) =>
    `${folder.managed_folder_id || managedFolderId || ""}:${folder.relative_path}`;

  useEffect(() => {
    setSubmittedKeys(new Set());
    setSelectedKeys(new Set());
  }, [folders]);

  const activeFolders = useMemo(() => {
    return folders.filter((f) => !submittedKeys.has(getFolderKey(f)));
  }, [folders, submittedKeys, managedFolderId]);

  const filteredFolders = useMemo(() => {
    if (!searchQuery.trim()) return activeFolders;
    const q = searchQuery.toLowerCase();
    return activeFolders.filter(
      (f) =>
        f.name.toLowerCase().includes(q) ||
        f.relative_path.toLowerCase().includes(q)
    );
  }, [activeFolders, searchQuery]);

  const handleCopyPath = async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      setTimeout(() => setCopiedPath(null), 2000);
    } catch {
      // ignore
    }
  };

  const handleToggleSelect = (key: string) => {
    const next = new Set(selectedKeys);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setSelectedKeys(next);
  };

  const handleToggleAll = () => {
    if (selectedKeys.size === filteredFolders.length) {
      setSelectedKeys(new Set());
    } else {
      setSelectedKeys(new Set(filteredFolders.map((f) => getFolderKey(f))));
    }
  };

  const handleSendCleanupPlan = async () => {
    const sourceList =
      selectedKeys.size > 0
        ? filteredFolders.filter((f) => selectedKeys.has(getFolderKey(f)))
        : filteredFolders;

    const items: StorageCleanupItemInput[] = [];
    for (const folder of sourceList) {
      const fid = folder.managed_folder_id || managedFolderId;
      if (fid) {
        items.push({
          managed_folder_id: fid,
          relative_path: folder.relative_path,
          reason: "Empty directory cleanup",
        });
      }
    }
    if (items.length === 0) return;
    setIsCreatingPlan(true);
    setPlanFeedback(null);
    setPlanError(null);
    try {
      const res = await ApiService.createStorageCleanupPlan({
        cleanup_type: "empty_folders",
        items,
      });
      const nextSubmitted = new Set(submittedKeys);
      sourceList.forEach((f) => nextSubmitted.add(getFolderKey(f)));
      setSubmittedKeys(nextSubmitted);
      setPlanFeedback(res.message);
      setSelectedKeys(new Set());
    } catch (err: unknown) {
      setPlanError(err instanceof Error ? err.message : "Failed to queue empty folder cleanup");
    } finally {
      setIsCreatingPlan(false);
    }
  };

  const hasPlanTargets = filteredFolders.some((f) => Boolean(f.managed_folder_id || managedFolderId));

  return (
    <div className="space-y-4">
      {/* Safety Notice */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-700 dark:text-emerald-300">
        <ShieldCheck size={16} className="shrink-0" />
        <span>
          These directories contain zero files and zero subdirectories. Cleanups or deletions must be planned and approved via Review Changes.
        </span>
      </div>

      {/* Plan Creation Feedback Banners */}
      {planFeedback && (
        <div className="flex items-center justify-between gap-3 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-700 dark:text-emerald-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="shrink-0" />
            <span>{planFeedback}</span>
          </div>
          {onNavigateToReviewChanges && (
            <button
              onClick={onNavigateToReviewChanges}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium shrink-0"
            >
              <span>Open Review Changes</span>
              <ArrowRight size={13} />
            </button>
          )}
        </div>
      )}
      {planError && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-xs text-destructive">
          <CircleX size={16} className="shrink-0" />
          <span>{planError}</span>
        </div>
      )}

      {/* Search Bar */}
      <div className="p-4 rounded-xl border border-border bg-card shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-96">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search empty folders by name or path..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-muted/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
          <span>
            Showing <strong className="text-foreground">{filteredFolders.length}</strong> of {activeFolders.length} empty directories
          </span>
          {hasPlanTargets && (
            <button
              onClick={handleSendCleanupPlan}
              disabled={isCreatingPlan}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 font-semibold transition-colors disabled:opacity-50"
            >
              <Trash2 size={13} />
              <span>
                {isCreatingPlan
                  ? "Creating Plan..."
                  : selectedKeys.size > 0
                  ? `Clean Up Selected (${selectedKeys.size})`
                  : "Clean Up Empty Folders (via Review Changes)"}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {filteredFolders.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground space-y-2">
            <FolderX size={32} className="mx-auto text-muted-foreground/40" />
            <p className="text-xs font-semibold">No empty folders found</p>
            <p className="text-[11px]">All scanned directories contain files or subfolders.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
                <tr>
                  <th className="py-2.5 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedKeys.size === filteredFolders.length && filteredFolders.length > 0}
                      onChange={handleToggleAll}
                      className="rounded border-border text-primary focus:ring-primary"
                    />
                  </th>
                  <th className="py-2.5 px-4">Folder Name</th>
                  <th className="py-2.5 px-4">Relative Path</th>
                  <th className="py-2.5 px-4">Modified Date</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredFolders.map((folder) => {
                  const key = getFolderKey(folder);
                  const isSelected = selectedKeys.has(key);
                  return (
                    <tr
                      key={key}
                      className={`hover:bg-muted/30 transition-colors ${
                        isSelected ? "bg-primary/5" : ""
                      }`}
                    >
                      <td className="py-2.5 px-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelect(key)}
                          className="rounded border-border text-primary focus:ring-primary"
                        />
                      </td>
                      <td className="py-2.5 px-4 font-semibold text-foreground flex items-center gap-2">
                        <Folder size={16} className="text-amber-500 fill-amber-500/20 shrink-0" />
                        <span>{folder.name}</span>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-[11px] text-muted-foreground truncate max-w-md" title={folder.relative_path}>
                        {folder.relative_path}
                      </td>
                      <td className="py-2.5 px-4 text-muted-foreground">
                        {formatDate(folder.modified_at)}
                      </td>
                      <td className="py-2.5 px-4 text-right space-x-1">
                        <button
                          onClick={() => handleCopyPath(folder.relative_path)}
                          title="Copy path"
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {copiedPath === folder.relative_path ? (
                            <Check size={14} className="text-emerald-600" />
                          ) : (
                            <Copy size={14} />
                          )}
                        </button>
                        {onOpenFolder && (
                          <button
                            onClick={() =>
                              onOpenFolder(
                                folder.relative_path,
                                folder.managed_folder_id || undefined
                              )
                            }
                            className="px-2 py-0.5 rounded text-[11px] bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border"
                          >
                            View
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
