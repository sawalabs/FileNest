import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  Plus,
  Play,
  Pause,
  Trash2,
  CheckCircle2,
  CircleX,
  RefreshCw,
  FolderTree,
} from "lucide-react";
import { ApiService } from "@/services/api";
import type {
  ManagedFolder,
  OrganizationRuleResponse,
  RuleAction,
  RuleCondition,
} from "@/types";
import { formatDate } from "@/lib/utils";

interface OrganizationRulesPanelProps {
  folders: ManagedFolder[];
  selectedFolderId?: string;
}

export const OrganizationRulesPanel: React.FC<OrganizationRulesPanelProps> = ({
  folders,
  selectedFolderId,
}) => {
  const [rules, setRules] = useState<OrganizationRuleResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Rule creation form state
  const [isCreating, setIsCreating] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [folderId, setFolderId] = useState<string>(
    () => selectedFolderId || folders[0]?.id || ""
  );
  const [name, setName] = useState("");
  const [ruleType, setRuleType] = useState<"organize" | "rename">("organize");
  const [subpath, setSubpath] = useState("");
  const [extensionsInput, setExtensionsInput] = useState("");
  const [condField, setCondField] = useState("extension");
  const [condOp, setCondOp] = useState<RuleCondition["operator"]>("equals");
  const [condValue, setCondValue] = useState("pdf");
  const [targetDir, setTargetDir] = useState("Documents");
  const [namingPattern, setNamingPattern] = useState("{date}_{name}");

  useEffect(() => {
    if (!folderId && folders.length > 0) {
      setFolderId(selectedFolderId || folders[0].id);
    }
  }, [folders, selectedFolderId, folderId]);

  const loadRules = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await ApiService.listRules(selectedFolderId || undefined);
      setRules(data);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load organization rules"
      );
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadRules();
  }, [selectedFolderId]);

  const handleCreateRule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderId || name.trim().length < 3) {
      setError("Please select a Managed Folder and enter a rule name (min 3 characters).");
      return;
    }

    const extensions = extensionsInput
      .split(",")
      .map((s) => s.trim().replace(/^\./, "").toLowerCase())
      .filter(Boolean);

    const conditions: RuleCondition[] = condValue.trim()
      ? [
          {
            field: condField,
            operator: condOp,
            value:
              condField === "size_bytes"
                ? Number(condValue.trim()) || 0
                : condValue.trim(),
          },
        ]
      : [];

    const actions: RuleAction[] =
      ruleType === "organize"
        ? [
            {
              action_type: "move",
              target_directory: targetDir.trim() || "Organized",
              create_subfolders: false,
            },
          ]
        : [
            {
              action_type: "rename",
              naming_pattern: namingPattern.trim() || "{date}_{name}",
              create_subfolders: false,
            },
          ];

    setIsCreating(true);
    setError(null);
    setNotice(null);
    try {
      await ApiService.createRule({
        managed_folder_id: folderId,
        name: name.trim(),
        rule_type: ruleType,
        scope: {
          subpath: subpath.trim(),
          extensions,
        },
        conditions,
        actions,
        is_enabled: false,
      });
      setName("");
      setShowForm(false);
      setNotice("Organization rule created. Approve and enable it when ready for monitoring automation.");
      await loadRules();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to create organization rule"
      );
    } finally {
      setIsCreating(false);
    }
  };

  const handleApprove = async (ruleId: string) => {
    setError(null);
    setNotice(null);
    try {
      await ApiService.approveRule(ruleId, "user");
      setNotice("Rule approved for automated execution within its exact configured scope.");
      await loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to approve rule");
    }
  };

  const handleToggle = async (rule: OrganizationRuleResponse) => {
    setError(null);
    setNotice(null);
    try {
      await ApiService.toggleRule(rule.id, !rule.is_enabled);
      await loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to toggle rule state");
    }
  };

  const handleDelete = async (ruleId: string) => {
    setError(null);
    setNotice(null);
    try {
      await ApiService.deleteRule(ruleId);
      setNotice("Rule removed.");
      await loadRules();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete rule");
    }
  };

  const folderNameMap = new Map(folders.map((f) => [f.id, f.name]));

  return (
    <div className="space-y-4">
      {/* Header Toolbar */}
      <div className="p-4 rounded-xl border border-border bg-card shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="space-y-0.5">
          <h4 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <ShieldCheck size={16} className="text-primary" />
            <span>Automation Organization Rules</span>
          </h4>
          <p className="text-xs text-muted-foreground">
            Rules only run automatically inside approved scopes after explicit user approval.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadRules}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={() => setShowForm((v) => !v)}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-semibold transition-colors"
          >
            <Plus size={14} />
            <span>{showForm ? "Cancel" : "New Rule"}</span>
          </button>
        </div>
      </div>

      {notice && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 size={15} className="shrink-0" />
          <span>{notice}</span>
        </div>
      )}
      {error && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-xs text-destructive">
          <CircleX size={15} className="shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* New Rule Form */}
      {showForm && (
        <form
          onSubmit={handleCreateRule}
          className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3 text-xs"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Rule Name
              </label>
              <input
                type="text"
                required
                placeholder="e.g. Sort PDF Invoices"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background text-foreground"
              />
            </div>

            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Managed Folder
              </label>
              <select
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background text-foreground"
              >
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Rule Type
              </label>
              <select
                value={ruleType}
                onChange={(e) =>
                  setRuleType(e.target.value as "organize" | "rename")
                }
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background text-foreground"
              >
                <option value="organize">Organize (Move to Folder)</option>
                <option value="rename">Smart Rename</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Subpath Scope (optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Inbox (blank = root)"
                value={subpath}
                onChange={(e) => setSubpath(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
              />
            </div>

            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Extensions Scope (comma-separated)
              </label>
              <input
                type="text"
                placeholder="pdf, docx"
                value={extensionsInput}
                onChange={(e) => setExtensionsInput(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
              />
            </div>

            {ruleType === "organize" ? (
              <div>
                <label className="block font-medium text-muted-foreground mb-1">
                  Target Directory (relative)
                </label>
                <input
                  type="text"
                  placeholder="Documents/Invoices"
                  value={targetDir}
                  onChange={(e) => setTargetDir(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
                />
              </div>
            ) : (
              <div>
                <label className="block font-medium text-muted-foreground mb-1">
                  Naming Pattern
                </label>
                <input
                  type="text"
                  placeholder="{date}_{name}"
                  value={namingPattern}
                  onChange={(e) => setNamingPattern(e.target.value)}
                  className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
                />
              </div>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Match Field
              </label>
              <select
                value={condField}
                onChange={(e) => setCondField(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
              >
                <option value="extension">Extension</option>
                <option value="name">File Name</option>
                <option value="category">Category</option>
                <option value="size_bytes">Size (Bytes)</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Operator
              </label>
              <select
                value={condOp}
                onChange={(e) =>
                  setCondOp(e.target.value as RuleCondition["operator"])
                }
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
              >
                <option value="equals">equals</option>
                <option value="contains">contains</option>
                <option value="starts_with">starts_with</option>
                <option value="ends_with">ends_with</option>
                <option value="matches_regex">matches_regex</option>
                <option value="greater_than">greater_than</option>
                <option value="less_than">less_than</option>
              </select>
            </div>
            <div>
              <label className="block font-medium text-muted-foreground mb-1">
                Match Value
              </label>
              <input
                type="text"
                placeholder="pdf"
                value={condValue}
                onChange={(e) => setCondValue(e.target.value)}
                className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
              />
            </div>
          </div>

          <div className="flex justify-end pt-1">
            <button
              type="submit"
              disabled={isCreating}
              className="px-4 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 font-semibold disabled:opacity-50"
            >
              {isCreating ? "Saving..." : "Save Rule"}
            </button>
          </div>
        </form>
      )}

      {/* Rules List */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {rules.length === 0 ? (
          <div className="p-10 text-center space-y-2 text-muted-foreground">
            <ShieldCheck size={28} className="mx-auto opacity-40" />
            <p className="text-xs font-semibold text-foreground">
              No organization rules created yet
            </p>
            <p className="text-[11px] max-w-md mx-auto">
              Create a scoped rule to automate moving or renaming matching files once approved.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {rules.map((rule) => (
              <div
                key={rule.id}
                className="p-4 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs hover:bg-muted/20 transition-colors"
              >
                <div className="space-y-1 min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-foreground text-sm">
                      {rule.name}
                    </span>
                    <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground font-medium capitalize text-[11px]">
                      {rule.rule_type} (v{rule.version})
                    </span>
                    {rule.is_approved ? (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-[11px] font-medium">
                        <CheckCircle2 size={11} />
                        Approved
                      </span>
                    ) : (
                      <span className="px-2 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 text-[11px] font-medium">
                        Pending Approval
                      </span>
                    )}
                    <span
                      className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                        rule.is_enabled
                          ? "bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {rule.is_enabled ? "Active" : "Paused"}
                    </span>
                  </div>

                  <div className="flex flex-wrap items-center gap-3 text-[11px] text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <FolderTree size={12} />
                      {folderNameMap.get(rule.managed_folder_id) || rule.managed_folder_id}
                      {rule.scope.subpath ? `/${rule.scope.subpath}` : ""}
                    </span>
                    {rule.conditions.length > 0 && (
                      <span className="font-mono">
                        If{" "}
                        {rule.conditions
                          .map((c) => `${c.field} ${c.operator} "${c.value}"`)
                          .join(" AND ")}
                      </span>
                    )}
                    {rule.actions.length > 0 && (
                      <span className="font-mono text-foreground">
                        →{" "}
                        {rule.actions
                          .map((a) =>
                            a.action_type === "move"
                              ? `move to ${a.target_directory}`
                              : `${a.action_type} (${a.naming_pattern || ""})`
                          )
                          .join(", ")}
                      </span>
                    )}
                    <span>Updated {formatDate(rule.updated_at)}</span>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {!rule.is_approved && (
                    <button
                      type="button"
                      onClick={() => handleApprove(rule.id)}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-emerald-600 text-white hover:bg-emerald-700 font-medium"
                    >
                      <CheckCircle2 size={12} />
                      <span>Approve</span>
                    </button>
                  )}
                  <button
                    type="button"
                    disabled={!rule.is_approved && !rule.is_enabled}
                    onClick={() => handleToggle(rule)}
                    title={
                      !rule.is_approved
                        ? "Approve rule before enabling automatic execution"
                        : rule.is_enabled
                        ? "Pause automated rule"
                        : "Enable automated rule"
                    }
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-border bg-background hover:bg-muted font-medium disabled:opacity-40"
                  >
                    {rule.is_enabled ? (
                      <>
                        <Pause size={12} />
                        <span>Pause</span>
                      </>
                    ) : (
                      <>
                        <Play size={12} />
                        <span>Enable</span>
                      </>
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDelete(rule.id)}
                    title="Delete rule"
                    className="p-1.5 rounded-md border border-border text-muted-foreground hover:text-destructive hover:border-destructive/40 transition-colors"
                  >
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
