import React, { useState, useMemo, useEffect } from "react";
import {
  Search,
  Filter,
  ArrowUpDown,
  Copy,
  Check,
  FileWarning,
  Info,
  Trash2,
  ArrowRight,
  CheckCircle2,
  CircleX,
} from "lucide-react";
import { formatBytes, formatDate } from "@/lib/utils";
import { FileIcon } from "@/features/files/FileIcon";
import { ApiService } from "@/services/api";
import type { LargeFileItem, FileCategory, StorageCleanupItemInput } from "@/types";

interface LargeFilesTabProps {
  files: LargeFileItem[];
  managedFolderId?: string;
  onOpenLocation?: (relativePath: string, folderId?: string) => void;
  onNavigateToReviewChanges?: () => void;
}

export const LargeFilesTab: React.FC<LargeFilesTabProps> = ({
  files,
  managedFolderId,
  onOpenLocation,
  onNavigateToReviewChanges,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [minSizeMB, setMinSizeMB] = useState<number>(0);
  const [sortBy, setSortBy] = useState<"size_desc" | "size_asc" | "name_asc" | "date_desc">("size_desc");
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [submittedKeys, setSubmittedKeys] = useState<Set<string>>(new Set());
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [isCreatingPlan, setIsCreatingPlan] = useState(false);
  const [planFeedback, setPlanFeedback] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  const getFileSelectionKey = (file: LargeFileItem) =>
    `${file.managed_folder_id || managedFolderId || ""}:${file.relative_path}`;

  useEffect(() => {
    setSubmittedKeys(new Set());
    setSelectedPaths(new Set());
  }, [files]);

  const activeFiles = useMemo(() => {
    return files.filter((f) => !submittedKeys.has(getFileSelectionKey(f)));
  }, [files, submittedKeys, managedFolderId]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    activeFiles.forEach((f) => {
      if (f.category) set.add(f.category);
    });
    return Array.from(set).sort();
  }, [activeFiles]);

  const filteredFiles = useMemo(() => {
    return activeFiles
      .filter((file) => {
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          if (
            !file.name.toLowerCase().includes(q) &&
            !file.relative_path.toLowerCase().includes(q)
          ) {
            return false;
          }
        }
        if (categoryFilter !== "all" && file.category.toLowerCase() !== categoryFilter.toLowerCase()) {
          return false;
        }
        if (minSizeMB > 0 && file.size_bytes < minSizeMB * 1024 * 1024) {
          return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "size_desc") return b.size_bytes - a.size_bytes;
        if (sortBy === "size_asc") return a.size_bytes - b.size_bytes;
        if (sortBy === "name_asc") return a.name.localeCompare(b.name);
        if (sortBy === "date_desc") {
          const da = a.modified_at ? new Date(a.modified_at).getTime() : 0;
          const db = b.modified_at ? new Date(b.modified_at).getTime() : 0;
          return db - da;
        }
        return 0;
      });
  }, [files, searchQuery, categoryFilter, minSizeMB, sortBy]);

  const handleToggleSelect = (key: string) => {
    const next = new Set(selectedPaths);
    if (next.has(key)) {
      next.delete(key);
    } else {
      next.add(key);
    }
    setSelectedPaths(next);
  };

  const handleSelectAll = () => {
    if (selectedPaths.size === filteredFiles.length) {
      setSelectedPaths(new Set());
    } else {
      setSelectedPaths(new Set(filteredFiles.map((f) => getFileSelectionKey(f))));
    }
  };

  const handleSendSelectedToReview = async () => {
    const items: StorageCleanupItemInput[] = [];
    for (const file of filteredFiles) {
      const key = getFileSelectionKey(file);
      if (!selectedPaths.has(key)) continue;
      const folderId = file.managed_folder_id || managedFolderId;
      if (folderId) {
        items.push({
          managed_folder_id: folderId,
          relative_path: file.relative_path,
          reason: `Large file cleanup (${formatBytes(file.size_bytes)})`,
        });
      }
    }
    if (items.length === 0) return;
    setIsCreatingPlan(true);
    setPlanFeedback(null);
    setPlanError(null);
    try {
      const res = await ApiService.createStorageCleanupPlan({
        cleanup_type: "large_files",
        items,
      });
      const nextSubmitted = new Set(submittedKeys);
      selectedPaths.forEach((k) => nextSubmitted.add(k));
      setSubmittedKeys(nextSubmitted);
      setPlanFeedback(res.message);
      setSelectedPaths(new Set());
    } catch (err: unknown) {
      setPlanError(err instanceof Error ? err.message : "Failed to queue large files");
    } finally {
      setIsCreatingPlan(false);
    }
  };

  const handleCopyPath = async (path: string) => {
    try {
      await navigator.clipboard.writeText(path);
      setCopiedPath(path);
      setTimeout(() => setCopiedPath(null), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-4">
      {/* Read-only Safety Banner */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-blue-700 dark:text-blue-300">
        <Info size={16} className="shrink-0" />
        <span>
          Storage Analyzer is strictly read-only. File review, cleanup plans, and relocations are safely processed through Transaction Manager.
        </span>
      </div>

      {/* Filter and Search Bar */}
      <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          {/* Search box */}
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search large files by name or relative path..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-muted/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          {/* Category Filter */}
          <div className="flex items-center gap-2">
            <Filter size={14} className="text-muted-foreground shrink-0" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </option>
              ))}
            </select>

            {/* Minimum Size Filter */}
            <select
              value={minSizeMB}
              onChange={(e) => setMinSizeMB(Number(e.target.value))}
              className="text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value={0}>Any Size</option>
              <option value={50}>&gt; 50 MB</option>
              <option value={100}>&gt; 100 MB</option>
              <option value={250}>&gt; 250 MB</option>
              <option value={500}>&gt; 500 MB</option>
              <option value={1024}>&gt; 1 GB</option>
            </select>

            {/* Sort Filter */}
            <div className="flex items-center gap-1.5">
              <ArrowUpDown size={14} className="text-muted-foreground shrink-0" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="size_desc">Largest First</option>
                <option value="size_asc">Smallest First</option>
                <option value="name_asc">File Name (A-Z)</option>
                <option value="date_desc">Modified (Newest)</option>
              </select>
            </div>
          </div>
        </div>

        {/* Status / Selection Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground pt-1 border-t border-border/40">
          <span>
            Showing <strong className="text-foreground">{filteredFiles.length}</strong> of {activeFiles.length} large files
          </span>
          {selectedPaths.size > 0 && (
            <div className="flex flex-wrap items-center gap-2.5">
              <span className="font-medium text-foreground">
                {selectedPaths.size} selected
              </span>
              <button
                onClick={handleSendSelectedToReview}
                disabled={isCreatingPlan}
                className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-amber-600 text-white hover:bg-amber-700 font-semibold transition-colors disabled:opacity-50"
              >
                <Trash2 size={12} />
                <span>
                  {isCreatingPlan
                    ? "Queueing..."
                    : "Move Selected to Recycle Bin (via Review Changes)"}
                </span>
              </button>
              <button
                onClick={() => setSelectedPaths(new Set())}
                className="text-primary hover:underline text-[11px]"
              >
                Clear Selection
              </button>
            </div>
          )}
        </div>
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

      {/* Files Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {filteredFiles.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground space-y-2">
            <FileWarning size={32} className="mx-auto text-muted-foreground/40" />
            <p className="text-xs font-semibold">No large files found</p>
            <p className="text-[11px]">Try adjusting your search query, size threshold, or category filter.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
                <tr>
                  <th className="py-2.5 px-3 w-8">
                    <input
                      type="checkbox"
                      checked={selectedPaths.size === filteredFiles.length && filteredFiles.length > 0}
                      onChange={handleSelectAll}
                      className="rounded border-border text-primary focus:ring-primary"
                    />
                  </th>
                  <th className="py-2.5 px-3">File Name</th>
                  <th className="py-2.5 px-3">Location</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3 text-right">Size</th>
                  <th className="py-2.5 px-3">Modified</th>
                  <th className="py-2.5 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredFiles.map((file) => {
                  const selectionKey = getFileSelectionKey(file);
                  const isSelected = selectedPaths.has(selectionKey);
                  return (
                    <tr
                      key={selectionKey}
                      className={`hover:bg-muted/30 transition-colors ${
                        isSelected ? "bg-primary/5" : ""
                      }`}
                    >
                      <td className="py-2 px-3">
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleToggleSelect(selectionKey)}
                          className="rounded border-border text-primary focus:ring-primary"
                        />
                      </td>
                      <td className="py-2 px-3">
                        <div className="flex items-center gap-2">
                          <FileIcon
                            itemType="file"
                            category={file.category as FileCategory}
                            extension={file.extension}
                            size={16}
                          />
                          <span className="font-medium text-foreground truncate max-w-xs" title={file.name}>
                            {file.name}
                          </span>
                        </div>
                      </td>
                      <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-[200px]" title={file.relative_path}>
                        {file.relative_path}
                      </td>
                      <td className="py-2 px-3">
                        <span className="capitalize px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
                          {file.category}
                        </span>
                      </td>
                      <td className="py-2 px-3 text-right font-bold text-foreground">
                        {formatBytes(file.size_bytes)}
                      </td>
                      <td className="py-2 px-3 text-muted-foreground">
                        {formatDate(file.modified_at)}
                      </td>
                      <td className="py-2 px-3 text-right space-x-1">
                        <button
                          onClick={() => handleCopyPath(file.relative_path)}
                          title="Copy relative path"
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {copiedPath === file.relative_path ? (
                            <Check size={14} className="text-emerald-600" />
                          ) : (
                            <Copy size={14} />
                          )}
                        </button>
                        {onOpenLocation && (
                          <button
                            onClick={() =>
                              onOpenLocation(
                                file.relative_path,
                                file.managed_folder_id || undefined
                              )
                            }
                            title="Locate file"
                            className="px-2 py-0.5 rounded text-[11px] bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border"
                          >
                            Locate
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
