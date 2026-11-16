import React, { useState, useEffect } from "react";
import {
  FolderTree,
  Sparkles,
  History,
  ShieldCheck,
  Shield,
  CheckCircle2,
  AlertCircle,
  FileText,
  RefreshCw,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  Pencil,
  Trash2,
  Check,
  Send,
  X,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext";
import { formatDate, cn } from "@/lib/utils";
import type {
  ManagedFolder,
  OrganizationPlanRequest,
  OrganizationPlanResult,
  ChangePlanResponse,
  RuleExecutionResponse,
} from "@/types";
import { OrganizationConfigPanel } from "./OrganizationConfigPanel";
import { OrganizationSummaryCards } from "./OrganizationSummaryCards";
import { OrganizationStructureComparison } from "./OrganizationStructureComparison";
import { OrganizationChangePlan } from "./OrganizationChangePlan";
import { OrganizationRulesPanel } from "./OrganizationRulesPanel";
import { ProtectedFoldersCard } from "./ProtectedFoldersCard";

type OrgTab = "create" | "review" | "rules" | "history";

interface OrganizationManagerProps {
  onNavigateToReviewChanges?: () => void;
}

export const OrganizationManager: React.FC<OrganizationManagerProps> = ({
  onNavigateToReviewChanges,
}) => {
  const { activeJobs, lastCompletedPayload, clearCompletedPayload } = useBackgroundTasks();

  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<OrgTab>("create");

  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [configResetKey, setConfigResetKey] = useState(0);
  const [planResult, setPlanResult] = useState<OrganizationPlanResult | null>(null);
  const [existingPlans, setExistingPlans] = useState<ChangePlanResponse[]>([]);
  const [ruleExecutions, setRuleExecutions] = useState<RuleExecutionResponse[]>([]);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const activeOrgJob = activeJobs.find(
    (j) =>
      j.job_type === "organization_plan" &&
      (!selectedFolderId ||
        j.managed_folder_id === selectedFolderId ||
        !j.managed_folder_id)
  );

  // Result hydration when job completes in background
  useEffect(() => {
    if (lastCompletedPayload && lastCompletedPayload.jobType === "organization_plan") {
      if (lastCompletedPayload.resultPayload) {
        if (lastCompletedPayload.resultPayload.change_plan_id) {
          setPlanResult(lastCompletedPayload.resultPayload);
          setSuccessMessage("Rencana organisasi folder selesai diproses di latar belakang.");
        }
      }
      clearCompletedPayload();
    }
  }, [lastCompletedPayload, clearCompletedPayload]);

  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null);
  const [editingItemId, setEditingItemId] = useState<string | null>(null);
  const [editDestPath, setEditDestPath] = useState<string>("");
  const [isUpdatingSavedItem, setIsUpdatingSavedItem] = useState(false);
  const [isSubmittingSavedPlan, setIsSubmittingSavedPlan] = useState(false);

  // Load registered folders
  useEffect(() => {
    ApiService.listFolders()
      .then((data) => {
        setFolders(data);
        if (data.length > 0 && !selectedFolderId) {
          setSelectedFolderId(data[0].id);
        }
      })
      .catch((err) => console.error("Failed to load folders:", err));
  }, []);

  const loadHistoryTab = () => {
    setIsHistoryLoading(true);
    Promise.all([
      ApiService.listPlans(undefined, undefined),
      ApiService.listRuleExecutions(undefined, 50),
    ])
      .then(([plans, execs]) => {
        setExistingPlans(plans.filter((p) => p.plan_type === "organize"));
        setRuleExecutions(execs);
      })
      .catch((err) => console.error("Failed to load organization history:", err))
      .finally(() => setIsHistoryLoading(false));
  };

  // Load existing plans when opening Review or History tab
  useEffect(() => {
    if (activeTab === "review") {
      ApiService.listPlans(undefined, undefined)
        .then((plans) => setExistingPlans(plans.filter((p) => p.plan_type === "organize")))
        .catch((err) => console.error("Failed to load plans:", err));
    } else if (activeTab === "history") {
      loadHistoryTab();
    }
  }, [activeTab]);

  const handleGeneratePlan = async (req: OrganizationPlanRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await ApiService.generateOrganizationPlanAsync(req);
      setSuccessMessage("Analisis organisasi folder sedang diproses di latar belakang...");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate organization plan";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateItemDestination = async (itemId: string, newDest: string) => {
    if (!planResult) return;
    try {
      await ApiService.updatePlanItem(planResult.change_plan_id, itemId, newDest);
      // Update local state
      setPlanResult((prev) => {
        if (!prev) return null;
        const updatedItems = prev.items.map((it) =>
          it.item_id === itemId
            ? { ...it, destination_relative_path: newDest, status: "pending" as const, conflict_reason: null }
            : it
        );
        const conflicts = updatedItems.filter((it) => it.status === "conflict").length;
        return {
          ...prev,
          items: updatedItems,
          conflicts_count: conflicts,
        };
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update item";
      setErrorMessage(msg);
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!planResult) return;
    try {
      await ApiService.deletePlanItem(planResult.change_plan_id, itemId);
      setPlanResult((prev) => {
        if (!prev) return null;
        const updated = prev.items.filter((it) => it.item_id !== itemId);
        return {
          ...prev,
          items: updated,
          files_to_move_count: updated.filter((it) => it.operation === "move").length,
          folders_to_create_count: updated.filter((it) => it.operation === "create_directory").length,
          conflicts_count: updated.filter((it) => it.status === "conflict").length,
        };
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete item";
      setErrorMessage(msg);
    }
  };

  const handleDeleteItems = async (itemIds: string[]) => {
    if (!planResult || itemIds.length === 0) return;
    try {
      await Promise.all(
        itemIds.map((id) => ApiService.deletePlanItem(planResult.change_plan_id, id))
      );
      const idSet = new Set(itemIds);
      setPlanResult((prev) => {
        if (!prev) return null;
        const updated = prev.items.filter((it) => !idSet.has(it.item_id || ""));
        return {
          ...prev,
          items: updated,
          files_to_move_count: updated.filter((it) => it.operation === "move").length,
          folders_to_create_count: updated.filter((it) => it.operation === "create_directory").length,
          conflicts_count: updated.filter((it) => it.status === "conflict").length,
        };
      });
      setSuccessMessage(`Berhasil menghapus ${itemIds.length} operasi dari rencana organisasi.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete items";
      setErrorMessage(msg);
    }
  };

  const handleSubmitPlan = async () => {
    if (!planResult) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      await ApiService.submitPlan(planResult.change_plan_id);
      setPlanResult(null);
      setConfigResetKey((prev) => prev + 1);
      setSuccessMessage(
        "Plan submitted to Review Changes! You can now inspect, approve, and execute it under Review Changes."
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit plan";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleExpandPlan = (planId: string) => {
    setExpandedPlanId((prev) => (prev === planId ? null : planId));
    setEditingItemId(null);
    setEditDestPath("");
  };

  const handleStartEditSavedItem = (itemId: string, currentDest: string) => {
    setEditingItemId(itemId);
    setEditDestPath(currentDest);
  };

  const handleSaveEditSavedItem = async (planId: string, itemId: string) => {
    if (!editDestPath.trim()) return;
    setIsUpdatingSavedItem(true);
    setErrorMessage(null);
    try {
      await ApiService.updatePlanItem(planId, itemId, editDestPath.trim());
      setExistingPlans((prev) =>
        prev.map((p) => {
          if (p.id !== planId) return p;
          return {
            ...p,
            items: p.items.map((it) =>
              it.id === itemId
                ? { ...it, destination_relative_path: editDestPath.trim(), status: "pending", conflict_reason: null }
                : it
            ),
          };
        })
      );
      setEditingItemId(null);
      setSuccessMessage("Item destination path updated successfully in draft plan.");
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to update item");
    } finally {
      setIsUpdatingSavedItem(false);
    }
  };

  const handleDeleteSavedPlanItem = async (planId: string, itemId: string) => {
    setIsUpdatingSavedItem(true);
    setErrorMessage(null);
    try {
      await ApiService.deletePlanItem(planId, itemId);
      setExistingPlans((prev) =>
        prev.map((p) => {
          if (p.id !== planId) return p;
          return {
            ...p,
            items: p.items.filter((it) => it.id !== itemId),
          };
        })
      );
      setSuccessMessage("Item removed from draft plan.");
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to delete item");
    } finally {
      setIsUpdatingSavedItem(false);
    }
  };

  const handleSubmitSavedDraftPlan = async (planId: string) => {
    setIsSubmittingSavedPlan(true);
    setErrorMessage(null);
    try {
      await ApiService.submitPlan(planId);
      setExistingPlans((prev) =>
        prev.map((p) => (p.id === planId ? { ...p, status: "pending_review" } : p))
      );
      setSuccessMessage(
        "Draft plan submitted to Review Changes! It is now visible in the Review Changes preview."
      );
    } catch (err: unknown) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to submit plan");
    } finally {
      setIsSubmittingSavedPlan(false);
    }
  };

  return (
    <div className="h-full w-full flex flex-col min-h-0 overflow-hidden bg-background">
      {/* Top Header Bar — Flush to top edge (h-14 border-b border-border) */}
      <div className="h-14 border-b border-border bg-card/60 backdrop-blur-xs flex items-center justify-between px-4 sm:px-6 shrink-0 z-20">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <FolderTree size={18} />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold tracking-tight text-foreground truncate">
              Organization
            </h1>
            <p className="text-[11px] text-muted-foreground truncate hidden md:block">
              Analyze and organize files into a cleaner and more structured folder layout using AI.
            </p>
          </div>
        </div>

        {/* Tab pills right in the top header */}
        <div className="flex items-center bg-muted/60 p-1 rounded-lg border border-border/50 text-xs shrink-0">
          <button
            onClick={() => setActiveTab("create")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all",
              activeTab === "create"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Sparkles size={13} />
            <span className="hidden sm:inline">Create Plan</span>
          </button>
          <button
            onClick={() => setActiveTab("review")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all",
              activeTab === "review"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <FileText size={13} />
            <span className="hidden sm:inline">Review Plans</span>
          </button>
          <button
            onClick={() => setActiveTab("rules")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all",
              activeTab === "rules"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <ShieldCheck size={13} />
            <span className="hidden sm:inline">Organization Rules</span>
          </button>
          <button
            onClick={() => setActiveTab("history")}
            className={cn(
              "flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all",
              activeTab === "history"
                ? "bg-background text-foreground shadow-xs font-semibold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <History size={13} />
            <span className="hidden sm:inline">History</span>
          </button>
        </div>
      </div>

      {/* Offset Content Scroll Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 space-y-5">
        {/* Alerts */}
        {errorMessage && (
          <div className="p-3.5 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}

        {successMessage && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-xs flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={16} className="shrink-0" />
              <span>{successMessage}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {onNavigateToReviewChanges && !planResult && (
                <button
                  type="button"
                  onClick={onNavigateToReviewChanges}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium transition-colors"
                >
                  <span>Open Review Changes</span>
                  <ArrowRight size={13} />
                </button>
              )}
              <button
                type="button"
                onClick={() => setSuccessMessage(null)}
                className="p-1 rounded hover:bg-emerald-500/20 transition-colors"
                title="Dismiss"
              >
                <X size={14} />
              </button>
            </div>
          </div>
        )}

        {/* Active Background Job Progress Banner (Decoupled, non-blocking) */}
        {activeOrgJob && (
          <div className="p-3.5 rounded-xl border border-emerald-500/40 bg-emerald-500/5 flex items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-3 min-w-0">
              <RefreshCw size={17} className="animate-spin text-emerald-500 shrink-0" />
              <div className="min-w-0">
                <p className="font-semibold text-foreground truncate">
                  {activeOrgJob.title} ({activeOrgJob.progress}%)
                </p>
                <p className="text-muted-foreground truncate text-[11px] mt-0.5">
                  {activeOrgJob.current_step}
                </p>
              </div>
            </div>
            <div className="w-36 hidden sm:block shrink-0 bg-secondary h-2 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full transition-all duration-300"
                style={{ width: `${Math.max(5, activeOrgJob.progress)}%` }}
              />
            </div>
          </div>
        )}

        {/* Tab: Create Plan */}
        {activeTab === "create" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* Left: Configuration Panel */}
            <div className="lg:col-span-5 lg:sticky lg:top-0">
            <OrganizationConfigPanel
              key={configResetKey}
              folders={folders}
              selectedFolderId={selectedFolderId}
              onSelectFolderId={setSelectedFolderId}
              onSubmit={handleGeneratePlan}
              isLoading={isLoading}
            />
          </div>

          {/* Right: Protected Folders Card + Results / Change Plan */}
          <div className="lg:col-span-7 space-y-5">
            <ProtectedFoldersCard folderId={selectedFolderId} />

            {!planResult ? (
              <div className="p-12 text-center border border-dashed border-border rounded-xl bg-card/40 space-y-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
                  <FolderTree size={22} />
                </div>
                <div className="max-w-sm mx-auto space-y-1">
                  <h4 className="text-sm font-semibold text-foreground">No Plan Generated Yet</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Select a target folder and choose an organization goal on the left, then click Analyze & Create Plan to preview proposed layouts.
                  </p>
                </div>
              </div>
            ) : (
              <>
                {((planResult.protected_folders_skipped_count || 0) > 0 ||
                  (planResult.protected_folders_skipped && planResult.protected_folders_skipped.length > 0)) && (
                  <div className="p-3.5 rounded-xl bg-amber-500/5 border border-amber-500/20 text-xs text-foreground flex flex-col gap-2 shadow-2xs">
                    <div className="flex items-center gap-2">
                      <div className="p-1 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400 shrink-0">
                        <Shield size={14} />
                      </div>
                      <span className="font-semibold text-foreground">
                        {planResult.protected_folders_skipped_count || planResult.protected_folders_skipped?.length || 0} Folder Dikecualikan & Dilindungi
                      </span>
                      <span className="text-muted-foreground">
                        (dilewati otomatis dari rencana organisasi agar struktur proyek tetap utuh)
                      </span>
                    </div>
                    {planResult.protected_folders_skipped && planResult.protected_folders_skipped.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pl-6 max-h-24 overflow-y-auto">
                        {planResult.protected_folders_skipped.map((p) => (
                          <span
                            key={p}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-[11px] bg-background/80 border border-border/60 text-muted-foreground"
                          >
                            <Shield size={10} className="text-amber-500 shrink-0" />
                            <span>{p}</span>
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                )}
                <OrganizationSummaryCards data={planResult} />
                <OrganizationStructureComparison
                  currentStructure={planResult.current_structure}
                  proposedStructure={planResult.proposed_structure}
                />
                <OrganizationChangePlan
                  planId={planResult.change_plan_id}
                  items={planResult.items}
                  onUpdateItemDestination={handleUpdateItemDestination}
                  onDeleteItem={handleDeleteItem}
                  onDeleteItems={handleDeleteItems}
                  onSubmitPlan={handleSubmitPlan}
                  onDiscardPlan={() => {
                    setPlanResult(null);
                    setSuccessMessage(null);
                    setErrorMessage(null);
                  }}
                  isSubmitting={isSubmitting}
                />
              </>
            )}
          </div>
        </div>
      )}

      {/* Tab: Review Plans */}
      {activeTab === "review" && (
        <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-border/60">
            <div>
              <h3 className="font-semibold text-sm text-foreground">Saved Organization Plans</h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                Plans in Draft status can be edited and pruned here, and will only appear in Preview/Review Changes after submission.
              </p>
            </div>
            <span className="text-xs text-muted-foreground">{existingPlans.length} plans</span>
          </div>

          {existingPlans.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">
              No organization change plans found. Generate a plan using the Create Plan tab.
            </p>
          ) : (
            <div className="space-y-3">
              {existingPlans.map((plan) => {
                const isExpanded = expandedPlanId === plan.id;
                const isDraft = plan.status === "draft";

                return (
                  <div
                    key={plan.id}
                    className="border border-border/70 rounded-xl overflow-hidden bg-card/40 transition-all text-xs"
                  >
                    {/* Header Row */}
                    <div className="p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-muted/20">
                      <div className="flex items-start gap-2.5 min-w-0">
                        <button
                          type="button"
                          onClick={() => handleToggleExpandPlan(plan.id)}
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0 mt-0.5"
                          title={isExpanded ? "Collapse" : "Expand items"}
                        >
                          {isExpanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />}
                        </button>
                        <div className="min-w-0">
                          <h4 className="font-semibold text-foreground text-sm truncate">{plan.title}</h4>
                          <p className="text-muted-foreground text-[11px] mt-0.5">
                            Created {formatDate(plan.created_at)} • {plan.items.length} operations
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 self-end sm:self-auto shrink-0">
                        {isDraft ? (
                          <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                            Draft (Editable • Not in Preview)
                          </span>
                        ) : plan.status === "pending_review" ? (
                          <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                            In Review (In Preview)
                          </span>
                        ) : plan.status === "approved" ? (
                          <span className="px-2.5 py-1 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                            Approved
                          </span>
                        ) : (
                          <span className="capitalize px-2.5 py-1 rounded-full text-[11px] font-semibold bg-muted text-foreground">
                            {plan.status.replace("_", " ")}
                          </span>
                        )}

                        {isDraft && (
                          <button
                            type="button"
                            onClick={() => handleSubmitSavedDraftPlan(plan.id)}
                            disabled={isSubmittingSavedPlan}
                            className="inline-flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50"
                            title="Submit plan to Review Changes"
                          >
                            <Send size={12} />
                            <span>Submit to Preview</span>
                          </button>
                        )}

                        {!isDraft && onNavigateToReviewChanges && (
                          <button
                            type="button"
                            onClick={onNavigateToReviewChanges}
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-muted hover:bg-accent text-foreground transition-colors"
                          >
                            <span>Open in Review Changes</span>
                            <ArrowRight size={12} />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expandable Plan Items Table */}
                    {isExpanded && (
                      <div className="border-t border-border/60 p-4 space-y-3 bg-card/60">
                        {isDraft ? (
                          <div className="p-2.5 rounded-lg bg-amber-500/5 border border-amber-500/20 text-[11px] text-amber-700 dark:text-amber-300">
                            <strong>Draf Rencana:</strong> Item di bawah ini dapat Anda edit nama tujuannya atau dihapus sebelum diajukan. Rencana ini belum muncul di halaman Preview/Review Changes.
                          </div>
                        ) : (
                          <div className="p-2.5 rounded-lg bg-blue-500/5 border border-blue-500/20 text-[11px] text-blue-700 dark:text-blue-300">
                            Rencana ini telah diajukan dan sedang aktif dalam tahap review / eksekusi.
                          </div>
                        )}

                        {plan.items.length === 0 ? (
                          <p className="text-center py-4 text-xs text-muted-foreground">Tidak ada item dalam rencana ini.</p>
                        ) : (
                          <div className="border border-border/60 rounded-lg overflow-x-auto">
                            <table className="w-full text-left text-xs border-collapse">
                              <thead>
                                <tr className="border-b border-border/60 bg-muted/40 text-[11px] font-semibold text-muted-foreground">
                                  <th className="py-2 px-3">Operation</th>
                                  <th className="py-2 px-3">Source Relative Path</th>
                                  <th className="py-2 px-3">Destination Relative Path</th>
                                  <th className="py-2 px-3">Status</th>
                                  {isDraft && <th className="py-2 px-3 text-right">Actions</th>}
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-border/40">
                                {plan.items.map((it) => {
                                  const isEditing = editingItemId === it.id;

                                  return (
                                    <tr key={it.id} className="hover:bg-muted/30 transition-colors">
                                      <td className="py-2 px-3 shrink-0">
                                        <span className={cn(
                                          "px-2 py-0.5 rounded text-[10px] font-semibold capitalize",
                                          it.operation === "move"
                                            ? "bg-blue-500/10 text-blue-600 dark:text-blue-400"
                                            : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                                        )}>
                                          {it.operation.replace("_", " ")}
                                        </span>
                                      </td>
                                      <td className="py-2 px-3 font-mono text-[11px] text-foreground max-w-[200px] truncate" title={it.source_relative_path || "(none)"}>
                                        {it.source_relative_path || <span className="text-muted-foreground italic">(new directory)</span>}
                                      </td>
                                      <td className="py-2 px-3 font-mono text-[11px] text-foreground min-w-[240px]">
                                        {isEditing ? (
                                          <div className="flex items-center gap-1.5">
                                            <input
                                              type="text"
                                              value={editDestPath}
                                              onChange={(e) => setEditDestPath(e.target.value)}
                                              className="w-full px-2 py-1 rounded border border-primary bg-background text-foreground text-xs font-mono"
                                              disabled={isUpdatingSavedItem}
                                              autoFocus
                                            />
                                            <button
                                              type="button"
                                              onClick={() => handleSaveEditSavedItem(plan.id, it.id)}
                                              disabled={isUpdatingSavedItem}
                                              className="p-1 rounded bg-primary text-primary-foreground hover:bg-primary/90"
                                              title="Save"
                                            >
                                              <Check size={13} />
                                            </button>
                                            <button
                                              type="button"
                                              onClick={() => setEditingItemId(null)}
                                              className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground"
                                              title="Cancel"
                                            >
                                              <X size={13} />
                                            </button>
                                          </div>
                                        ) : (
                                          <div className="flex items-center justify-between gap-2">
                                            <span className="truncate" title={it.destination_relative_path || ""}>
                                              {it.destination_relative_path}
                                            </span>
                                            {isDraft && (
                                              <button
                                                type="button"
                                                onClick={() => handleStartEditSavedItem(it.id, it.destination_relative_path || "")}
                                                className="p-1 rounded text-muted-foreground hover:text-primary hover:bg-primary/10 transition-colors shrink-0"
                                                title="Edit destination path"
                                              >
                                                <Pencil size={12} />
                                              </button>
                                            )}
                                          </div>
                                        )}
                                      </td>
                                      <td className="py-2 px-3">
                                        {it.conflict_reason || it.status === "conflict" ? (
                                          <span className="text-[10px] text-destructive bg-destructive/10 px-1.5 py-0.5 rounded font-medium">
                                            {it.conflict_reason || "Conflict"}
                                          </span>
                                        ) : (
                                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded font-medium">
                                            Ready
                                          </span>
                                        )}
                                      </td>
                                      {isDraft && (
                                        <td className="py-2 px-3 text-right">
                                          <button
                                            type="button"
                                            onClick={() => handleDeleteSavedPlanItem(plan.id, it.id)}
                                            disabled={isUpdatingSavedItem}
                                            className="p-1 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                                            title="Delete item from draft"
                                          >
                                            <Trash2 size={13} />
                                          </button>
                                        </td>
                                      )}
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Tab: Organization Rules */}
      {activeTab === "rules" && (
        <OrganizationRulesPanel
          folders={folders}
          selectedFolderId={selectedFolderId || undefined}
        />
      )}

      {/* Tab: History */}
      {activeTab === "history" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between p-4 rounded-xl border border-border bg-card shadow-sm">
            <div>
              <h4 className="font-semibold text-sm text-foreground flex items-center gap-2">
                <History size={16} className="text-primary" />
                <span>Organization & Rule Execution History</span>
              </h4>
              <p className="text-xs text-muted-foreground mt-0.5">
                Completed or rolled-back organization plans and automated rule runs.
              </p>
            </div>
            <button
              type="button"
              onClick={loadHistoryTab}
              disabled={isHistoryLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
            >
              <RefreshCw size={13} className={isHistoryLoading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </button>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Executed Organization Plans */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-border bg-muted/30">
                <h5 className="text-xs font-semibold text-foreground">
                  Executed Organization Plans
                </h5>
              </div>
              {existingPlans.filter((p) => p.status !== "draft").length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground">
                  No executed organization plans yet.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {existingPlans
                    .filter((p) => p.status !== "draft")
                    .map((plan) => (
                      <div key={plan.id} className="p-3.5 text-xs flex items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="font-semibold text-foreground truncate">{plan.title}</p>
                          <p className="text-[11px] text-muted-foreground">
                            {plan.items?.length || 0} operations · Updated {formatDate(plan.updated_at)}
                          </p>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground font-medium capitalize text-[11px] shrink-0">
                          {plan.status}
                        </span>
                      </div>
                    ))}
                </div>
              )}
            </div>

            {/* Automated Rule Execution Logs */}
            <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
              <div className="px-4 py-3 border-b border-border bg-muted/30">
                <h5 className="text-xs font-semibold text-foreground">
                  Automated Rule Evaluation History
                </h5>
              </div>
              {ruleExecutions.length === 0 ? (
                <div className="p-8 text-center text-xs text-muted-foreground">
                  No automated rule executions recorded yet.
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {ruleExecutions.map((exec) => (
                    <div key={exec.id} className="p-3.5 text-xs flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-mono text-[11px] text-foreground truncate">
                          Rule {exec.organization_rule_id.slice(0, 8)} (v{exec.rule_version})
                        </p>
                        <p className="text-[11px] text-muted-foreground truncate">
                          {exec.reason || "Evaluated against file event"} · {formatDate(exec.created_at)}
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground font-medium capitalize text-[11px] shrink-0">
                        {exec.status}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
      </div>
    </div>
  );
};
