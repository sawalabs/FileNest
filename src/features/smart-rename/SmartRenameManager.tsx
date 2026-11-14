import React, { useState, useEffect } from "react";
import {
  FilePenLine,
  Sparkles,
  FileText,
  History,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  X,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { formatDate, cn } from "@/lib/utils";
import type {
  ManagedFolder,
  SmartRenamePlanRequest,
  SmartRenamePlanResult,
  ChangePlanResponse,
} from "@/types";
import { SmartRenameConfigPanel } from "./SmartRenameConfigPanel";
import { SmartRenameSummaryCards } from "./SmartRenameSummaryCards";
import { SmartRenamePreviewTable } from "./SmartRenamePreviewTable";

type RenameTab = "create" | "review" | "rules" | "history";

interface SmartRenameManagerProps {
  onNavigateToReviewChanges?: () => void;
}

export const SmartRenameManager: React.FC<SmartRenameManagerProps> = ({
  onNavigateToReviewChanges,
}) => {
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("");
  const [activeTab, setActiveTab] = useState<RenameTab>("create");

  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [configResetKey, setConfigResetKey] = useState(0);
  const [planResult, setPlanResult] = useState<SmartRenamePlanResult | null>(null);
  const [existingPlans, setExistingPlans] = useState<ChangePlanResponse[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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

  useEffect(() => {
    if (activeTab === "review") {
      ApiService.listPlans(undefined, undefined)
        .then((plans) => setExistingPlans(plans.filter((p) => p.plan_type === "rename")))
        .catch((err) => console.error("Failed to load plans:", err));
    }
  }, [activeTab]);

  const handleGeneratePlan = async (req: SmartRenamePlanRequest) => {
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await ApiService.createSmartRenamePlan(req);
      setPlanResult(res);
      setSuccessMessage("Smart Rename plan generated as draft with conflict checks.");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate rename plan";
      setErrorMessage(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateProposedName = async (itemId: string, newDest: string) => {
    if (!planResult) return;
    try {
      await ApiService.updatePlanItem(planResult.change_plan_id, itemId, newDest);
      const newName = newDest.split("/").pop() || newDest;
      setPlanResult((prev) => {
        if (!prev) return null;
        const updated = prev.items.map((it) =>
          it.item_id === itemId
            ? {
                ...it,
                destination_relative_path: newDest,
                proposed_name: newName,
                status: "ready" as const,
                conflict_reason: null,
              }
            : it
        );
        return {
          ...prev,
          items: updated,
          conflicts_count: updated.filter((it) => it.status === "conflict").length,
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
          files_to_rename_count: updated.filter((it) => it.status === "ready").length,
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
          files_to_rename_count: updated.filter((it) => it.status === "ready").length,
          conflicts_count: updated.filter((it) => it.status === "conflict").length,
        };
      });
      setSuccessMessage(`Berhasil menghapus ${itemIds.length} berkas dari rencana perubahan.`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to delete items";
      setErrorMessage(msg);
    }
  };

  const handleRefreshPlan = async () => {
    if (!planResult) return;
    try {
      const plan = await ApiService.getPlan(planResult.change_plan_id);
      if (plan && plan.items) {
        setPlanResult((prev) => {
          if (!prev) return null;
          const mappedItems = plan.items.map((it, idx) => {
            const origName = it.source_relative_path?.split("/").pop() || "";
            const proposedName = it.destination_relative_path?.split("/").pop() || origName;
            return {
              item_id: it.id,
              sequence_no: it.sequence_no || idx + 1,
              source_relative_path: it.source_relative_path || "",
              original_name: origName,
              proposed_name: proposedName,
              destination_relative_path: it.destination_relative_path || "",
              size_bytes: it.expected_size_bytes || 0,
              extension: origName.split(".").pop(),
              category: "file",
              status: it.status === "conflict" ? ("conflict" as const) : origName === proposedName ? ("unchanged" as const) : ("ready" as const),
              conflict_reason: it.conflict_reason,
            };
          });
          return {
            ...prev,
            items: mappedItems,
            files_to_rename_count: mappedItems.filter((i) => i.status === "ready").length,
            files_unchanged_count: mappedItems.filter((i) => i.status === "unchanged").length,
            conflicts_count: mappedItems.filter((i) => i.status === "conflict").length,
          };
        });
      }
    } catch (err) {
      console.error("Failed to refresh plan:", err);
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
        "Rename Plan submitted to Review Changes! You can inspect, approve, and execute it under Review Changes."
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to submit plan";
      setErrorMessage(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="h-full w-full flex flex-col min-h-0 overflow-hidden bg-background">
      {/* Top Header Bar — Flush to top edge (h-14 border-b border-border) */}
      <div className="h-14 border-b border-border bg-card/60 backdrop-blur-xs flex items-center justify-between px-4 sm:px-6 shrink-0 z-20">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <FilePenLine size={18} />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold tracking-tight text-foreground truncate">
              Smart Rename
            </h1>
            <p className="text-[11px] text-muted-foreground truncate hidden md:block">
              Analyze and generate consistent, descriptive, and organized file names using AI.
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
            <span className="hidden sm:inline">Rename Rules</span>
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

        {/* Tab: Create Plan */}
        {activeTab === "create" && (
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            <div className="lg:col-span-5 lg:sticky lg:top-0">
            <SmartRenameConfigPanel
              key={configResetKey}
              folders={folders}
              selectedFolderId={selectedFolderId}
              onSelectFolderId={setSelectedFolderId}
              onSubmit={handleGeneratePlan}
              isLoading={isLoading}
            />
          </div>

          <div className="lg:col-span-7 space-y-5">
            {!planResult ? (
              <div className="p-12 text-center border border-dashed border-border rounded-xl bg-card/40 space-y-3">
                <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
                  <FilePenLine size={22} />
                </div>
                <div className="max-w-sm mx-auto space-y-1">
                  <h4 className="text-sm font-semibold text-foreground">No Rename Plan Generated</h4>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    Select a target folder and choose a renaming strategy on the left, then click Generate Rename Plan to preview proposed names side-by-side.
                  </p>
                </div>
              </div>
            ) : (
              <>
                <SmartRenameSummaryCards data={planResult} />
                <SmartRenamePreviewTable
                  planId={planResult.change_plan_id}
                  items={planResult.items}
                  onUpdateProposedName={handleUpdateProposedName}
                  onDeleteItem={handleDeleteItem}
                  onDeleteItems={handleDeleteItems}
                  onSubmitPlan={handleSubmitPlan}
                  onDiscardPlan={() => {
                    setPlanResult(null);
                    setSuccessMessage(null);
                    setErrorMessage(null);
                  }}
                  onRefreshPlan={handleRefreshPlan}
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
            <h3 className="font-semibold text-sm text-foreground">Saved Rename Plans</h3>
            <span className="text-xs text-muted-foreground">{existingPlans.length} plans</span>
          </div>

          {existingPlans.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">
              No rename change plans found. Generate a plan using the Create Plan tab.
            </p>
          ) : (
            <div className="divide-y divide-border/60">
              {existingPlans.map((plan) => (
                <div key={plan.id} className="py-3 flex items-center justify-between text-xs">
                  <div>
                    <h4 className="font-semibold text-foreground">{plan.title}</h4>
                    <p className="text-muted-foreground text-[11px] mt-0.5">
                      Created {formatDate(plan.created_at)} • {plan.items.length} operations
                    </p>
                  </div>
                  <span className="capitalize px-2.5 py-1 rounded-full text-[11px] font-semibold bg-muted text-foreground">
                    {plan.status.replace("_", " ")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab: Rename Rules */}
      {activeTab === "rules" && (
        <div className="p-12 text-center border border-border rounded-xl bg-card shadow-sm space-y-2">
          <ShieldCheck size={32} className="mx-auto text-primary/60" />
          <h4 className="font-semibold text-sm text-foreground">Approved Rename Rules</h4>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Configured naming conventions that can run automatically on newly added files when monitoring is active.
          </p>
        </div>
      )}

      {/* Tab: History */}
      {activeTab === "history" && (
        <div className="p-12 text-center border border-border rounded-xl bg-card shadow-sm space-y-2">
          <History size={32} className="mx-auto text-muted-foreground/60" />
          <h4 className="font-semibold text-sm text-foreground">Execution History</h4>
          <p className="text-xs text-muted-foreground max-w-md mx-auto">
            Audit logs and transactional history of executed rename operations.
          </p>
        </div>
      )}
      </div>
    </div>
  );
};

