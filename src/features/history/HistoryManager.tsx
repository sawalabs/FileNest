import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Download,
  User,
  Sparkles,
  Cpu,
  Search,
  Eye,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  FileText,
  Activity,
  ChevronDown,
  History,
  FolderTree,
  ShieldCheck,
  Zap,
  Radio,
  LayoutList,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { usePreferences } from "@/contexts/PreferencesContext";
import { HistorySummaryCards } from "./HistorySummaryCards";
import { AuditLogDetailsModal } from "./AuditLogDetailsModal";
import { ExecutionDetailsModal } from "./ExecutionDetailsModal";
import type {
  AuditLogItem,
  ExecutionHistoryItem,
  HistorySummaryStats,
  ManagedFolder,
  UndoExecutionResponse,
} from "@/types";
import { cn } from "@/lib/utils";

type HistoryTab =
  | "all"
  | "file_changes"
  | "plans_approvals"
  | "executions"
  | "monitoring"
  | "rules"
  | "system";

export const HistoryManager: React.FC = () => {
  const { defaultTableDensity } = usePreferences();
  const rowPad = defaultTableDensity === "compact" ? "py-1.5 px-3" : "py-2.5 px-3.5";

  const [activeTab, setActiveTab] = useState<HistoryTab>("all");
  const [isLoading, setIsLoading] = useState(false);
  const [stats, setStats] = useState<HistorySummaryStats>({
    total_activities: 0,
    file_changes_count: 0,
    executions_succeeded: 0,
    executions_failed: 0,
    rollbacks_count: 0,
    pending_plans_count: 0,
  });

  // Audit Logs state
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [totalLogs, setTotalLogs] = useState(0);

  // Execution history state
  const [executionJobs, setExecutionJobs] = useState<ExecutionHistoryItem[]>([]);
  const [totalExecutions, setTotalExecutions] = useState(0);

  // Folders for filtering
  const [folders, setFolders] = useState<ManagedFolder[]>([]);

  // Filters
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [selectedActor, setSelectedActor] = useState<string>("all");
  const [selectedFolderId, setSelectedFolderId] = useState<string>("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  // Modals & Undo feedback
  const [inspectingLog, setInspectingLog] = useState<AuditLogItem | null>(null);
  const [inspectingJob, setInspectingJob] = useState<ExecutionHistoryItem | null>(null);
  const [isExportDropdownOpen, setIsExportDropdownOpen] = useState(false);
  const [confirmUndoJobId, setConfirmUndoJobId] = useState<string | null>(null);
  const [undoingJobId, setUndoingJobId] = useState<string | null>(null);
  const [undoNotice, setUndoNotice] = useState<string | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);

  const handleQuickUndo = async (job: ExecutionHistoryItem) => {
    setUndoingJobId(job.id);
    setUndoNotice(null);
    setUndoError(null);
    try {
      const res = await ApiService.undoExecutionJob(job.id);
      setUndoNotice(
        `Reverted "${job.change_plan_title}" (${res.status}): ${res.reverted_count} reverted, ${res.skipped_count} skipped, ${res.failed_count} failed.`
      );
      setConfirmUndoJobId(null);
      await Promise.all([loadStatsAndFolders(), loadRecords()]);
    } catch (err: unknown) {
      setUndoError(
        err instanceof Error ? err.message : "Failed to revert execution job"
      );
    } finally {
      setUndoingJobId(null);
    }
  };

  // Load stats & folders
  const loadStatsAndFolders = async () => {
    try {
      const [s, f] = await Promise.all([
        ApiService.getHistoryStats(),
        ApiService.listFolders(),
      ]);
      setStats(s);
      setFolders(f);
    } catch {
      // ignore non-fatal stats load errors
    }
  };

  // Load tab records
  const loadRecords = useCallback(async () => {
    setIsLoading(true);
    try {
      if (activeTab === "executions") {
        const params: Record<string, any> = { limit: 100 };
        if (selectedStatus !== "all") params.status = selectedStatus;
        if (selectedFolderId !== "all") params.folder_id = selectedFolderId;
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;

        const res = await ApiService.getExecutionHistory(params);
        setExecutionJobs(res.items);
        setTotalExecutions(res.total);
      } else {
        const params: Record<string, any> = { limit: 150 };
        if (activeTab !== "all") params.category = activeTab;
        if (selectedActor !== "all") params.actor_type = selectedActor;
        if (startDate) params.start_date = startDate;
        if (endDate) params.end_date = endDate;
        if (searchQuery.trim()) params.search = searchQuery.trim();

        const res = await ApiService.getAuditLogs(params);
        setAuditLogs(res.items);
        setTotalLogs(res.total);
      }
    } catch (err) {
      console.error("Failed to load history records", err);
    } finally {
      setIsLoading(false);
    }
  }, [activeTab, selectedStatus, selectedFolderId, selectedActor, startDate, endDate, searchQuery]);

  useEffect(() => {
    loadStatsAndFolders();
  }, []);

  useEffect(() => {
    loadRecords();
  }, [loadRecords]);

  // Export handlers
  const handleExport = async (format: "csv" | "json") => {
    setIsExportDropdownOpen(false);
    try {
      const params: Record<string, any> = {};
      if (activeTab !== "all" && activeTab !== "executions") {
        params.category = activeTab;
      }
      if (selectedActor !== "all") params.actor_type = selectedActor;
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;
      if (searchQuery.trim()) params.search = searchQuery.trim();

      const blob = await ApiService.exportHistory(format, params);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `activity_history_${new Date().toISOString().slice(0, 10)}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      console.error("Export failed", err);
    }
  };

  const resetFilters = () => {
    setStartDate("");
    setEndDate("");
    setSelectedActor("all");
    setSelectedFolderId("all");
    setSelectedStatus("all");
    setSearchQuery("");
  };

  const getActorBadge = (actor: string) => {
    switch (actor) {
      case "ai":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-secondary text-secondary-foreground border border-border">
            <Sparkles size={11} className="text-muted-foreground" />
            AI
          </span>
        );
      case "user":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <User size={11} />
            User
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground border border-border">
            <Cpu size={11} />
            System
          </span>
        );
    }
  };

  const getExecutionStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={12} />
            Completed
          </span>
        );
      case "rolled_back":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <RotateCcw size={12} />
            Rolled Back
          </span>
        );
      case "failed":
      case "partial":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <AlertTriangle size={12} />
            {status === "partial" ? "Partial" : "Failed"}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground border border-border">
            {status}
          </span>
        );
    }
  };

  const currentRecordsCount =
    activeTab === "executions" ? totalExecutions : totalLogs;

  const tabConfig = [
    { id: "all" as const, label: "All Activities", icon: LayoutList },
    { id: "file_changes" as const, label: "File Changes", icon: FileText },
    { id: "plans_approvals" as const, label: "Plans & Approvals", icon: ShieldCheck },
    { id: "executions" as const, label: "Executions", icon: Zap },
    { id: "monitoring" as const, label: "Monitoring", icon: Radio },
    { id: "rules" as const, label: "Rules", icon: FolderTree },
    { id: "system" as const, label: "System", icon: Cpu },
  ];

  return (
    <div className="h-full w-full flex flex-col min-h-0 overflow-hidden bg-background">
      {/* Top Header Bar — Flush to top edge */}
      <div className="h-14 border-b border-border bg-card/60 backdrop-blur-xs flex items-center justify-between px-4 sm:px-6 shrink-0 z-20">
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
            <History size={18} />
          </div>
          <div className="min-w-0">
            <h1 className="text-base font-bold tracking-tight text-foreground truncate">
              History
            </h1>
            <p className="text-[11px] text-muted-foreground truncate hidden md:block">
              View and audit all activities, changes, approvals, executions, and system events.
            </p>
          </div>
        </div>

        {/* Tab pills right in the top header */}
        <div className="flex items-center bg-muted/60 p-1 rounded-lg border border-border/50 text-xs shrink-0">
          {tabConfig.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all",
                  activeTab === tab.id
                    ? "bg-background text-foreground shadow-xs font-semibold"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                <Icon size={13} />
                <span className="hidden lg:inline">{tab.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Offset Content Scroll Area */}
      <div className="flex-1 min-h-0 overflow-y-auto p-4 md:p-6 space-y-5">
        {/* Summary Cards */}
        <HistorySummaryCards stats={stats} />

        {/* Action Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">
              Total: {currentRecordsCount} records
            </span>
            <button
              type="button"
              onClick={() => {
                loadStatsAndFolders();
                loadRecords();
              }}
              disabled={isLoading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </button>
          </div>

          {/* Export Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setIsExportDropdownOpen(!isExportDropdownOpen)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors shadow-xs"
            >
              <Download size={14} />
              <span>Export History</span>
              <ChevronDown size={12} />
            </button>

            {isExportDropdownOpen && (
              <div className="absolute right-0 mt-1.5 w-36 rounded-md border border-border bg-card shadow-lg z-20 py-1 text-xs animate-in fade-in">
                <button
                  type="button"
                  onClick={() => handleExport("csv")}
                  className="w-full text-left px-3 py-1.5 hover:bg-muted flex items-center gap-2"
                >
                  <FileText size={13} className="text-emerald-500" />
                  <span>Export CSV</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleExport("json")}
                  className="w-full text-left px-3 py-1.5 hover:bg-muted flex items-center gap-2"
                >
                  <FileText size={13} className="text-blue-500" />
                  <span>Export JSON</span>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-card border border-border rounded-lg">
          <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[280px]">
            {/* Search Input (For Audit Logs) */}
            {activeTab !== "executions" && (
              <div className="relative flex-1 min-w-[180px]">
                <Search
                  size={14}
                  className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search action, entity, details..."
                  className="w-full pl-8 pr-3 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>
            )}

            {/* Actor Filter (For Audit Logs) */}
            {activeTab !== "executions" && (
              <select
                value={selectedActor}
                onChange={(e) => setSelectedActor(e.target.value)}
                className="px-2.5 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="all">All Actors</option>
                <option value="user">User</option>
                <option value="ai">AI Agent</option>
                <option value="system">System</option>
              </select>
            )}

            {/* Status Filter (For Executions) */}
            {activeTab === "executions" && (
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value)}
                className="px-2.5 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="all">All Statuses</option>
                <option value="completed">Completed</option>
                <option value="rolled_back">Rolled Back</option>
                <option value="failed">Failed</option>
                <option value="partial">Partial</option>
              </select>
            )}

            {/* Folder Filter (For Executions) */}
            {activeTab === "executions" && (
              <select
                value={selectedFolderId}
                onChange={(e) => setSelectedFolderId(e.target.value)}
                className="px-2.5 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="all">All Managed Folders</option>
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.name}
                  </option>
                ))}
              </select>
            )}

            {/* Date Range Start */}
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground text-[11px]">From:</span>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>

            {/* Date Range End */}
            <div className="flex items-center gap-1 text-xs">
              <span className="text-muted-foreground text-[11px]">To:</span>
              <input
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
            </div>
          </div>

          <button
            type="button"
            onClick={resetFilters}
            className="px-2.5 py-1.5 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
          >
            Reset Filters
          </button>
        </div>

        {/* Undo Feedback Banners */}
        {undoNotice && (
          <div className="flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/30 text-xs text-emerald-700 dark:text-emerald-300">
            <div className="flex items-center gap-2">
              <CheckCircle2 size={15} className="shrink-0" />
              <span>{undoNotice}</span>
            </div>
            <button
              type="button"
              onClick={() => setUndoNotice(null)}
              className="text-[11px] underline"
            >
              Dismiss
            </button>
          </div>
        )}
        {undoError && (
          <div className="flex items-center justify-between gap-2 px-3.5 py-2.5 rounded-lg bg-rose-500/10 border border-rose-500/30 text-xs text-rose-700 dark:text-rose-300">
            <div className="flex items-center gap-2">
              <AlertTriangle size={15} className="shrink-0" />
              <span>{undoError}</span>
            </div>
            <button
              type="button"
              onClick={() => setUndoError(null)}
              className="text-[11px] underline"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Table Section */}
        {activeTab === "executions" ? (
          /* Executions Table */
          <div className="border border-border rounded-lg bg-card overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3.5">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3.5">Plan Title</th>
                  <th className="py-2.5 px-3.5">Managed Folder</th>
                  <th className="py-2.5 px-3.5">Status</th>
                  <th className="py-2.5 px-3.5">Operations</th>
                  <th className="py-2.5 px-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {executionJobs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-muted-foreground">
                      <Activity size={32} className="mx-auto mb-2 opacity-50" />
                      <span>No execution jobs found matching filters.</span>
                    </td>
                  </tr>
                ) : (
                  executionJobs.map((job) => (
                    <tr key={job.id} className="hover:bg-muted/20 transition-colors">
                      <td className={`${rowPad} font-mono text-muted-foreground`}>
                        {job.created_at}
                      </td>
                      <td className={`${rowPad} font-medium text-foreground`}>
                        {job.change_plan_title}
                      </td>
                      <td className={`${rowPad} text-muted-foreground`}>
                        {job.managed_folder_name}
                      </td>
                      <td className={`${rowPad}`}>{getExecutionStatusBadge(job.status)}</td>
                      <td className={`${rowPad}`}>
                        <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                          {job.completed_count}
                        </span>
                        {" / "}
                        <span>{job.operations_count} completed</span>
                        {job.rolled_back_count > 0 && (
                          <span className="ml-1.5 text-amber-600 dark:text-amber-400">
                            ({job.rolled_back_count} rolled back)
                          </span>
                        )}
                      </td>
                      <td className={`${rowPad} text-right`}>
                        <div className="inline-flex items-center justify-end gap-1.5">
                          {(job.status === "completed" || job.status === "partial") &&
                            (confirmUndoJobId === job.id ? (
                              <>
                                <button
                                  type="button"
                                  disabled={undoingJobId === job.id}
                                  onClick={() => handleQuickUndo(job)}
                                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-amber-600 text-white hover:bg-amber-700 text-xs font-semibold transition-colors disabled:opacity-50"
                                >
                                  <RotateCcw
                                    size={12}
                                    className={undoingJobId === job.id ? "animate-spin" : ""}
                                  />
                                  <span>
                                    {undoingJobId === job.id ? "Reverting..." : "Confirm Undo"}
                                  </span>
                                </button>
                                <button
                                  type="button"
                                  disabled={undoingJobId === job.id}
                                  onClick={() => setConfirmUndoJobId(null)}
                                  className="px-2 py-1 rounded-md border border-border bg-background hover:bg-muted text-xs"
                                >
                                  Cancel
                                </button>
                              </>
                            ) : (
                              <button
                                type="button"
                                onClick={() => setConfirmUndoJobId(job.id)}
                                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 text-xs font-medium transition-colors"
                              >
                                <RotateCcw size={12} />
                                <span>Undo</span>
                              </button>
                            ))}
                          <button
                            type="button"
                            onClick={() => setInspectingJob(job)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
                          >
                            <Eye size={13} />
                            <span>Inspect Ops</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* Audit Logs Table */
          <div className="border border-border rounded-lg bg-card overflow-hidden">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3.5 w-44">Timestamp (UTC)</th>
                  <th className="py-2.5 px-3.5 w-24">Actor</th>
                  <th className="py-2.5 px-3.5 w-48">Action Event</th>
                  <th className="py-2.5 px-3.5 w-36">Target Entity</th>
                  <th className="py-2.5 px-3.5">Details Snapshot</th>
                  <th className="py-2.5 px-3.5 w-16 text-right"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {auditLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-muted-foreground">
                      <Activity size={32} className="mx-auto mb-2 opacity-50" />
                      <span>No audit logs recorded for this category yet.</span>
                    </td>
                  </tr>
                ) : (
                  auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-muted/20 transition-colors">
                      <td className={`${rowPad} font-mono text-muted-foreground`}>
                        {log.created_at}
                      </td>
                      <td className={`${rowPad}`}>{getActorBadge(log.actor_type)}</td>
                      <td className={`${rowPad} font-mono font-medium text-foreground`}>
                        {log.action}
                      </td>
                      <td className={`${rowPad} font-mono text-muted-foreground`}>
                        {log.entity_type}
                      </td>
                      <td className={`${rowPad} font-mono text-[11px] text-muted-foreground truncate max-w-xs`}>
                        {log.details ? JSON.stringify(log.details) : "—"}
                      </td>
                      <td className={`${rowPad} text-right`}>
                        <button
                          type="button"
                          onClick={() => setInspectingLog(log)}
                          title="View complete record"
                          className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                        >
                          <Eye size={14} />
                        </button>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Audit Log Inspector Modal */}
      {inspectingLog && (
        <AuditLogDetailsModal
          log={inspectingLog}
          isOpen={true}
          onClose={() => setInspectingLog(null)}
        />
      )}

      {/* Execution Details & Rollback Inspector Modal */}
      {inspectingJob && (
        <ExecutionDetailsModal
          job={inspectingJob}
          isOpen={true}
          onClose={() => setInspectingJob(null)}
          onJobReverted={(res: UndoExecutionResponse) => {
            setUndoNotice(
              `Reverted "${inspectingJob.change_plan_title}" (${res.status}): ${res.reverted_count} reverted, ${res.skipped_count} skipped, ${res.failed_count} failed.`
            );
            loadStatsAndFolders();
            loadRecords();
          }}
        />
      )}
    </div>
  );
};
