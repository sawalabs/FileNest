import React, { useState, useMemo, useEffect } from "react";
import {
  FolderPlus,
  ArrowRightLeft,
  CheckCircle2,
  AlertTriangle,
  Trash2,
  Pencil,
  Check,
  X,
  Send,
  ShieldCheck,
  Folder,
  FolderOpen,
  FolderTree,
  ChevronDown,
  ChevronRight,
  Search,
} from "lucide-react";
import { formatBytes, getFolderByMode, getTopProjectFolder, cn, type GroupingMode } from "@/lib/utils";
import { ApiService } from "@/services/api";
import type { ProposedChangeItem } from "@/types";

interface OrganizationChangePlanProps {
  planId: string;
  items: ProposedChangeItem[];
  onUpdateItemDestination: (itemId: string, newDestination: string) => Promise<void>;
  onDeleteItem: (itemId: string) => Promise<void>;
  onDeleteItems?: (itemIds: string[]) => Promise<void>;
  onSubmitPlan: () => Promise<void>;
  onDiscardPlan: () => void;
  isSubmitting: boolean;
}

interface FolderGroup<T> {
  folderPath: string;
  folderName: string;
  items: T[];
  totalBytes: number;
}

export const OrganizationChangePlan: React.FC<OrganizationChangePlanProps> = ({
  planId,
  items,
  onUpdateItemDestination,
  onDeleteItem,
  onDeleteItems,
  onSubmitPlan,
  onDiscardPlan,
  isSubmitting,
}) => {
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [isUpdating, setIsUpdating] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [isPruningExcluded, setIsPruningExcluded] = useState(false);

  // Selected item IDs state
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(() => {
    return new Set(items.map((i) => i.item_id || i.source_relative_path || i.destination_relative_path));
  });

  // Collapsed folders state (all expanded by default)
  const [collapsedFolders, setCollapsedFolders] = useState<Set<string>>(new Set());

  // Sync selectedItemIds when items change
  useEffect(() => {
    setSelectedItemIds((prev) => {
      const next = new Set<string>();
      for (const item of items) {
        const id = item.item_id || item.source_relative_path || item.destination_relative_path;
        if (prev.size === 0 || prev.has(id)) {
          next.add(id);
        }
      }
      return next;
    });
  }, [items]);

  const startEdit = (item: ProposedChangeItem) => {
    if (!item.item_id) return;
    setEditingItemId(item.item_id);
    setEditValue(item.destination_relative_path);
  };

  const cancelEdit = () => {
    setEditingItemId(null);
    setEditValue("");
  };

  const handleSaveEdit = async (itemId: string) => {
    if (!editValue.trim()) return;
    setIsUpdating(true);
    try {
      await onUpdateItemDestination(itemId, editValue.trim());
      setEditingItemId(null);
    } finally {
      setIsUpdating(false);
    }
  };

  // Filter items by search
  const filteredItems = useMemo(() => {
    if (!searchFilter.trim()) return items;
    const q = searchFilter.toLowerCase();
    return items.filter(
      (it) =>
        (it.source_relative_path && it.source_relative_path.toLowerCase().includes(q)) ||
        it.destination_relative_path.toLowerCase().includes(q)
    );
  }, [items, searchFilter]);

  // Grouping mode state: "project" (default), "leaf", "top", or "flat"
  const [groupingMode, setGroupingMode] = useState<GroupingMode>("project");

  // Group items by parent folder based on groupingMode
  const groupedItems = useMemo<FolderGroup<ProposedChangeItem>[]>(() => {
    const map = new Map<string, FolderGroup<ProposedChangeItem>>();
    for (const item of filteredItems) {
      const rawPath = item.source_relative_path || item.destination_relative_path || "";
      const folder = getFolderByMode(rawPath, groupingMode);
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
        const p = (it.source_relative_path || it.destination_relative_path || "").replace(/\\/g, "/");
        return p.startsWith(topParent + "/") || p === topParent;
      })
      .map((it) => it.item_id || it.source_relative_path || it.destination_relative_path);

    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      const isAnySelected = matchingItemIds.some((id) => next.has(id));
      if (isAnySelected) {
        matchingItemIds.forEach((id) => next.delete(id));
      } else {
        matchingItemIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const allFilteredItemIds = useMemo(() => {
    return filteredItems.map((i) => i.item_id || i.source_relative_path || i.destination_relative_path);
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

  // Clear folder action
  const handleClearFolder = async (folderItemIds: string[]) => {
    const validIds = folderItemIds.filter((id) => items.some((it) => it.item_id === id));
    if (validIds.length === 0) return;
    if (onDeleteItems) {
      await onDeleteItems(validIds);
    } else {
      await Promise.all(validIds.map((id) => onDeleteItem(id)));
    }
  };

  // Submit with auto-pruning of excluded items
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
  const activeSelectedCount = items.filter((it) =>
    selectedItemIds.has(it.item_id || it.source_relative_path || it.destination_relative_path)
  ).length;

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-border/60">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <span>Proposed Change Plan (Draft #{planId.slice(0, 8)})</span>
            <span className="text-[11px] font-normal text-muted-foreground">
              • {groupedItems.length} {groupedItems.length === 1 ? "folder" : "folders"}
            </span>
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            File dikelompokkan per direktori. Centang atau kosongkan folder untuk menyertakan/mengecualikan berkas dari rencana organisasi.
          </p>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          <button
            onClick={onDiscardPlan}
            className="px-3 py-1.5 text-xs font-medium rounded-lg border border-border bg-secondary text-secondary-foreground hover:bg-secondary/80 transition-colors"
          >
            Discard
          </button>
          <button
            onClick={handleSubmitPlanWithExclusions}
            disabled={isSubmitting || isPruningExcluded || hasConflicts || activeSelectedCount === 0}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm cursor-pointer"
          >
            <Send size={13} className={isSubmitting || isPruningExcluded ? "animate-spin" : ""} />
            <span>
              {isSubmitting || isPruningExcluded
                ? "Submitting..."
                : `Submit to Review Changes (${activeSelectedCount})`}
            </span>
          </button>
        </div>
      </div>

      {/* Search Filter Bar & Grouping Mode */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="relative flex-1 min-w-[200px]">
          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            value={searchFilter}
            onChange={(e) => setSearchFilter(e.target.value)}
            placeholder="Cari lokasi sumber atau destinasi target..."
            className="w-full pl-8 pr-3 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Folder Grouping Level Selector */}
        <div className="flex items-center gap-1.5 pl-2 border-l border-border/70">
          <FolderTree size={13} className="text-muted-foreground shrink-0" />
          <select
            value={groupingMode}
            onChange={(e) => setGroupingMode(e.target.value as GroupingMode)}
            className="px-2 py-1.5 rounded-md border border-border bg-background text-[11px] font-medium text-foreground focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer"
            title="Tingkat pengelompokan folder"
          >
            <option value="project">Folder Proyek (Top-Level)</option>
            <option value="leaf">Per Subfolder Rinci (Leaf)</option>
            <option value="top">Folder Terluar (Level 1)</option>
            <option value="flat">Tanpa Grup (Daftar File)</option>
          </select>
        </div>
      </div>

      {/* Safety Notice */}
      <div className="flex items-center gap-2 p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 text-xs text-blue-700 dark:text-blue-300">
        <ShieldCheck size={16} className="shrink-0" />
        <span>
          Rencana organisasi bersifat rekomendasi aman. Berkas hanya dipindahkan atau dibuat direktorinya setelah disetujui di Review Changes.
        </span>
      </div>

      {/* Conflict Alert if any */}
      {hasConflicts && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-xs text-destructive">
          <AlertTriangle size={16} className="shrink-0" />
          <span>
            Beberapa operasi memiliki konflik (tabrakan nama tujuan). Edit jalur tujuan atau hapus item sebelum submit.
          </span>
        </div>
      )}

      {/* Operations Table with Folder Grouping */}
      <div className="rounded-lg border border-border overflow-hidden bg-card flex flex-col shadow-2xs">
        {filteredItems.length === 0 ? (
          <div className="py-8 text-center text-xs text-muted-foreground">
            Tidak ada operasi yang sesuai dalam rencana ini.
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
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
                  <th className="py-2.5 px-3 sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Operation</th>
                  <th className="py-2.5 px-3 sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Source Location</th>
                  <th className="py-2.5 px-3 sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Target Destination</th>
                  <th className="py-2.5 px-3 text-right sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Size</th>
                  <th className="py-2.5 px-3 text-center sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Status</th>
                  <th className="py-2.5 px-3 text-right sticky top-0 bg-muted/95 backdrop-blur-xs z-20">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {groupedItems.map((group) => {
                  const isCollapsed = collapsedFolders.has(group.folderPath);
                  const folderItemIds = group.items.map(
                    (i) => i.item_id || i.source_relative_path || i.destination_relative_path
                  );
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
                          colSpan={6}
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
                                ({group.items.length} {group.items.length === 1 ? "operasi" : "operasi"} • {formatBytes(group.totalBytes)})
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
                                onClick={() => handleClearFolder(folderItemIds)}
                                className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border border-transparent hover:border-destructive/20"
                                title="Hapus semua operasi dalam folder ini dari rencana"
                              >
                                <Trash2 size={11} />
                                <span>Clear</span>
                              </button>
                            </div>
                          </div>
                        </td>
                        <td className="py-2 px-3 text-right">
                          {/* spacer */}
                        </td>
                      </tr>

                      {/* Item Rows */}
                      {!isCollapsed &&
                        group.items.map((item, idx) => {
                          const itemId = item.item_id || item.source_relative_path || item.destination_relative_path;
                          const isIncluded = selectedItemIds.has(itemId);
                          const isEditing = editingItemId === item.item_id;
                          const isConflict = item.status === "conflict";

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
                              {/* Row checkbox */}
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
                                {item.operation === "create_directory" ? (
                                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400">
                                    <FolderPlus size={12} />
                                    Create Dir
                                  </span>
                                ) : (
                                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400">
                                    <ArrowRightLeft size={12} />
                                    Move File
                                  </span>
                                )}
                              </td>

                              <td
                                className={cn(
                                  "py-2.5 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-[180px]",
                                  !isIncluded && "line-through"
                                )}
                                title={item.source_relative_path || "-"}
                              >
                                {item.source_relative_path || (
                                  <span className="text-muted-foreground/50">New Directory</span>
                                )}
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
                                      onClick={() => item.item_id && handleSaveEdit(item.item_id)}
                                      disabled={isUpdating}
                                      className="p-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
                                      title="Simpan perubahan"
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
                                        "text-foreground font-medium truncate max-w-[200px]",
                                        !isIncluded && "text-muted-foreground line-through"
                                      )}
                                      title={item.destination_relative_path}
                                    >
                                      {item.destination_relative_path}
                                    </span>
                                    {item.item_id && isIncluded && (
                                      <button
                                        onClick={() => startEdit(item)}
                                        className="opacity-0 group-hover:opacity-100 p-0.5 text-muted-foreground hover:text-foreground transition-opacity"
                                        title="Edit jalur tujuan"
                                      >
                                        <Pencil size={12} />
                                      </button>
                                    )}
                                  </div>
                                )}
                              </td>

                              <td className="py-2.5 px-3 text-right font-medium text-foreground">
                                {item.size_bytes > 0 ? formatBytes(item.size_bytes) : "-"}
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
                                ) : (
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/15 text-emerald-600 dark:text-emerald-400">
                                    <CheckCircle2 size={11} />
                                    Ready
                                  </span>
                                )}
                              </td>

                              <td className="py-2.5 px-3 text-right">
                                {item.item_id && (
                                  <button
                                    onClick={() => item.item_id && onDeleteItem(item.item_id)}
                                    className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                                    title="Hapus operasi ini dari rencana"
                                  >
                                    <Trash2 size={13} />
                                  </button>
                                )}
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
