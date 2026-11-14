import React, { useEffect, useState, useMemo } from "react";
import {
  RefreshCw,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  FolderInput,
  FilePenLine,
  Trash2,
  FolderPlus,
  Copy,
  FileText,
  Search,
  Check,
  X,
  Layers,
  Sparkles,
  ShieldAlert,
  Loader2,
  ShieldCheck,
  Save,
  ArrowDown,
  Info,
  ChevronDown,
  ChevronUp,
  ChevronRight,
  Folder,
  FolderOpen,
  PanelRight,
  ClipboardCheck,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { usePreferences } from "@/contexts/PreferencesContext";
import { ReviewSummaryCards } from "./ReviewSummaryCards";
import type {
  ChangePlanItemResponse,
  ChangePlanResponse,
  ManagedFolder,
  ExecutionJobResponse,
} from "@/types";
import { cn, getParentFolder } from "@/lib/utils";

type StatusTab = "pending" | "approved" | "executed" | "rejected" | "all";

interface FlattenedChangeItem {
  planId: string;
  planTitle: string;
  planStatus: string;
  managedFolderId: string;
  created_by: string;
  created_at: string;
  item: ChangePlanItemResponse;
}

export const ReviewChangesManager: React.FC = () => {
  const { defaultTableDensity } = usePreferences();
  const isCompact = defaultTableDensity === "compact";
  const rowPad = isCompact ? "py-1 px-2.5" : "py-2.5 px-3";

  const [plans, setPlans] = useState<ChangePlanResponse[]>([]);
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>(new Date().toLocaleTimeString());
  const [activeTab, setActiveTab] = useState<StatusTab>("pending");
  const [selectedPlanId, setSelectedPlanId] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState<string>("all");
  const [selectedOperation, setSelectedOperation] = useState<string>("all");
  const [cardFilter, setCardFilter] = useState<string | undefined>(undefined);
  const [showSummaryCards, setShowSummaryCards] = useState<boolean>(true);
  const [isInspectorOpen, setIsInspectorOpen] = useState<boolean>(true);
  const [selectedItemKeys, setSelectedItemKeys] = useState<Set<string>>(new Set());
  const [feedbackMessage, setFeedbackMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  // Persistent Right Inspector State
  const [activeSelectedItem, setActiveSelectedItem] = useState<FlattenedChangeItem | null>(null);
  const [editingDestPath, setEditingDestPath] = useState<string>("");
  const [isSavingItem, setIsSavingItem] = useState<boolean>(false);
  const [copiedPath, setCopiedPath] = useState<boolean>(false);

  // Execution Confirmation Modal
  const [isConfirmModalOpen, setIsConfirmModalOpen] = useState(false);
  const [plansToExecute, setPlansToExecute] = useState<ChangePlanResponse[]>([]);

  const isItemSelectable = (status: string) =>
    ["draft", "pending_review", "approved"].includes(status);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [fetchedPlans, fetchedFolders] = await Promise.all([
        ApiService.listPlans(),
        ApiService.listFolders(),
      ]);
      setPlans(fetchedPlans);
      setFolders(fetchedFolders);
      setSelectedItemKeys(new Set());
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to load review plans",
      });
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Compute counts for status tabs (exclude empty 0-item plans)
  const tabCounts = useMemo(() => {
    let pending = 0;
    let approved = 0;
    let executed = 0;
    let rejected = 0;
    let all = 0;

    plans.forEach((p) => {
      if (p.items.length === 0) return;
      all++;
      if (p.status === "draft" || p.status === "pending_review") pending++;
      else if (p.status === "approved") approved++;
      else if (p.status === "completed") executed++;
      else if (p.status === "rejected") rejected++;
    });

    return {
      pending,
      approved,
      executed,
      rejected,
      all,
    };
  }, [plans]);

  // Plans belonging to the currently active status tab
  const plansInActiveTab = useMemo(() => {
    const nonEmptyPlans = plans.filter((p) => p.items.length > 0);
    if (activeTab === "pending") {
      return nonEmptyPlans.filter((p) => ["draft", "pending_review"].includes(p.status));
    }
    if (activeTab === "approved") {
      return nonEmptyPlans.filter((p) => p.status === "approved");
    }
    if (activeTab === "executed") {
      return nonEmptyPlans.filter((p) => p.status === "completed");
    }
    if (activeTab === "rejected") {
      return nonEmptyPlans.filter((p) => p.status === "rejected");
    }
    return nonEmptyPlans;
  }, [plans, activeTab]);

  // Currently selected plan object within the active tab (if not "all")
  const currentPlan = useMemo(() => {
    if (selectedPlanId === "all") return null;
    return plansInActiveTab.find((p) => p.id === selectedPlanId) || null;
  }, [plansInActiveTab, selectedPlanId]);

  const tabTotalItems = useMemo(() => {
    return plansInActiveTab.reduce((acc, p) => acc + p.items.length, 0);
  }, [plansInActiveTab]);

  const getPlanConflictCount = (plan: ChangePlanResponse) => {
    return plan.items.filter((i) => i.status === "conflict" || i.conflict_reason).length;
  };

  // Synchronize selectedPlanId when activeTab or plansInActiveTab changes
  useEffect(() => {
    if (plansInActiveTab.length > 0) {
      const exists = plansInActiveTab.some((p) => p.id === selectedPlanId);
      if (!exists) {
        setSelectedPlanId(plansInActiveTab[0].id);
      }
    } else {
      setSelectedPlanId("all");
    }
    setSelectedItemKeys(new Set());
  }, [activeTab, plansInActiveTab]);

  // Compute summary card counts across all items
  const summaryCounts = useMemo(() => {
    let pending = 0;
    let move = 0;
    let rename = 0;
    let deleteCount = 0;
    let conflicts = 0;

    plans.forEach((p) => {
      if (p.status === "draft" || p.status === "pending_review") {
        pending += p.items.length;
      }
      p.items.forEach((item) => {
        if (item.operation === "move") move++;
        else if (item.operation === "rename") rename++;
        else if (item.operation === "delete_to_recycle_bin") deleteCount++;

        if (item.status === "conflict" || item.conflict_reason) {
          conflicts++;
        }
      });
    });

    return { pending, move, rename, deleteCount, conflicts };
  }, [plans]);

  // Flatten change items for high-density 2-column master table
  const allFlattenedItems = useMemo<FlattenedChangeItem[]>(() => {
    const list: FlattenedChangeItem[] = [];
    plans.forEach((plan) => {
      plan.items.forEach((item) => {
        list.push({
          planId: plan.id,
          planTitle: plan.title,
          planStatus: plan.status,
          managedFolderId: plan.managed_folder_id,
          created_by: plan.created_by,
          created_at: plan.created_at,
          item,
        });
      });
    });
    return list;
  }, [plans]);

  // Filter items based on selected plan, active tab, search, folder, card filter, operation
  const filteredItems = useMemo<FlattenedChangeItem[]>(() => {
    return allFlattenedItems.filter((entry) => {
      const { planId, planStatus, managedFolderId, item, planTitle } = entry;

      // 0. Plan filter (per-plan selection)
      if (selectedPlanId !== "all" && planId !== selectedPlanId) {
        return false;
      }

      // 1. Tab filter (always enforce active tab status so executed/rejected plans never linger on Pending)
      if (activeTab === "pending" && !["draft", "pending_review"].includes(planStatus)) {
        return false;
      }
      if (activeTab === "approved" && planStatus !== "approved") {
        return false;
      }
      if (activeTab === "executed" && planStatus !== "completed") {
        return false;
      }
      if (activeTab === "rejected" && planStatus !== "rejected") {
        return false;
      }

      // 2. Folder filter
      if (selectedFolderId !== "all" && managedFolderId !== selectedFolderId) {
        return false;
      }

      // 3. Card filter
      if (cardFilter === "conflict") {
        if (item.status !== "conflict" && !item.conflict_reason) return false;
      } else if (cardFilter === "move") {
        if (item.operation !== "move") return false;
      } else if (cardFilter === "rename") {
        if (item.operation !== "rename") return false;
      } else if (cardFilter === "delete") {
        if (item.operation !== "delete_to_recycle_bin") return false;
      }

      // 4. Operation dropdown filter
      if (selectedOperation !== "all" && item.operation !== selectedOperation) {
        return false;
      }

      // 5. Search query filter
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = planTitle.toLowerCase().includes(q);
        const matchesSource =
          item.source_relative_path && item.source_relative_path.toLowerCase().includes(q);
        const matchesDest =
          item.destination_relative_path &&
          item.destination_relative_path.toLowerCase().includes(q);
        if (!matchesTitle && !matchesSource && !matchesDest) return false;
      }

      return true;
    });
  }, [
    allFlattenedItems,
    selectedPlanId,
    activeTab,
    selectedFolderId,
    cardFilter,
    selectedOperation,
    searchQuery,
  ]);

  // Sync activeSelectedItem with latest data or select first item if none active
  useEffect(() => {
    if (activeSelectedItem) {
      const updated = filteredItems.find(
        (i) => i.item.id === activeSelectedItem.item.id && i.planId === activeSelectedItem.planId
      );
      if (updated) {
        setActiveSelectedItem(updated);
        setEditingDestPath(updated.item.destination_relative_path || "");
        return;
      }
    }
    if (filteredItems.length > 0) {
      setActiveSelectedItem(filteredItems[0]);
      setEditingDestPath(filteredItems[0].item.destination_relative_path || "");
    } else {
      setActiveSelectedItem(null);
      setEditingDestPath("");
    }
  }, [filteredItems]);

  const selectItemForInspection = (entry: FlattenedChangeItem) => {
    setActiveSelectedItem(entry);
    setEditingDestPath(entry.item.destination_relative_path || "");
  };

  // Selection helpers
  const toggleSelectItem = (itemKey: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const next = new Set(selectedItemKeys);
    if (next.has(itemKey)) next.delete(itemKey);
    else next.add(itemKey);
    setSelectedItemKeys(next);
  };

  const selectableFilteredItems = useMemo(
    () => filteredItems.filter((i) => isItemSelectable(i.planStatus)),
    [filteredItems]
  );

  const isSelectionAllowed =
    (activeTab === "pending" || activeTab === "approved" || activeTab === "all") &&
    selectableFilteredItems.length > 0;

  const selectAllFiltered = () => {
    if (!isSelectionAllowed) return;
    if (selectedItemKeys.size === selectableFilteredItems.length) {
      setSelectedItemKeys(new Set());
    } else {
      setSelectedItemKeys(
        new Set(selectableFilteredItems.map((i) => `${i.planId}:${i.item.id}`))
      );
    }
  };

  // Get selected plan IDs from selected item keys
  const targetPlanIdsFromSelection = useMemo(() => {
    const pids = new Set<string>();
    selectedItemKeys.forEach((key) => {
      const [pid] = key.split(":");
      if (pid) pids.add(pid);
    });
    return Array.from(pids);
  }, [selectedItemKeys]);

  // Group filtered items by parent folder
  const [collapsedReviewFolders, setCollapsedReviewFolders] = useState<Set<string>>(new Set());

  const groupedReviewItems = useMemo(() => {
    const map = new Map<string, { folderPath: string; folderName: string; entries: FlattenedChangeItem[] }>();
    for (const entry of filteredItems) {
      const rawPath = entry.item.source_relative_path || entry.item.destination_relative_path || "";
      const folder = getParentFolder(rawPath);
      if (!map.has(folder)) {
        const parts = folder === "/" ? [] : folder.split("/").filter(Boolean);
        const folderName = folder === "/" ? "Root Directory" : parts[parts.length - 1];
        map.set(folder, {
          folderPath: folder,
          folderName,
          entries: [],
        });
      }
      map.get(folder)!.entries.push(entry);
    }
    return Array.from(map.values()).sort((a, b) => {
      if (a.folderPath === "/") return -1;
      if (b.folderPath === "/") return 1;
      return a.folderPath.localeCompare(b.folderPath);
    });
  }, [filteredItems]);

  const toggleReviewFolderCollapse = (folderPath: string) => {
    setCollapsedReviewFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folderPath)) {
        next.delete(folderPath);
      } else {
        next.add(folderPath);
      }
      return next;
    });
  };

  const toggleFolderSelection = (folderKeys: string[], isAllSelected: boolean) => {
    setSelectedItemKeys((prev) => {
      const next = new Set(prev);
      if (isAllSelected) {
        folderKeys.forEach((k) => next.delete(k));
      } else {
        folderKeys.forEach((k) => next.add(k));
      }
      return next;
    });
  };

  const handleClearFolderInReview = async (entries: FlattenedChangeItem[]) => {
    const editableEntries = entries.filter((e) =>
      ["draft", "pending_review"].includes(e.planStatus)
    );
    if (editableEntries.length === 0) return;
    try {
      for (const e of editableEntries) {
        await ApiService.deletePlanItem(e.planId, e.item.id);
      }
      setFeedbackMessage({
        type: "success",
        text: `Berhasil menghapus ${editableEntries.length} operasi dalam folder dari rencana.`,
      });
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Gagal menghapus operasi dari folder";
      setFeedbackMessage({ type: "error", text: msg });
    }
  };

  // Save Destination Path in Inspector
  const handleSaveDestination = async () => {
    if (!activeSelectedItem) return;
    if (!editingDestPath.trim()) {
      setFeedbackMessage({ type: "error", text: "Destination path cannot be empty" });
      return;
    }
    setIsSavingItem(true);
    try {
      await ApiService.updatePlanItem(
        activeSelectedItem.planId,
        activeSelectedItem.item.id,
        editingDestPath.trim()
      );
      setFeedbackMessage({
        type: "success",
        text: `Destination updated to '${editingDestPath.trim()}'`,
      });
      await loadData();
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to update item path",
      });
    } finally {
      setIsSavingItem(false);
    }
  };

  // Reject Plan(s)
  const handleRejectPlan = async (planId: string) => {
    try {
      await ApiService.rejectPlan(planId);
      setFeedbackMessage({ type: "info", text: "Rencana ditolak dan dibatalkan." });
      await loadData();
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to reject plan",
      });
    }
  };

  // Remove All Conflicting Items from a Plan
  const handleRemoveConflictsFromPlan = async (targetPlan: ChangePlanResponse) => {
    const conflictItems = targetPlan.items.filter(
      (it) => it.status === "conflict" || Boolean(it.conflict_reason)
    );
    if (conflictItems.length === 0) return;
    try {
      for (const it of conflictItems) {
        await ApiService.deletePlanItem(targetPlan.id, it.id);
      }
      setFeedbackMessage({
        type: "success",
        text: `Berhasil menghapus ${conflictItems.length} item konflik dari rencana '${targetPlan.title}'.`,
      });
      await loadData();
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Gagal menghapus item konflik",
      });
    }
  };

  // Remove Only Checked Items from Pending Plans (rejects plan if all items in a plan were checked)
  const handleRemoveSelectedItems = async () => {
    if (selectedItemKeys.size === 0) return;

    const groupedByPlan = new Map<string, string[]>();
    selectedItemKeys.forEach((key) => {
      const sepIdx = key.indexOf(":");
      if (sepIdx === -1) return;
      const pid = key.slice(0, sepIdx);
      const iid = key.slice(sepIdx + 1);
      if (!pid || !iid) return;
      const list = groupedByPlan.get(pid) || [];
      list.push(iid);
      groupedByPlan.set(pid, list);
    });

    let removedCount = 0;
    try {
      for (const [planId, itemIds] of groupedByPlan.entries()) {
        const plan = plans.find((p) => p.id === planId);
        if (!plan) continue;
        if (!["draft", "pending_review"].includes(plan.status)) {
          // If plan is already approved, reject the plan if user wants to drop it
          await ApiService.rejectPlan(planId);
          removedCount += plan.items.length;
        } else if (itemIds.length >= plan.items.length) {
          await ApiService.rejectPlan(planId);
          removedCount += plan.items.length;
        } else {
          for (const iid of itemIds) {
            await ApiService.deletePlanItem(planId, iid);
          }
          removedCount += itemIds.length;
        }
      }
      setFeedbackMessage({
        type: "info",
        text: `Berhasil menghapus ${removedCount} item terpilih dari rencana.`,
      });
      setSelectedItemKeys(new Set());
      await loadData();
    } catch (err: unknown) {
      setFeedbackMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Gagal menghapus item terpilih",
      });
    }
  };

  // Execute (and auto-approve if pending) Plans
  const initiateExecuteApproved = (targetPlans?: ChangePlanResponse[]) => {
    const toRun =
      targetPlans ||
      plans.filter((p) => ["draft", "pending_review", "approved"].includes(p.status));
    if (toRun.length === 0) return;
    setPlansToExecute(toRun);
    setIsConfirmModalOpen(true);
  };

  const handleConfirmExecution = async () => {
    const selectedSnapshot = new Set(selectedItemKeys);
    const hasItemSelection = selectedSnapshot.size > 0;
    setIsConfirmModalOpen(false);
    setIsExecuting(true);
    try {
      const planIds: string[] = [];

      for (const plan of plansToExecute) {
        // If user checked a subset of items in a pending plan, prune unchecked items sequentially first
        if (hasItemSelection && ["draft", "pending_review"].includes(plan.status)) {
          const selectedInPlan = plan.items.filter((it) =>
            selectedSnapshot.has(`${plan.id}:${it.id}`)
          );
          if (selectedInPlan.length > 0 && selectedInPlan.length < plan.items.length) {
            const unselected = plan.items.filter(
              (it) => !selectedSnapshot.has(`${plan.id}:${it.id}`)
            );
            for (const it of unselected) {
              await ApiService.deletePlanItem(plan.id, it.id);
            }
          }
        }

        // Auto-approve pending plans in the same step before executing
        if (["draft", "pending_review"].includes(plan.status)) {
          await ApiService.approvePlan(plan.id);
        }

        planIds.push(plan.id);
      }

      const results: ExecutionJobResponse[] = await ApiService.executeApprovedPlans(planIds);
      const successful = results.filter((r) => r.status === "completed").length;
      const failedJobs = results.filter((r) => r.status !== "completed");
      setSelectedItemKeys(new Set());

      if (failedJobs.length > 0 && successful === 0) {
        setFeedbackMessage({
          type: "error",
          text:
            failedJobs[0].error_message ||
            "Eksekusi gagal dan perubahan telah di-rollback.",
        });
      } else {
        setFeedbackMessage({
          type: "success",
          text: `Berhasil menyetujui dan mengeksekusi ${successful} rencana melalui Transaction Manager.`,
        });
      }
      await loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Execution failed during transaction processing";
      setFeedbackMessage({
        type: "error",
        text: msg,
      });
      await loadData();
      if (msg.toLowerCase().includes("validation issues") || msg.toLowerCase().includes("conflict")) {
        setCardFilter("conflict");
      }
    } finally {
      setIsExecuting(false);
      setPlansToExecute([]);
    }
  };

  const getFolderName = (folderId: string) => {
    return folders.find((f) => f.id === folderId)?.name || folderId;
  };

  const getOpBadge = (op: string) => {
    switch (op) {
      case "move":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FolderInput size={11} />
            Move
          </span>
        );
      case "rename":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <FilePenLine size={11} />
            Rename
          </span>
        );
      case "delete_to_recycle_bin":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <Trash2 size={11} />
            Recycle Bin
          </span>
        );
      case "create_directory":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <FolderPlus size={11} />
            New Folder
          </span>
        );
      case "copy":
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <Copy size={11} />
            Copy
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground border border-border">
            <FileText size={11} />
            {op}
          </span>
        );
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "approved":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={11} />
            Approved
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <CheckCircle2 size={11} />
            Executed
          </span>
        );
      case "rejected":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <XCircle size={11} />
            Rejected
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            Pending
          </span>
        );
    }
  };

  return (
    <div className="h-full w-full flex flex-col min-h-0 overflow-hidden bg-background">
      {/* Top Header Bar — Full width, flush to top edge (h-14 border-b border-border) */}
      <div className="h-14 border-b border-border bg-card/60 backdrop-blur-xs flex items-center justify-between px-4 sm:px-6 shrink-0 z-10">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <ClipboardCheck size={18} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="text-base font-bold tracking-tight text-foreground truncate">
                Review Changes
              </h1>
              <span className="hidden sm:inline-flex items-center text-[11px] font-mono px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
                {allFlattenedItems.length} total operations
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground truncate hidden md:block">
              Review, inspect, approve, or modify filesystem operations before execution.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="text-xs text-muted-foreground mr-1 hidden sm:inline">
            Updated: {lastUpdated}
          </span>
          <button
            type="button"
            onClick={() => setShowSummaryCards(!showSummaryCards)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-card text-xs font-medium hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
            title={showSummaryCards ? "Sembunyikan kartu ringkasan untuk memperluas area tabel" : "Tampilkan kartu ringkasan"}
          >
            {showSummaryCards ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            <span className="hidden md:inline">Ringkasan</span>
          </button>
          <button
            type="button"
            onClick={loadData}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {/* Content Area — Offset with padding below the top header bar */}
      <div className="flex-1 min-h-0 flex flex-col p-4 md:p-6 gap-3 overflow-hidden">
        {/* Feedback Banner */}
      {feedbackMessage && (
        <div
          className={cn(
            "shrink-0 p-2.5 rounded-lg border text-xs flex items-center justify-between animate-in fade-in",
            feedbackMessage.type === "success" &&
              "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400",
            feedbackMessage.type === "error" &&
              "bg-rose-500/10 border-rose-500/30 text-rose-700 dark:text-rose-400",
            feedbackMessage.type === "info" &&
              "bg-blue-500/10 border-blue-500/30 text-blue-700 dark:text-blue-400"
          )}
        >
          <div className="flex items-center gap-2">
            {feedbackMessage.type === "success" && <CheckCircle2 size={16} />}
            {feedbackMessage.type === "error" && <AlertTriangle size={16} />}
            {feedbackMessage.type === "info" && <ShieldAlert size={16} />}
            <span>{feedbackMessage.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setFeedbackMessage(null)}
            className="p-1 text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Summary Cards (Collapsible for Max Screen Space) */}
      {showSummaryCards && (
        <div className="shrink-0 animate-in fade-in duration-150">
          <ReviewSummaryCards
            pendingCount={summaryCounts.pending}
            moveCount={summaryCounts.move}
            renameCount={summaryCounts.rename}
            deleteCount={summaryCounts.deleteCount}
            conflictCount={summaryCounts.conflicts}
            activeFilter={cardFilter}
            onFilterClick={(key) => setCardFilter(cardFilter === key ? undefined : key)}
          />
        </div>
      )}

      {/* Status Tabs */}
      <div className="shrink-0 border-b border-border flex items-center gap-1 overflow-x-auto">
        {(
          [
            { id: "pending", label: "Pending Plans", count: tabCounts.pending },
            { id: "approved", label: "Approved Plans", count: tabCounts.approved },
            { id: "executed", label: "Executed Plans", count: tabCounts.executed },
            { id: "rejected", label: "Rejected Plans", count: tabCounts.rejected },
            { id: "all", label: "All Plans", count: tabCounts.all },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => {
              setActiveTab(tab.id);
              setSelectedItemKeys(new Set());
            }}
            className={cn(
              "px-3.5 py-2 text-xs font-medium border-b-2 transition-colors flex items-center gap-2 whitespace-nowrap",
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            )}
          >
            <span>{tab.label}</span>
            <span
              className={cn(
                "px-1.5 py-0.2 rounded-full text-[10px]",
                activeTab === tab.id
                  ? "bg-primary/10 text-primary font-semibold"
                  : "bg-muted text-muted-foreground"
              )}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* ===================================================================== */}
      {/* 2-COLUMN MASTER-DETAIL SPLIT PANE */}
      {/* ===================================================================== */}
      <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-12 gap-3.5 items-stretch overflow-hidden">
        {/* ------------------------------------------------------------------- */}
        {/* LEFT MASTER COLUMN (col-span-8 / ~67% width or col-span-12)        */}
        {/* ------------------------------------------------------------------- */}
        <div
          className={cn(
            "flex flex-col min-h-0 h-full overflow-hidden transition-all duration-200",
            isInspectorOpen ? "lg:col-span-7 xl:col-span-8" : "col-span-12"
          )}
        >
          {/* Plan Selector & Filter Toolbar */}
          <div className="shrink-0 mb-2 p-2 sm:p-2.5 bg-card border border-border rounded-lg shadow-2xs space-y-2">
            {/* Row 1: Plan Selector + Plan Quick Actions */}
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 flex-1 min-w-[260px]">
                <div className="p-1.5 rounded-md bg-primary/10 text-primary shrink-0">
                  <Layers size={15} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between text-[10px] text-muted-foreground font-semibold uppercase tracking-wider mb-0.5">
                    <span>Pilih Rencana (Plan)</span>
                    {currentPlan && (
                      <span className="font-normal text-muted-foreground lowercase">
                        {plansInActiveTab.findIndex((p) => p.id === currentPlan.id) + 1} dari {plansInActiveTab.length} rencana
                      </span>
                    )}
                  </div>
                  <select
                    value={selectedPlanId}
                    onChange={(e) => {
                      setSelectedPlanId(e.target.value);
                      setSelectedItemKeys(new Set());
                    }}
                    className="w-full px-2.5 py-1 rounded-md border border-input bg-background text-xs font-semibold text-foreground focus:outline-none focus:ring-1 focus:ring-primary cursor-pointer truncate"
                  >
                    {plansInActiveTab.map((p, idx) => {
                      const conflicts = getPlanConflictCount(p);
                      return (
                        <option key={p.id} value={p.id}>
                          #{idx + 1}: {p.title} ({p.items.length} items){conflicts > 0 ? ` • ⚠️ ${conflicts} konflik` : ""} • [{p.status.toUpperCase()}]
                        </option>
                      );
                    })}
                    {plansInActiveTab.length > 1 && (
                      <option value="all">
                        — Tampilkan Semua ({plansInActiveTab.length} Rencana Digabung • {tabTotalItems} operasi) —
                      </option>
                    )}
                    {plansInActiveTab.length === 0 && (
                      <option value="all">Tidak ada rencana di tab ini</option>
                    )}
                  </select>
                </div>
              </div>

              {/* Quick Plan Info & Actions */}
              {currentPlan && (
                <div className="flex items-center gap-2 text-xs pl-2.5 border-l border-border shrink-0">
                  <div className="hidden xl:block text-right">
                    <div className="text-[11px] font-semibold text-foreground truncate max-w-[150px]" title={getFolderName(currentPlan.managed_folder_id)}>
                      {getFolderName(currentPlan.managed_folder_id)}
                    </div>
                    <div className="text-[10px] text-muted-foreground flex items-center justify-end gap-1">
                      {currentPlan.created_by === "ai" ? (
                        <span className="text-primary font-medium">AI Agent</span>
                      ) : (
                        <span>Manual</span>
                      )}
                      <span>•</span>
                      <span className="font-medium text-foreground">{currentPlan.items.length} items</span>
                    </div>
                  </div>

                  {["draft", "pending_review"].includes(currentPlan.status) &&
                    getPlanConflictCount(currentPlan) > 0 && (
                      <button
                        type="button"
                        onClick={() => handleRemoveConflictsFromPlan(currentPlan)}
                        className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20 text-xs font-medium transition-colors shadow-2xs"
                        title="Hapus semua item yang mengalami konflik dari rencana ini agar sisa item yang valid dapat disetujui"
                      >
                        <ShieldAlert size={13} />
                        <span className="hidden sm:inline">Hapus Konflik ({getPlanConflictCount(currentPlan)})</span>
                      </button>
                    )}
                </div>
              )}
            </div>

            {/* Row 2: Search + Filter + Inspector Toggle + Select All */}
            <div className="flex flex-wrap items-center justify-between gap-2 pt-1 border-t border-border/60">
              <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[200px]">
                {/* Search */}
                <div className="relative flex-1 min-w-[140px]">
                  <Search
                    size={13}
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                  />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Cari file, path asal/tujuan..."
                    className="w-full pl-8 pr-3 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                {/* Folder Filter */}
                <select
                  value={selectedFolderId}
                  onChange={(e) => setSelectedFolderId(e.target.value)}
                  className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary max-w-[140px] truncate"
                  title="Filter berdasarkan Folder"
                >
                  <option value="all">Semua Folder</option>
                  {folders.map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.name || f.root_path}
                    </option>
                  ))}
                </select>

                {/* Operation Filter */}
                <select
                  value={selectedOperation}
                  onChange={(e) => setSelectedOperation(e.target.value)}
                  className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="all">Semua Operasi</option>
                  <option value="move">Move</option>
                  <option value="rename">Rename</option>
                  <option value="delete_to_recycle_bin">Recycle Bin</option>
                  <option value="create_directory">New Folder</option>
                  <option value="copy">Copy</option>
                </select>
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsInspectorOpen(!isInspectorOpen)}
                  title={isInspectorOpen ? "Sembunyikan panel detail untuk memperluas tabel" : "Tampilkan panel detail"}
                  className={cn(
                    "px-2.5 py-1 rounded-md border text-xs font-medium flex items-center gap-1.5 transition-colors",
                    isInspectorOpen
                      ? "bg-primary/10 text-primary border-primary/30"
                      : "bg-background text-muted-foreground hover:text-foreground border-border"
                  )}
                >
                  <PanelRight size={13} />
                  <span className="hidden sm:inline">{isInspectorOpen ? "Detail Aktif" : "Buka Detail"}</span>
                </button>

                {isSelectionAllowed && (
                  <button
                    type="button"
                    onClick={selectAllFiltered}
                    className="px-2.5 py-1 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
                  >
                    {selectedItemKeys.size === selectableFilteredItems.length &&
                    selectableFilteredItems.length > 0
                      ? "Batal Semua"
                      : "Pilih Semua"}
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Master Table */}
          {filteredItems.length === 0 ? (
            <div className="flex-1 min-h-0 flex flex-col items-center justify-center p-8 text-center border border-border border-dashed rounded-lg bg-card/40 space-y-2">
              <Layers size={36} className="mx-auto text-muted-foreground/60" />
              <h3 className="text-sm font-semibold">No Changes Found</h3>
              <p className="text-xs text-muted-foreground max-w-sm mx-auto">
                {activeTab === "pending"
                  ? "All pending changes have been reviewed. Run Organization or Smart Rename to stage new operations."
                  : "No change items matching your filters."}
              </p>
            </div>
          ) : (
            <div className="flex-1 min-h-0 rounded-lg border border-border bg-card shadow-xs flex flex-col overflow-hidden">
              <div className="flex-1 min-h-0 overflow-y-auto overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="sticky top-0 z-20 bg-muted/95 backdrop-blur-xs text-muted-foreground border-b border-border uppercase tracking-wider text-[10px] font-semibold shadow-2xs">
                    <tr>
                      {isSelectionAllowed && (
                        <th className="py-2.5 px-3 w-8 text-center bg-muted/95 backdrop-blur-xs sticky top-0">
                          <input
                            type="checkbox"
                            checked={
                              selectedItemKeys.size === selectableFilteredItems.length &&
                              selectableFilteredItems.length > 0
                            }
                            onChange={selectAllFiltered}
                            className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                          />
                        </th>
                      )}
                      <th className="py-2.5 px-2 w-10 text-center bg-muted/95 backdrop-blur-xs sticky top-0">#</th>
                      <th className="py-2.5 px-2 w-24 bg-muted/95 backdrop-blur-xs sticky top-0">Action</th>
                      <th className="py-2.5 px-3 bg-muted/95 backdrop-blur-xs sticky top-0">Source Path</th>
                      <th className="py-2.5 px-3 bg-muted/95 backdrop-blur-xs sticky top-0">Destination Path</th>
                      <th className="py-2.5 px-2 w-28 bg-muted/95 backdrop-blur-xs sticky top-0">Validation</th>
                      <th className="py-2.5 px-2 w-16 text-center bg-muted/95 backdrop-blur-xs sticky top-0">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {groupedReviewItems.map((group) => {
                      const isCollapsed = collapsedReviewFolders.has(group.folderPath);
                      const selectableEntries = group.entries.filter((e) =>
                        isItemSelectable(e.planStatus)
                      );
                      const hasEditableEntries = group.entries.some((e) =>
                        ["draft", "pending_review"].includes(e.planStatus)
                      );
                      const folderKeys = selectableEntries.map(
                        (e) => `${e.planId}:${e.item.id}`
                      );
                      const selectedInFolder = folderKeys.filter((k) =>
                        selectedItemKeys.has(k)
                      ).length;
                      const isAllSelected =
                        selectedInFolder === folderKeys.length && folderKeys.length > 0;
                      const isIndeterminate =
                        selectedInFolder > 0 && selectedInFolder < folderKeys.length;
                      const isNoneSelected = selectedInFolder === 0;

                      return (
                        <React.Fragment key={group.folderPath}>
                          {/* Folder Group Header Row */}
                          <tr className="bg-muted/70 hover:bg-muted/85 transition-colors border-y border-border/80 sticky top-[37px] z-10 backdrop-blur-xs select-none">
                            {isSelectionAllowed && (
                              <td
                                className="py-2 px-3 text-center"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {folderKeys.length > 0 && (
                                  <input
                                    type="checkbox"
                                    checked={isAllSelected}
                                    ref={(el) => {
                                      if (el) el.indeterminate = isIndeterminate;
                                    }}
                                    onChange={() =>
                                      toggleFolderSelection(folderKeys, isAllSelected)
                                    }
                                    className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                                    title={
                                      isAllSelected
                                        ? "Kosongkan seleksi seluruh operasi dalam folder ini"
                                        : "Pilih seluruh operasi dalam folder ini"
                                    }
                                  />
                                )}
                              </td>
                            )}
                            <td
                              colSpan={5}
                              className="py-2 px-2 cursor-pointer"
                              onClick={() => toggleReviewFolderCollapse(group.folderPath)}
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
                                    ({group.entries.length} {group.entries.length === 1 ? "operasi" : "operasi"})
                                  </span>
                                  {isSelectionAllowed && folderKeys.length > 0 && (
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
                                      {selectedInFolder} / {folderKeys.length} dipilih
                                    </span>
                                  )}
                                </div>

                                {/* Folder Clear Action (only for editable pending/draft entries) */}
                                {hasEditableEntries && (
                                  <div
                                    className="flex items-center gap-2"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    <button
                                      type="button"
                                      onClick={() => handleClearFolderInReview(group.entries)}
                                      className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors border border-transparent hover:border-destructive/20"
                                      title="Hapus / bersihkan seluruh operasi dalam folder ini dari rencana"
                                    >
                                      <Trash2 size={12} />
                                      <span>Clear Folder</span>
                                    </button>
                                  </div>
                                )}
                              </div>
                            </td>
                            <td className="py-2 px-2 text-right">
                              {/* spacer */}
                            </td>
                          </tr>

                          {/* Entries inside folder */}
                          {!isCollapsed &&
                            group.entries.map((entry) => {
                              const itemKey = `${entry.planId}:${entry.item.id}`;
                              const itemSelectable = isItemSelectable(entry.planStatus);
                              const isSelected = itemSelectable && selectedItemKeys.has(itemKey);
                              const isActive =
                                activeSelectedItem?.item.id === entry.item.id &&
                                activeSelectedItem?.planId === entry.planId;
                              const hasConflict =
                                entry.item.status === "conflict" || entry.item.conflict_reason;

                              return (
                                <tr
                                  key={itemKey}
                                  onClick={() => selectItemForInspection(entry)}
                                  className={cn(
                                    "cursor-pointer transition-colors group",
                                    isActive
                                      ? "bg-primary/10 border-l-2 border-primary"
                                      : isSelected
                                      ? "bg-muted/60"
                                      : hasConflict
                                      ? "bg-rose-500/5 hover:bg-rose-500/10"
                                      : "hover:bg-muted/30"
                                  )}
                                >
                                  {isSelectionAllowed && (
                                    <td
                                      className={`${rowPad} text-center`}
                                      onClick={(e) => {
                                        if (itemSelectable) {
                                          toggleSelectItem(itemKey, e);
                                        } else {
                                          e.stopPropagation();
                                        }
                                      }}
                                    >
                                      {itemSelectable && (
                                        <input
                                          type="checkbox"
                                          checked={isSelected}
                                          onChange={() => toggleSelectItem(itemKey)}
                                          className="rounded border-border text-primary focus:ring-primary cursor-pointer"
                                        />
                                      )}
                                    </td>
                                  )}
                                  <td className={`${rowPad} text-center text-muted-foreground font-mono text-[11px]`}>
                                    #{entry.item.sequence_no}
                                  </td>
                                  <td className={`${rowPad}`}>{getOpBadge(entry.item.operation)}</td>
                                  <td className={`${rowPad} font-mono text-foreground min-w-[120px] max-w-[200px] xl:max-w-[320px]`}>
                                    <span
                                      title={entry.item.source_relative_path || "(Directory)"}
                                      className="truncate block"
                                    >
                                      {entry.item.source_relative_path || (
                                        <span className="text-muted-foreground italic">(Directory)</span>
                                      )}
                                    </span>
                                  </td>
                                  <td className={`${rowPad} font-mono text-foreground min-w-[120px] max-w-[200px] xl:max-w-[320px]`}>
                                    <span
                                      title={entry.item.destination_relative_path || "(Recycle Bin)"}
                                      className="truncate block"
                                    >
                                      {entry.item.destination_relative_path || (
                                        <span className="text-rose-500 italic">(Recycle Bin)</span>
                                      )}
                                    </span>
                                  </td>
                                  <td className={`${rowPad}`}>
                                    {hasConflict ? (
                                      <span
                                        title={entry.item.conflict_reason || "Conflict detected"}
                                        className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-medium text-[11px]"
                                      >
                                        <AlertTriangle size={12} className="shrink-0" />
                                        <span className="truncate max-w-[100px]">Conflict</span>
                                      </span>
                                    ) : entry.item.status === "completed" ? (
                                      <span className="inline-flex items-center gap-1 text-blue-600 dark:text-blue-400 font-medium text-[11px]">
                                        <CheckCircle2 size={12} />
                                        <span>Executed</span>
                                      </span>
                                    ) : (
                                      <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium text-[11px]">
                                        <CheckCircle2 size={12} />
                                        <span>Verified</span>
                                      </span>
                                    )}
                                  </td>
                                  <td className={`${rowPad} text-center`}>
                                    {getStatusBadge(entry.planStatus)}
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
            </div>
          )}

          {/* Single Primary Action Bar (Only rendered when runnable plans exist) */}
          {plansInActiveTab.length > 0 &&
            (activeTab === "pending" || activeTab === "approved" || isSelectionAllowed) && (
          <div className="shrink-0 mt-2 p-2.5 bg-card border border-border rounded-lg shadow-md flex flex-wrap items-center justify-between gap-3 z-10">
            <div className="flex items-center gap-2 text-xs flex-wrap">
              <span className="font-semibold text-foreground">
                {selectedItemKeys.size > 0
                  ? `${selectedItemKeys.size} item dipilih`
                  : currentPlan
                  ? `${filteredItems.length} operasi dalam rencana ini`
                  : `${filteredItems.length} total operasi`}
              </span>
              {selectedItemKeys.size > 0 ? (
                <button
                  type="button"
                  onClick={() => setSelectedItemKeys(new Set())}
                  className="text-muted-foreground hover:text-foreground text-[11px] underline"
                >
                  Reset pilihan
                </button>
              ) : currentPlan && getPlanConflictCount(currentPlan) > 0 ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/30 text-[11px] font-medium">
                  <AlertTriangle size={11} />
                  {getPlanConflictCount(currentPlan)} konflik (hapus konflik dulu sebelum eksekusi)
                </span>
              ) : null}
            </div>

            <div className="flex items-center gap-2">
              {selectedItemKeys.size > 0 ? (
                (() => {
                  const runnableSelectedPlans = plans.filter(
                    (p) =>
                      targetPlanIdsFromSelection.includes(p.id) &&
                      ["draft", "pending_review", "approved"].includes(p.status)
                  );
                  if (runnableSelectedPlans.length === 0) return null;
                  return (
                    <>
                      <button
                        type="button"
                        onClick={handleRemoveSelectedItems}
                        disabled={isExecuting}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-rose-600 hover:bg-rose-500/10 text-xs font-medium transition-colors disabled:opacity-40"
                      >
                        <Trash2 size={13} />
                        <span>Hapus Item Terpilih ({selectedItemKeys.size})</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => initiateExecuteApproved(runnableSelectedPlans)}
                        disabled={isExecuting}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {isExecuting ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Play size={13} />
                        )}
                        <span>Setujui &amp; Eksekusi Terpilih ({selectedItemKeys.size})</span>
                      </button>
                    </>
                  );
                })()
              ) : currentPlan ? (
                <>
                  {["draft", "pending_review"].includes(currentPlan.status) && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleRejectPlan(currentPlan.id)}
                        disabled={isExecuting}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-rose-600 hover:bg-rose-500/10 text-xs font-medium transition-colors disabled:opacity-40"
                      >
                        <X size={13} />
                        <span>Tolak Rencana</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => initiateExecuteApproved([currentPlan])}
                        disabled={
                          isExecuting ||
                          currentPlan.items.length === 0 ||
                          getPlanConflictCount(currentPlan) > 0
                        }
                        title={
                          getPlanConflictCount(currentPlan) > 0
                            ? "Selesaikan atau hapus item konflik terlebih dahulu"
                            : "Setujui dan jalankan seluruh operasi dalam rencana ini"
                        }
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {isExecuting ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Play size={13} />
                        )}
                        <span>Setujui &amp; Eksekusi ({currentPlan.items.length} item)</span>
                      </button>
                    </>
                  )}
                  {currentPlan.status === "approved" && (
                    <>
                      <button
                        type="button"
                        onClick={() => handleRejectPlan(currentPlan.id)}
                        disabled={isExecuting}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border text-rose-600 hover:bg-rose-500/10 text-xs font-medium transition-colors disabled:opacity-40"
                      >
                        <X size={13} />
                        <span>Batalkan / Tolak</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => initiateExecuteApproved([currentPlan])}
                        disabled={isExecuting || currentPlan.items.length === 0}
                        className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
                      >
                        {isExecuting ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Play size={13} />
                        )}
                        <span>Eksekusi Rencana ({currentPlan.items.length} item)</span>
                      </button>
                    </>
                  )}
                </>
              ) : (
                (() => {
                  const runnablePlans = plansInActiveTab.filter(
                    (p) =>
                      ["draft", "pending_review", "approved"].includes(p.status) &&
                      getPlanConflictCount(p) === 0 &&
                      p.items.length > 0
                  );
                  if (runnablePlans.length === 0) return null;
                  const runnableOpsCount = runnablePlans.reduce(
                    (acc, p) => acc + p.items.length,
                    0
                  );
                  return (
                    <button
                      type="button"
                      onClick={() => initiateExecuteApproved(runnablePlans)}
                      disabled={isExecuting}
                      className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-xs disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      {isExecuting ? (
                        <Loader2 size={13} className="animate-spin" />
                      ) : (
                        <Play size={13} />
                      )}
                      <span>
                        Setujui &amp; Eksekusi Semua ({runnablePlans.length} rencana •{" "}
                        {runnableOpsCount} item)
                      </span>
                    </button>
                  );
                })()
              )}
            </div>
          </div>
          )}
        </div>

        {/* ------------------------------------------------------------------- */}
        {/* RIGHT DETAIL COLUMN (collapsible inspector)                         */}
        {/* ------------------------------------------------------------------- */}
        {isInspectorOpen && (
          <div className="lg:col-span-5 xl:col-span-4 flex flex-col min-h-0 h-full overflow-hidden animate-in fade-in duration-150">
            {activeSelectedItem ? (
              <div className="flex-1 min-h-0 overflow-y-auto pr-1 space-y-3">
                {/* Card 1: Change Details */}
                <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3.5">
                  <div className="flex items-center justify-between border-b border-border pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                        Change Details
                      </span>
                      <span className="font-mono text-xs text-muted-foreground">
                        #{activeSelectedItem.item.sequence_no}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      {getOpBadge(activeSelectedItem.item.operation)}
                      <button
                        type="button"
                        onClick={() => setIsInspectorOpen(false)}
                        className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                        title="Tutup panel detail"
                      >
                        <X size={13} />
                      </button>
                    </div>
                  </div>

                {/* Plan Info */}
                <div className="space-y-1 text-xs">
                  <div className="text-[11px] text-muted-foreground">Plan Context</div>
                  <div className="font-medium text-foreground truncate" title={activeSelectedItem.planTitle}>
                    {activeSelectedItem.planTitle}
                  </div>
                  <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                    <span>Folder: {getFolderName(activeSelectedItem.managedFolderId)}</span>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      {activeSelectedItem.created_by === "ai" ? (
                        <>
                          <Sparkles size={11} className="text-muted-foreground" />
                          <span>AI Agent</span>
                        </>
                      ) : (
                        <span>User Manual</span>
                      )}
                    </span>
                  </div>
                </div>

                {/* Source Path */}
                <div className="space-y-1 text-xs">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>Source Relative Path</span>
                    <button
                      type="button"
                      onClick={() => {
                        navigator.clipboard.writeText(
                          activeSelectedItem.item.source_relative_path || ""
                        );
                        setCopiedPath(true);
                        setTimeout(() => setCopiedPath(false), 2000);
                      }}
                      className="hover:text-foreground text-[10px] flex items-center gap-1"
                    >
                      <Copy size={11} />
                      <span>{copiedPath ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                  <div className="p-2 rounded bg-muted/50 border border-border font-mono text-[11px] text-foreground break-all">
                    {activeSelectedItem.item.source_relative_path || "(Directory root)"}
                  </div>
                </div>

                {/* Editable Destination Path */}
                <div className="space-y-1.5 text-xs">
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span>Proposed Destination Path</span>
                    {["draft", "pending_review"].includes(activeSelectedItem.planStatus) && (
                      <span className="text-[10px] text-primary">Editable</span>
                    )}
                  </div>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="text"
                      value={editingDestPath}
                      onChange={(e) => setEditingDestPath(e.target.value)}
                      disabled={
                        !["draft", "pending_review"].includes(activeSelectedItem.planStatus)
                      }
                      placeholder="e.g. documents/invoice-2026.pdf"
                      className="flex-1 px-2.5 py-1.5 rounded-md border border-input bg-background font-mono text-[11px] focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
                    />
                    {["draft", "pending_review"].includes(activeSelectedItem.planStatus) && (
                      <button
                        type="button"
                        onClick={handleSaveDestination}
                        disabled={
                          isSavingItem ||
                          editingDestPath === activeSelectedItem.item.destination_relative_path
                        }
                        title="Save changed path"
                        className="p-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-40"
                      >
                        {isSavingItem ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <Save size={13} />
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {/* Conflict / Validation Indicator */}
                <div className="pt-2 border-t border-border">
                  {activeSelectedItem.item.status === "conflict" ||
                  activeSelectedItem.item.conflict_reason ? (
                    <div className="p-2.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-700 dark:text-rose-400 text-xs flex flex-col gap-2">
                      <div className="flex items-start gap-2">
                        <AlertTriangle size={15} className="shrink-0 mt-0.5" />
                        <div>
                          <div className="font-semibold">Conflict Detected</div>
                          <div className="text-[11px] mt-0.5">
                            {activeSelectedItem.item.conflict_reason ||
                              "Destination file already exists or target directory is restricted."}
                          </div>
                        </div>
                      </div>
                      {["draft", "pending_review"].includes(activeSelectedItem.planStatus) && (
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              await ApiService.deletePlanItem(activeSelectedItem.planId, activeSelectedItem.item.id);
                              setFeedbackMessage({
                                type: "success",
                                text: `Item berhasil dihapus dari rencana.`,
                              });
                              setIsInspectorOpen(false);
                              setActiveSelectedItem(null);
                              await loadData();
                            } catch (err: unknown) {
                              setFeedbackMessage({
                                type: "error",
                                text: err instanceof Error ? err.message : "Gagal menghapus item",
                              });
                            }
                          }}
                          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-700 dark:text-rose-400 border border-rose-500/30 text-[11px] font-medium transition-colors w-fit"
                        >
                          <Trash2 size={12} />
                          <span>Hapus Item Ini Dari Rencana</span>
                        </button>
                      )}
                    </div>
                  ) : (
                    <div className="p-2.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-xs flex items-center gap-2">
                      <ShieldCheck size={15} className="shrink-0 text-emerald-500" />
                      <div>
                        <span className="font-semibold">Verified Safe</span>
                        <span className="text-[11px] block text-muted-foreground">
                          Target is within managed folder scope. No collisions detected.
                        </span>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Card 2: Live Diff Preview */}
              <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3">
                <div className="flex items-center justify-between border-b border-border pb-2">
                  <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                    Transformation Preview
                  </span>
                  <span className="text-[10px] text-muted-foreground">Live Diff</span>
                </div>

                <div className="space-y-2 text-xs">
                  {/* Current State */}
                  <div>
                    <div className="text-[10px] text-muted-foreground font-medium mb-1">
                      CURRENT NAME / PATH:
                    </div>
                    <div className="p-2 rounded bg-rose-500/10 border border-rose-500/20 font-mono text-[11px] text-rose-700 dark:text-rose-300 break-all">
                      {activeSelectedItem.item.source_relative_path || "(Directory)"}
                    </div>
                  </div>

                  {/* Flow Arrow */}
                  <div className="flex justify-center text-muted-foreground">
                    <ArrowDown size={14} />
                  </div>

                  {/* Proposed State */}
                  <div>
                    <div className="text-[10px] text-muted-foreground font-medium mb-1">
                      PROPOSED NAME / PATH:
                    </div>
                    <div className="p-2 rounded bg-emerald-500/10 border border-emerald-500/20 font-mono text-[11px] text-emerald-700 dark:text-emerald-300 break-all">
                      {editingDestPath ||
                        activeSelectedItem.item.destination_relative_path ||
                        "(Recycle Bin)"}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-full flex flex-col items-center justify-center p-8 rounded-lg border border-border bg-card/60 text-center text-muted-foreground space-y-2 relative">
              <button
                type="button"
                onClick={() => setIsInspectorOpen(false)}
                className="absolute top-3 right-3 p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                title="Tutup panel detail"
              >
                <X size={13} />
              </button>
              <Info size={32} className="mx-auto text-muted-foreground/40" />
              <h4 className="text-xs font-medium text-foreground">No Change Selected</h4>
              <p className="text-[11px] text-muted-foreground max-w-[200px] mx-auto">
                Click any row in the changes table to view its full validation details and live diff.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  </div>

      {/* Execution Confirmation Modal */}
      {isConfirmModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in">
          <div className="bg-card border border-border w-full max-w-md rounded-xl shadow-xl p-5 space-y-4">
            <div className="flex items-start gap-3">
              <div className="p-2.5 rounded-full bg-emerald-500/10 text-emerald-600 shrink-0">
                <Play size={20} />
              </div>
              <div>
                <h3 className="text-base font-semibold text-foreground">
                  Konfirmasi Eksekusi Perubahan File
                </h3>
                <p className="text-xs text-muted-foreground mt-1">
                  {selectedItemKeys.size > 0 ? (
                    <>
                      Anda akan menyetujui dan mengeksekusi{" "}
                      <strong>{selectedItemKeys.size} item terpilih</strong> pada{" "}
                      <strong>{plansToExecute.length} rencana</strong> melalui Transaction Manager.
                      Item yang tidak dicentang pada rencana pending akan dikeluarkan dari rencana.
                    </>
                  ) : (
                    <>
                      Anda akan menyetujui dan mengeksekusi{" "}
                      <strong>{plansToExecute.length} rencana</strong> berisi{" "}
                      <strong>
                        {plansToExecute.reduce((acc, p) => acc + p.items.length, 0)} operasi
                        filesystem
                      </strong>{" "}
                      melalui Transaction Manager.
                    </>
                  )}
                </p>
              </div>
            </div>

            <div className="p-3 rounded-lg bg-muted/40 border border-border text-xs space-y-1">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Transactions:</span>
                <span className="font-semibold text-foreground">Atomic with Rollback Log</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Deletions:</span>
                <span className="font-semibold text-emerald-600">Recycle Bin / Quarantine</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Overwrite Safety:</span>
                <span className="font-semibold text-foreground">Strict Collision Protection</span>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setIsConfirmModalOpen(false)}
                className="px-3 py-1.5 rounded-md border border-border text-xs font-medium hover:bg-muted transition-colors"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleConfirmExecution}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-semibold transition-colors shadow-xs"
              >
                <Check size={14} />
                <span>Ya, Setujui &amp; Eksekusi Sekarang</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
