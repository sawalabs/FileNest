import React, { useState, useMemo, useEffect, useRef } from "react";
import {
  CheckCircle2,
  AlertTriangle,
  MinusCircle,
  Pencil,
  Trash2,
  Check,
  X,
  Send,
  ShieldCheck,
  Search,
  Sparkles,
  RefreshCw,
  Folder,
  FolderOpen,
  FolderTree,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { formatBytes, getFolderByMode, getTopProjectFolder, cn, type GroupingMode } from "@/lib/utils";
import { FileIcon } from "@/features/files/FileIcon";
import { ApiService } from "@/services/api";
import type { SmartRenamePreviewItem, FileCategory, BatchOCRJobStatus } from "@/types";

interface SmartRenamePreviewTableProps {
  planId: string;
  items: SmartRenamePreviewItem[];
  onUpdateProposedName: (itemId: string, newDestinationPath: string) => Promise<void>;
  onDeleteItem: (itemId: string) => Promise<void>;
  onDeleteItems?: (itemIds: string[]) => Promise<void>;
  onSubmitPlan: () => Promise<void>;
  onDiscardPlan: () => void;
  onRefreshPlan?: () => Promise<void>;
  isSubmitting: boolean;
}

interface FolderGroup<T> {
  folderPath: string;
  folderName: string;
  items: T[];
  totalBytes: number;
}

export const SmartRenamePreviewTable: React.FC<SmartRenamePreviewTableProps> = ({
  planId,
  items,
  onUpdateProposedName,
  onDeleteItem,
  onDeleteItems,
  onSubmitPlan,
  onDiscardPlan,
  onRefreshPlan,
  isSubmitting,
}) => {
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "ready" | "conflict" | "unchanged">("all");

  // Selection & Exclusion state per item
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(() => {
    return new Set(items.map((i) => i.item_id || i.source_relative_path));
  });

  // Collapsed folders state (all expanded by default)
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());
  const [isPruningExcluded, setIsPruningExcluded] = useState(false);

  // Sync selectedItemIds when items change
  useEffect(() => {
    setSelectedItemIds((prev) => {
      const next = new Set<string>();
      for (const item of items) {
        const id = item.item_id || item.source_relative_path;
        if (prev.size === 0 || prev.has(id)) {
          next.add(id);
        }
      }
      return next;
    });
  }, [items]);

  // Single Item & Batch Background OCR states
  const [analyzingItemId, setAnalyzingItemId] = useState<string | null>(null);
  const [isBatchRunning, setIsBatchRunning] = useState(false);
  const [batchStatus, setBatchStatus] = useState<BatchOCRJobStatus | null>(null);
  const [ocrMessage, setOcrMessage] = useState<string | null>(null);
  const pollIntervalRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }
    };
  }, []);

  const handleRunSingleItemOCR = async (item: SmartRenamePreviewItem) => {
    if (!item.item_id) return;
    setAnalyzingItemId(item.item_id);
    setOcrMessage(null);
    try {
      const res = await ApiService.analyzeSmartRenameItemOCR(planId, item.item_id);
      if (res.success) {
        await onUpdateProposedName(item.item_id, res.destination_relative_path);
        setOcrMessage(`OCR berhasil untuk ${item.original_name} → ${res.proposed_name}`);
      } else {
        setOcrMessage(res.error_message || "OCR tidak mendeteksi teks terbaca");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memproses OCR";
      setOcrMessage(msg);
    } finally {
      setAnalyzingItemId(null);
      setTimeout(() => setOcrMessage(null), 5000);
    }
  };

  const handleStartBatchOCR = async () => {
    try {
      setIsBatchRunning(true);
      setOcrMessage("Memulai ekstraksi OCR & AI di latar belakang...");
      const initial = await ApiService.startBatchOCRBackground(planId);
      setBatchStatus(initial);

      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
      }

      pollIntervalRef.current = window.setInterval(async () => {
        try {
          const cur = await ApiService.getBatchOCRStatus(planId);
          setBatchStatus(cur);
          if (!cur.is_running) {
            if (pollIntervalRef.current) {
              clearInterval(pollIntervalRef.current);
              pollIntervalRef.current = null;
            }
            setIsBatchRunning(false);
            setOcrMessage(
              `Batch OCR selesai: ${cur.processed_items}/${cur.total_items} diproses (${cur.error_count} gagal)`
            );
            if (onRefreshPlan) {
              await onRefreshPlan();
            }
          }
        } catch {
          // ignore transient poll error
        }
      }, 1500);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal memulai Batch OCR";
      setOcrMessage(msg);
      setIsBatchRunning(false);
    }
  };

  const startEdit = (item: SmartRenamePreviewItem) => {
    if (!item.item_id) return;
    setEditingItemId(item.item_id);
    setEditValue(item.proposed_name);
  };

  const cancelEdit = () => {
    setEditingItemId(null);
    setEditValue("");
  };

  const handleSaveEdit = async (item: SmartRenamePreviewItem) => {
    if (!item.item_id || !editValue.trim()) return;
    setIsUpdating(true);
    try {
      const parts = item.destination_relative_path.split("/");
      parts[parts.length - 1] = editValue.trim();
      const newDest = parts.join("/");
      await onUpdateProposedName(item.item_id, newDest);
      setEditingItemId(null);
    } finally {
      setIsUpdating(false);
    }
  };

  // Filtered Items
  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      if (statusFilter !== "all" && item.status !== statusFilter) return false;
      if (searchFilter.trim()) {
        const query = searchFilter.toLowerCase();
        const matchesOriginal = item.original_name.toLowerCase().includes(query);
        const matchesProposed = item.proposed_name.toLowerCase().includes(query);
        if (!matchesOriginal && !matchesProposed) return false;
      }
      return true;
    });
  }, [items, searchFilter, statusFilter]);

  // Grouping mode state: "project" (default), "leaf", "top", or "flat"
  const [groupingMode, setGroupingMode] = useState<GroupingMode>("project");

  // Group items by directory based on groupingMode
  const groupedItems = useMemo<FolderGroup<SmartRenamePreviewItem>[]>(() => {
    const map = new Map<string, FolderGroup<SmartRenamePreviewItem>>();
    for (const item of filteredItems) {
      const folder = getFolderByMode(item.source_relative_path, groupingMode);
      if (!map.has(folder)) {
        const parts = folder === "/" ? [] : folder.split("/").filter(Boolean);
        const folderName = folder === "/" ? "Root Directory" : parts[parts.length - 1];
        map.set(folder, {
          folderPath: folder,
          folderName,
          items: [],
          totalBytes: 0,
        });
      }
      const g = map.get(folder)!;
      g.items.push(item);
      g.totalBytes += item.size_bytes || 0;
    }
    return Array.from(map.values()).sort((a, b) => {
      if (a.folderPath === "/") return -1;
      if (b.folderPath === "/") return 1;
      return a.folderPath.localeCompare(b.folderPath);
    });
  }, [filteredItems, groupingMode]);

  // Selection toggle handlers
  const toggleItemSelection = (id: string) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleFolderSelection = (folderItemIds: string[], currentlyAllSelected: boolean) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (currentlyAllSelected) {
        folderItemIds.forEach((id) => next.delete(id));
      } else {
        folderItemIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  // Exclude or include an entire parent project folder and all its nested subfolders
  const handleExcludeParentProject = (folderPath: string) => {
    const topParent = getTopProjectFolder(folderPath);
    const matchingItemIds = items
      .filter((it) => {
        const p = it.source_relative_path.replace(/\\/g, "/");
        return p.startsWith(topParent + "/") || p === topParent;
      })
      .map((it) => it.item_id || it.source_relative_path);

    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      const isAnySelected = matchingItemIds.some((id) => next.has(id));
      if (isAnySelected) {
        matchingItemIds.forEach((id) => next.delete(id));
        setOcrMessage(`Seluruh ${matchingItemIds.length} berkas dalam induk "${topParent}" telah dikecualikan.`);
      } else {
        matchingItemIds.forEach((id) => next.add(id));
        setOcrMessage(`Seluruh ${matchingItemIds.length} berkas dalam induk "${topParent}" telah disertakan.`);
      }
      return next;
    });
  };

  const allFilteredItemIds = useMemo(() => {
    return filteredItems.map((i) => i.item_id || i.source_relative_path);
  }, [filteredItems]);

  const isAllFilteredSelected =
    allFilteredItemIds.length > 0 &&
    allFilteredItemIds.every((id) => selectedItemIds.has(id));

  const toggleSelectAllFiltered = () => {
    if (isAllFilteredSelected) {
      setSelectedItemIds((prev) => {
        const next = new Set(prev);
        allFilteredItemIds.forEach((id) => next.delete(id));
        return next;
      });
    } else {
      setSelectedItemIds((prev) => {
        const next = new Set(prev);
        allFilteredItemIds.forEach((id) => next.add(id));
        return next;
      });
    }
  };

  const toggleFolderCollapse = (folderPath: string) => {
    setCollapsedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderPath)) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
  };

  // Clear an entire folder from the plan in one click
  const handleClearFolder = async (folderPath: string, folderItemIds: string[]) => {
    const validIds = folderItemIds.filter((id) => items.some((it) => it.item_id === id));
    if (validIds.length === 0) return;
    try {
      if (onDeleteItems) {
        await onDeleteItems(validIds);
      } else {
        await Promise.all(validIds.map((id) => onDeleteItem(id)));
      }
      setOcrMessage(`Seluruh berkas dalam folder "${folderPath}" telah dibersihkan dari rencana.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal membersihkan folder dari rencana";
      setOcrMessage(msg);
    }
  };

  // Submit only selected/included items: automatically prune excluded items from draft plan
  const handleSubmitPlanWithExclusions = async () => {
    const excluded = items.filter(
      (it) => it.item_id && !selectedItemIds.has(it.item_id)
    );
    if (excluded.length > 0) {
      setIsPruningExcluded(true);
      try {
        const excludedIds = excluded.map((it) => it.item_id as string);
        if (onDeleteItems) {
          await onDeleteItems(excludedIds);
        } else {
          await Promise.all(
            excludedIds.map((id) => ApiService.deletePlanItem(planId, id))
          );
        }
      } catch (err) {
        console.error("Gagal membersihkan file yang dikecualikan sebelum submit:", err);
      } finally {
        setIsPruningExcluded(false);
      }
    }
    await onSubmitPlan();
  };

  const hasConflicts = items.some((it) => it.status === "conflict");
  const activeSelectedItems = items.filter(
    (it) => it.status === "ready" && selectedItemIds.has(it.item_id || it.source_relative_path)
  );

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4 flex flex-col">
      {/* Sticky Card Header */}
      <div className="sticky top-0 z-30 bg-card/95 backdrop-blur-xs pb-3 border-b border-border/60 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
              <span>Rename Preview & Proposed Plan (Draft #{planId.slice(0, 8)})</span>
              <span className="text-[11px] font-normal text-muted-foreground">
                • {groupedItems.length} {groupedItems.length === 1 ? "folder" : "folders"}
              </span>
            </h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              File dikelompokkan per direktori. Centang atau kosongkan folder untuk menyertakan/mengecualikan berkas dari rencana.
            </p>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center flex-wrap gap-2">
            <button
              type="button"
              onClick={handleStartBatchOCR}
              disabled={isBatchRunning}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all",
                isBatchRunning
                  ? "border-primary/50 bg-primary/10 text-primary animate-pulse"
                  : "border-border bg-card text-foreground hover:bg-muted/70 shadow-2xs"
              )}
              title="Ekstrak teks gambar dengan PaddleOCR untuk semua file di latar belakang (non-blocking)"
            >
              {isBatchRunning ? (
                <RefreshCw size={12} className="animate-spin text-primary" />
              ) : (
                <Sparkles size={12} className="text-primary" />
              )}
              <span>
                {isBatchRunning
                  ? `OCR di Background (${batchStatus?.processed_items || 0}/${batchStatus?.total_items || items.length})...`
                  : "Jalankan OCR Semua di Background"}
              </span>
            </button>

            <button
              onClick={onDiscardPlan}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
            >
              Discard
            </button>
            <button
              onClick={handleSubmitPlanWithExclusions}
              disabled={isSubmitting || isPruningExcluded || hasConflicts || activeSelectedItems.length === 0}
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm cursor-pointer"
            >
              <Send size={13} className={isSubmitting || isPruningExcluded ? "animate-spin" : ""} />
              <span>
                {isSubmitting || isPruningExcluded
                  ? "Submitting..."
                  : `Submit to Review Changes (${activeSelectedItems.length})`}
              </span>
            </button>
          </div>
        </div>

        {ocrMessage && (
          <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-primary/10 border border-primary/20 text-xs text-primary animate-in fade-in">
            <Sparkles size={13} className="shrink-0" />
            <span className="flex-1 font-medium">{ocrMessage}</span>
            <button onClick={() => setOcrMessage(null)} className="p-0.5 hover:opacity-80">
              <X size={12} />
            </button>
          </div>
        )}

        {/* Search & Status Filter Bar */}
        <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/50 text-xs">
          <div className="relative flex-1 min-w-[180px]">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              value={searchFilter}
              onChange={(e) => setSearchFilter(e.target.value)}
              placeholder="Cari nama asli, usulan, atau path folder..."
              className="w-full pl-8 pr-3 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setStatusFilter("all")}
              className={cn(
                "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors",
                statusFilter === "all"
                  ? "bg-primary text-primary-foreground shadow-2xs"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              Semua ({items.length})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("ready")}
              className={cn(
                "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors",
                statusFilter === "ready"
                  ? "bg-primary text-primary-foreground shadow-2xs"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              Ready ({items.filter((i) => i.status === "ready").length})
            </button>
            <button
              type="button"
              onClick={() => setStatusFilter("unchanged")}
              className={cn(
                "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors",
                statusFilter === "unchanged"
                  ? "bg-primary text-primary-foreground shadow-2xs"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              )}
            >
              Unchanged ({items.filter((i) => i.status === "unchanged").length})
            </button>
            {hasConflicts && (
              <button
                type="button"
                onClick={() => setStatusFilter("conflict")}
                className={cn(
                  "px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors",
                  statusFilter === "conflict"
                    ? "bg-destructive text-destructive-foreground shadow-2xs"
                    : "bg-destructive/10 text-destructive hover:bg-destructive/20"
                )}
              >
                Konflik ({items.filter((i) => i.status === "conflict").length})
              </button>
            )}

            {/* Folder Grouping Level Selector */}
            <div className="flex items-center gap-1.5 pl-2 ml-1 border-l border-border/70">
              <FolderTree size={13} className="text-muted-foreground shrink-0" />
              <select
                value={groupingMode}
                onChange={(e) => setGroupingMode(e.target.value as GroupingMode)}
                className="px-2 py-1 rounded-md border border-border bg-background text-[11px] font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
                title="Tingkat pengelompokan folder"
              >
                <option value="project">Folder Proyek (Top-Level)</option>
                <option value="leaf">Per Subfolder Rinci (Leaf)</option>
                <option value="top">Folder Terluar (Level 1)</option>
                <option value="flat">Tanpa Grup (Daftar File)</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Safety Notice */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-blue-700 dark:text-blue-300">
        <ShieldCheck size={16} className="shrink-0" />
        <span>
          Berkas tidak langsung diubah namanya. Centang kotak folder untuk menyertakan atau mengecualikan berkas. Perubahan hanya dieksekusi setelah disetujui di Review Changes.
        </span>
      </div>

      {/* Conflicts warning */}
      {hasConflicts && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
          <AlertTriangle size={16} className="shrink-0" />
          <span>
            Ditemukan konflik penamaan. Edit nama baru yang berkonflik atau bersihkan berkas tersebut dari rencana untuk melanjutkan.
          </span>
        </div>
      )}

      {/* Table Container with Confined Height and Sticky Header */}
      <div className="rounded-lg border border-border overflow-hidden bg-card flex flex-col max-h-[580px] shadow-2xs">
        {filteredItems.length === 0 ? (
          <div className="py-12 text-center text-xs text-muted-foreground space-y-1">
            <p className="font-semibold text-foreground">Tidak ada file yang cocok</p>
            <p className="text-[11px]">Coba sesuaikan kata kunci pencarian atau filter status.</p>
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead className="sticky top-0 z-20 bg-muted/95 backdrop-blur-xs border-b border-border text-muted-foreground font-semibold shadow-2xs">
                <tr>
                  <th className="py-2.5 px-3 w-10 text-center sticky top-0 bg-muted/95 backdrop-blur-xs z-20">
                    <input
                      type="checkbox"
                      checked={isAllFilteredSelected}
                      onChange={toggleSelectAllFiltered}
                      className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                      title={isAllFilteredSelected ? "Deselect All" : "Select All"}
                    />
                  </th>
                  <th className="py-2.5 px-3 w-10 text-center sticky top-0 bg-muted/95 backdrop-blur-xs z-20">#</th>
                  <th className="py-2.5 px-3 sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Original Filename</th>
                  <th className="py-2.5 px-3 sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Proposed New Filename</th>
                  <th className="py-2.5 px-3 text-right sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Size</th>
                  <th className="py-2.5 px-3 text-center sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Status</th>
                  <th className="py-2.5 px-3 text-right sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {groupedItems.map((group) => {
                  const isCollapsed = collapsedFolders.has(group.folderPath);
                  const folderItemIds = group.items.map((i) => i.item_id || i.source_relative_path);
                  const selectedCount = folderItemIds.filter((id) => selectedItemIds.has(id)).length;
                  const isAllSelected = selectedCount === folderItemIds.length && folderItemIds.length > 0;
                  const isIndeterminate = selectedCount > 0 && selectedCount < folderItemIds.length;
                  const isNoneSelected = selectedCount === 0;

                  return (
                    <React.Fragment key={group.folderPath}>
                      {/* Folder Group Header Row */}
                      <tr className="bg-muted/65 hover:bg-muted/80 transition-colors border-y border-border/80 sticky top-[37px] z-10 backdrop-blur-xs select-none">
                        <td
                          className="py-2 px-3 text-center"
                          onClick={(e) => e.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            checked={isAllSelected}
                            ref={(el) => {
                              if (el) el.indeterminate = isIndeterminate;
                            }}
                            onChange={() => toggleFolderSelection(folderItemIds, isAllSelected)}
                            className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                            title={
                              isAllSelected
                                ? "Kecualikan seluruh berkas dalam folder ini dari plan"
                                : "Sertakan seluruh berkas dalam folder ini di plan"
                            }
                          />
                        </td>
                        <td
                          colSpan={5}
                          className="py-2 px-2 cursor-pointer"
                          onClick={() => toggleFolderCollapse(group.folderPath)}
                        >
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 flex-wrap">
                              <button
                                type="button"
                                className="text-muted-foreground hover:text-foreground p-0.5 rounded transition-transform"
                                title={isCollapsed ? "Buka folder" : "Tutup folder"}
                              >
                                {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                              </button>
                              <div className="flex items-center gap-1.5 font-medium text-foreground text-xs">
                                {isCollapsed ? (
                                  <Folder size={15} className="text-amber-500 shrink-0" />
                                ) : (
                                  <FolderOpen size={15} className="text-amber-500 shrink-0" />
                                )}
                                <span className="font-semibold font-mono">{group.folderPath}</span>
                              </div>
                              <span className="text-[11px] text-muted-foreground">
                                ({group.items.length} {group.items.length === 1 ? "berkas" : "berkas"} • {formatBytes(group.totalBytes)})
                              </span>
                              <span
                                className={cn(
                                  "text-[10px] px-2 py-0.5 rounded font-medium border",
                                  isNoneSelected
                                    ? "bg-muted text-muted-foreground border-border"
                                    : isAllSelected
                                    ? "bg-secondary text-secondary-foreground border-border"
                                    : "bg-primary/10 text-primary border-primary/20"
                                )}
                              >
                                {selectedCount} / {group.items.length} disertakan {isNoneSelected && "(Dikecualikan)"}
                              </span>
                            </div>

                            {/* Folder Actions: Clear Folder, Exclude Parent */}
                            <div
                              className="flex items-center gap-1.5"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {group.folderPath !== "/" && (
                                <button
                                  type="button"
                                  onClick={() => handleExcludeParentProject(group.folderPath)}
                                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted transition-colors border border-border/60"
                                  title={`Kecualikan atau sertakan semua berkas dalam induk '${getTopProjectFolder(group.folderPath)}'`}
                                >
                                  <FolderTree size={11} />
                                  <span>Kecualikan Induk ({getTopProjectFolder(group.folderPath).split("/").pop()})</span>
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleClearFolder(group.folderPath, folderItemIds)}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border border-transparent hover:border-destructive/20"
                                title="Hapus semua berkas dalam folder ini dari rencana"
                              >
                                <Trash2 size={11} />
                                <span>Clear</span>
                              </button>
                            </div>
                          </div>
                        </td>
                        <td className="py-2 px-3 text-right">
                          {/* action spacer */}
                        </td>
                      </tr>

                      {/* Folder Item Rows */}
                      {!isCollapsed &&
                        group.items.map((item, idx) => {
                          const itemId = item.item_id || item.source_relative_path;
                          const isIncluded = selectedItemIds.has(itemId);
                          const isEditing = editingItemId === item.item_id;
                          const isConflict = item.status === "conflict";
                          const isUnchanged = item.status === "unchanged";
                          const isOcrEligible = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"].includes(
                            (item.extension || "").toLowerCase()
                          );

                          return (
                            <tr
                              key={item.item_id || `${group.folderPath}-${idx}`}
                              className={cn(
                                "transition-colors",
                                !isIncluded
                                  ? "opacity-50 bg-muted/15"
                                  : isConflict
                                  ? "bg-destructive/5 hover:bg-destructive/10"
                                  : "hover:bg-muted/30"
                              )}
                            >
                              {/* Checkbox item */}
                              <td className="py-2.5 px-3 text-center">
                                <input
                                  type="checkbox"
                                  checked={isIncluded}
                                  onChange={() => toggleItemSelection(itemId)}
                                  className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                                  title={isIncluded ? "Kecualikan dari rencana" : "Sertakan dalam rencana"}
                                />
                              </td>

                              <td className="py-2.5 px-3 text-center text-muted-foreground font-mono text-[11px]">
                                {item.sequence_no}
                              </td>

                              <td className="py-2.5 px-3">
                                <div className="flex items-center gap-2">
                                  <FileIcon
                                    itemType="file"
                                    category={item.category as FileCategory}
                                    extension={item.extension}
                                    size={15}
                                  />
                                  {(() => {
                                    const normalizedSrc = item.source_relative_path.replace(/\\/g, "/");
                                    const normalizedGrp = group.folderPath.replace(/\\/g, "/");
                                    let subRel = "";
                                    if (normalizedGrp !== "/" && normalizedSrc.startsWith(normalizedGrp + "/")) {
                                      const afterGrp = normalizedSrc.slice(normalizedGrp.length + 1);
                                      const parts = afterGrp.split("/");
                                      if (parts.length > 1) {
                                        subRel = parts.slice(0, -1).join("/");
                                      }
                                    }
                                    return (
                                      <div className="min-w-0 flex flex-col">
                                        <span
                                          className={cn(
                                            "font-medium text-foreground truncate max-w-xs",
                                            !isIncluded && "line-through text-muted-foreground"
                                          )}
                                          title={item.original_name}
                                        >
                                          {item.original_name}
                                        </span>
                                        {subRel && (
                                          <span
                                            className="text-[10px] text-muted-foreground/75 font-mono truncate max-w-xs"
                                            title={item.source_relative_path}
                                          >
                                            📁 {subRel}
                                          </span>
                                        )}
                                      </div>
                                    );
                                  })()}
                                </div>
                              </td>

                              <td className="py-2.5 px-3 font-mono text-[11px]">
                                {isEditing ? (
                                  <div className="flex items-center gap-1">
                                    <input
                                      type="text"
                                      value={editValue}
                                      onChange={(e) => setEditValue(e.target.value)}
                                      className="px-2 py-1 bg-card border border-primary rounded text-foreground focus:outline-none focus:ring-1 focus:ring-primary w-full"
                                    />
                                    <button
                                      onClick={() => handleSaveEdit(item)}
                                      disabled={isUpdating}
                                      className="p-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
                                      title="Simpan nama baru"
                                    >
                                      <Check size={12} />
                                    </button>
                                    <button
                                      onClick={cancelEdit}
                                      className="p-1 rounded bg-muted text-muted-foreground hover:bg-muted/80"
                                      title="Batal"
                                    >
                                      <X size={12} />
                                    </button>
                                  </div>
                                ) : (
                                  <div className="flex items-center justify-between gap-1 group">
                                    <span
                                      className={cn(
                                        "truncate max-w-xs",
                                        !isIncluded
                                          ? "text-muted-foreground line-through italic"
                                          : isUnchanged
                                          ? "text-muted-foreground italic"
                                          : isConflict
                                          ? "text-destructive font-semibold"
                                          : "text-foreground font-semibold"
                                      )}
                                      title={item.proposed_name}
                                    >
                                      {item.proposed_name}
                                    </span>
                                    {item.item_id && !isUnchanged && isIncluded && (
                                      <button
                                        onClick={() => startEdit(item)}
                                        className="opacity-0 group-hover:opacity-100 p-0.5 text-muted-foreground hover:text-foreground transition-opacity"
                                        title="Edit nama usulan"
                                      >
                                        <Pencil size={12} />
                                      </button>
                                    )}
                                  </div>
                                )}
                              </td>

                              <td className="py-2.5 px-3 text-right text-muted-foreground">
                                {formatBytes(item.size_bytes)}
                              </td>

                              <td className="py-2.5 px-3 text-center">
                                {!isIncluded ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground border border-border">
                                    Dikecualikan
                                  </span>
                                ) : isConflict ? (
                                  <span
                                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold bg-destructive/15 text-destructive"
                                    title={item.conflict_reason || "Conflict"}
                                  >
                                    <AlertTriangle size={11} />
                                    Konflik
                                  </span>
                                ) : isUnchanged ? (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
                                    <MinusCircle size={11} />
                                    Sama
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 size={11} />
                                    Ready
                                  </span>
                                )}
                              </td>

                              <td className="py-2.5 px-3 text-right">
                                <div className="flex items-center justify-end gap-1.5">
                                  {item.item_id && isOcrEligible && isIncluded && (
                                    <button
                                      type="button"
                                      onClick={() => handleRunSingleItemOCR(item)}
                                      disabled={analyzingItemId === item.item_id || isBatchRunning}
                                      className={cn(
                                        "inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium transition-all",
                                        analyzingItemId === item.item_id
                                          ? "bg-primary/20 text-primary"
                                          : "bg-primary/10 text-primary hover:bg-primary/20 border border-primary/25"
                                      )}
                                      title="Jalankan PaddleOCR & AI pada file ini"
                                    >
                                      {analyzingItemId === item.item_id ? (
                                        <RefreshCw size={11} className="animate-spin" />
                                      ) : (
                                        <Sparkles size={11} />
                                      )}
                                      <span>{analyzingItemId === item.item_id ? "OCR..." : "OCR Rename"}</span>
                                    </button>
                                  )}

                                  {item.item_id && (
                                    <button
                                      onClick={() => item.item_id && onDeleteItem(item.item_id)}
                                      className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                                      title="Hapus berkas ini dari rencana"
                                    >
                                      <Trash2 size={13} />
                                    </button>
                                  )}
                                </div>
                              </td>
                            </tr>
                          );
                        })}
                    </React.Fragment>
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
