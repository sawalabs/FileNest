import React, { useState, useMemo, useEffect } from "react";
import {
  Copy,
  ChevronDown,
  ChevronRight,
  Search,
  Check,
  ShieldAlert,
  Layers,
  Sparkles,
  Trash2,
  ArrowRight,
  CheckCircle2,
  CircleX,
} from "lucide-react";
import { formatBytes, formatDate, formatNumber } from "@/lib/utils";
import { FileIcon } from "@/features/files/FileIcon";
import { ApiService } from "@/services/api";
import type { DuplicateGroup, StorageCleanupItemInput } from "@/types";

interface DuplicatesTabProps {
  groups: DuplicateGroup[];
  managedFolderId?: string;
  onOpenLocation?: (relativePath: string, folderId?: string) => void;
  onNavigateToReviewChanges?: () => void;
}

export const DuplicatesTab: React.FC<DuplicatesTabProps> = ({
  groups,
  managedFolderId,
  onOpenLocation,
  onNavigateToReviewChanges,
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedHashes, setExpandedHashes] = useState<Set<string>>(() => {
    // Expand the first 3 groups by default
    return new Set(groups.slice(0, 3).map((g) => g.hash));
  });
  const [copiedPath, setCopiedPath] = useState<string | null>(null);
  const [keepSelections, setKeepSelections] = useState<Record<string, string>>({});
  const [submittedHashes, setSubmittedHashes] = useState<Set<string>>(new Set());
  const [isCreatingPlan, setIsCreatingPlan] = useState(false);
  const [planFeedback, setPlanFeedback] = useState<string | null>(null);
  const [planError, setPlanError] = useState<string | null>(null);

  useEffect(() => {
    setSubmittedHashes(new Set());
    setKeepSelections({});
  }, [groups]);

  const activeGroups = useMemo(() => {
    return groups.filter((g) => !submittedHashes.has(g.hash));
  }, [groups, submittedHashes]);

  const filteredGroups = useMemo(() => {
    if (!searchQuery.trim()) return activeGroups;
    const q = searchQuery.toLowerCase();
    return activeGroups.filter((g) =>
      g.files.some(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          f.relative_path.toLowerCase().includes(q)
      )
    );
  }, [activeGroups, searchQuery]);

  const toggleExpand = (hash: string) => {
    const next = new Set(expandedHashes);
    if (next.has(hash)) {
      next.delete(hash);
    } else {
      next.add(hash);
    }
    setExpandedHashes(next);
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

  const handleSelectKeep = (groupHash: string, relativePath: string) => {
    setKeepSelections((prev) => ({
      ...prev,
      [groupHash]: relativePath,
    }));
  };

  const totalPotentialSavings = useMemo(() => {
    return activeGroups.reduce((acc, g) => acc + g.potential_savings_bytes, 0);
  }, [activeGroups]);

  const cleanupCandidates = useMemo(() => {
    const items: StorageCleanupItemInput[] = [];
    for (const group of filteredGroups) {
      const keepKey = keepSelections[group.hash] || group.files[0]?.relative_path;
      for (const file of group.files) {
        if (file.relative_path === keepKey) continue;
        const folderId = file.managed_folder_id || managedFolderId;
        if (folderId) {
          items.push({
            managed_folder_id: folderId,
            relative_path: file.relative_path,
            reason: `Duplicate of ${keepKey} (SHA ${group.hash.slice(0, 8)})`,
          });
        }
      }
    }
    return items;
  }, [filteredGroups, keepSelections, managedFolderId]);

  const handleCreateDuplicateCleanupPlan = async () => {
    if (cleanupCandidates.length === 0) return;
    setIsCreatingPlan(true);
    setPlanFeedback(null);
    setPlanError(null);
    try {
      const res = await ApiService.createStorageCleanupPlan({
        cleanup_type: "duplicates",
        items: cleanupCandidates,
      });
      const submitted = new Set(submittedHashes);
      filteredGroups.forEach((g) => submitted.add(g.hash));
      setSubmittedHashes(submitted);
      setKeepSelections({});
      setPlanFeedback(res.message);
    } catch (err: unknown) {
      setPlanError(err instanceof Error ? err.message : "Failed to create cleanup plan");
    } finally {
      setIsCreatingPlan(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Safety Banner */}
      <div className="flex items-center gap-2.5 p-3 rounded-lg bg-muted/60 border border-border text-xs text-muted-foreground">
        <ShieldAlert size={16} className="shrink-0 text-foreground" />
        <span>
          Identical files detected via progressive SHA-256 chunk hashing. Potential savings:{" "}
          <strong className="text-foreground">{formatBytes(totalPotentialSavings)}</strong>. Deletion or archival must be reviewed and approved.
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

      {/* Filter Bar */}
      <div className="p-4 rounded-xl border border-border bg-card shadow-sm flex flex-col sm:flex-row items-center justify-between gap-3">
        <div className="relative w-full sm:w-96">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search duplicate files..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-muted/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground self-end sm:self-auto">
          <span>
            <strong className="text-foreground">{filteredGroups.length}</strong> duplicate groups
          </span>
          <button
            onClick={() => {
              if (expandedHashes.size === filteredGroups.length) {
                setExpandedHashes(new Set());
              } else {
                setExpandedHashes(new Set(filteredGroups.map((g) => g.hash)));
              }
            }}
            className="text-primary hover:underline font-medium"
          >
            {expandedHashes.size === filteredGroups.length ? "Collapse All" : "Expand All"}
          </button>
          {cleanupCandidates.length > 0 && (
            <button
              onClick={handleCreateDuplicateCleanupPlan}
              disabled={isCreatingPlan}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-600 text-white hover:bg-amber-700 font-semibold transition-colors disabled:opacity-50"
            >
              <Trash2 size={13} />
              <span>
                {isCreatingPlan
                  ? "Creating Plan..."
                  : `Send Cleanup Plan (${cleanupCandidates.length}) to Review`}
              </span>
            </button>
          )}
        </div>
      </div>

      {/* Duplicate Groups List */}
      <div className="space-y-3">
        {filteredGroups.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground border border-border rounded-xl bg-card space-y-2">
            <Layers size={32} className="mx-auto text-muted-foreground/40" />
            <p className="text-xs font-semibold">No duplicate file groups found</p>
            <p className="text-[11px]">All indexed files appear to have unique content signatures.</p>
          </div>
        ) : (
          filteredGroups.map((group, idx) => {
            const isExpanded = expandedHashes.has(group.hash);
            const keepFile = keepSelections[group.hash] || group.files[0]?.relative_path;

            return (
              <div
                key={group.hash}
                className="rounded-xl border border-border bg-card shadow-sm overflow-hidden"
              >
                {/* Group Header */}
                <div
                  onClick={() => toggleExpand(group.hash)}
                  className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-muted/40 transition-colors bg-muted/15"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <button className="text-muted-foreground p-0.5">
                      {isExpanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                    </button>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-xs text-foreground">
                          Duplicate Group #{idx + 1}
                        </span>
                        <span className="text-[11px] px-2 py-0.5 rounded-md bg-secondary text-secondary-foreground font-medium border border-border">
                          {formatNumber(group.files_count)} copies
                        </span>
                        <span className="text-[11px] font-mono text-muted-foreground bg-muted px-2 py-0.5 rounded">
                          SHA: {group.hash.slice(0, 10)}...
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5 truncate max-w-md">
                        {group.files[0]?.name}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-4 text-xs">
                    <div className="text-right">
                      <div className="font-bold text-foreground">
                        {formatBytes(group.size_bytes)} each
                      </div>
                      <div className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
                        +{formatBytes(group.potential_savings_bytes)} potential savings
                      </div>
                    </div>
                  </div>
                </div>

                {/* Group Files Details (Expanded) */}
                {isExpanded && (
                  <div className="border-t border-border/60 divide-y divide-border/40">
                    {group.files.map((file) => {
                      const isKeep = keepFile === file.relative_path;

                      return (
                        <div
                          key={file.relative_path}
                          className={`p-3 flex items-center justify-between gap-3 text-xs transition-colors ${
                            isKeep ? "bg-emerald-500/5" : "hover:bg-muted/30"
                          }`}
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <FileIcon
                              itemType="file"
                              extension={file.name.split(".").pop()}
                              size={16}
                            />
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="font-medium text-foreground truncate max-w-sm" title={file.name}>
                                  {file.name}
                                </span>
                                {isKeep && (
                                  <span className="text-[10px] bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 px-2 py-0.2 rounded font-semibold flex items-center gap-1">
                                    <Sparkles size={11} />
                                    Keep Target
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] font-mono text-muted-foreground truncate max-w-md" title={file.relative_path}>
                                {file.relative_path}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-3 shrink-0">
                            <span className="text-muted-foreground text-[11px]">
                              {formatDate(file.modified_at)}
                            </span>
                            <span className="font-medium text-foreground">
                              {formatBytes(file.size_bytes)}
                            </span>

                            {/* Select as Keep Button */}
                            <button
                              onClick={() => handleSelectKeep(group.hash, file.relative_path)}
                              className={`px-2 py-1 rounded text-[11px] font-medium border transition-colors ${
                                isKeep
                                  ? "bg-emerald-600 text-white border-emerald-600"
                                  : "bg-secondary text-secondary-foreground hover:bg-secondary/80 border-border"
                              }`}
                            >
                              {isKeep ? "Selected to Keep" : "Select as Keep"}
                            </button>

                            {/* Copy Path */}
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

                            {/* Locate */}
                            {onOpenLocation && (
                              <button
                                onClick={() =>
                                  onOpenLocation(
                                    file.relative_path,
                                    file.managed_folder_id || undefined
                                  )
                                }
                                className="px-2 py-1 rounded text-[11px] bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border"
                              >
                                Locate
                              </button>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
