import React, { useState } from "react";
import {
  X,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  FolderInput,
  FilePenLine,
  Trash2,
  FolderPlus,
  Copy,
  FileText,
  ArrowRight,
  ShieldAlert,
  HardDrive,
} from "lucide-react";
import { ApiService } from "@/services/api";
import type { ExecutionHistoryItem, UndoExecutionResponse } from "@/types";

interface ExecutionDetailsModalProps {
  job: ExecutionHistoryItem;
  isOpen: boolean;
  onClose: () => void;
  onJobReverted?: (result: UndoExecutionResponse) => void;
}

export const ExecutionDetailsModal: React.FC<ExecutionDetailsModalProps> = ({
  job,
  isOpen,
  onClose,
  onJobReverted,
}) => {
  const [confirmUndo, setConfirmUndo] = useState(false);
  const [isUndoing, setIsUndoing] = useState(false);
  const [undoError, setUndoError] = useState<string | null>(null);
  const [undoResult, setUndoResult] = useState<UndoExecutionResponse | null>(null);

  if (!isOpen) return null;

  const canUndo =
    (job.status === "completed" || job.status === "partial") && !undoResult;

  const handleUndo = async () => {
    setIsUndoing(true);
    setUndoError(null);
    try {
      const res = await ApiService.undoExecutionJob(job.id);
      setUndoResult(res);
      setConfirmUndo(false);
      onJobReverted?.(res);
    } catch (err: unknown) {
      setUndoError(
        err instanceof Error ? err.message : "Failed to undo execution job"
      );
    } finally {
      setIsUndoing(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 size={13} />
            Completed
          </span>
        );
      case "rolled_back":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <RotateCcw size={13} />
            Rolled Back
          </span>
        );
      case "failed":
      case "partial":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <AlertTriangle size={13} />
            {status === "partial" ? "Partial Rollback" : "Failed"}
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-muted text-muted-foreground border border-border">
            {status}
          </span>
        );
    }
  };

  const getOpBadge = (op: string) => {
    switch (op) {
      case "move":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FolderInput size={12} />
            Move
          </span>
        );
      case "rename":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border border-indigo-500/20">
            <FilePenLine size={12} />
            Rename
          </span>
        );
      case "delete_to_recycle_bin":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <Trash2 size={12} />
            Delete
          </span>
        );
      case "create_directory":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <FolderPlus size={12} />
            Folder
          </span>
        );
      case "copy":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <Copy size={12} />
            Copy
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground border border-border">
            <FileText size={12} />
            {op}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-card border border-border w-full max-w-4xl rounded-xl shadow-xl overflow-hidden flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-muted border border-border">
              <HardDrive size={18} className="text-primary" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-sm">{job.change_plan_title}</h3>
                {getStatusBadge(job.status)}
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                Job ID: {job.id} • Folder: <strong>{job.managed_folder_name}</strong>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 space-y-4 overflow-y-auto flex-1">
          {/* Failure / Rollback Banner */}
          {job.error_message && (
            <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400 text-xs flex items-start gap-2.5">
              <AlertTriangle size={16} className="shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <div>
                <span className="font-semibold block">Execution Failure Triggered Rollback</span>
                <span>{job.error_message}</span>
              </div>
            </div>
          )}

          {job.status === "rolled_back" && (
            <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-400 text-xs flex items-center gap-2">
              <RotateCcw size={15} />
              <span>
                <strong>Best-Effort Rollback Completed:</strong> Completed mutations prior to the error were safely reversed.
              </span>
            </div>
          )}

          {/* Timing & Metric Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs p-3.5 rounded-lg border border-border bg-muted/20">
            <div>
              <span className="text-muted-foreground block text-[11px] mb-0.5">Started At</span>
              <span className="font-mono">{job.started_at || job.created_at}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-0.5">Finished At</span>
              <span className="font-mono">{job.finished_at || "—"}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-0.5">Completed Operations</span>
              <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                {job.completed_count} / {job.operations_count}
              </span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-0.5">Rollbacks / Failed</span>
              <span className="font-semibold text-amber-600 dark:text-amber-400">
                {job.rolled_back_count} reverted • {job.failed_count} failed
              </span>
            </div>
          </div>

          {/* Operation Logs / Snapshots Table */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Persistent Operation Audit & Path Snapshots
              </label>
              <span className="text-[11px] text-muted-foreground">
                Preserved independently of disk file existence
              </span>
            </div>

            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-2 px-3 w-10 text-center">#</th>
                    <th className="py-2 px-3 w-28">Operation</th>
                    <th className="py-2 px-3">Source Snapshot</th>
                    <th className="py-2 px-3 w-6 text-center"></th>
                    <th className="py-2 px-3">Destination Snapshot</th>
                    <th className="py-2 px-3 w-32">Operation Status</th>
                    <th className="py-2 px-3 w-28">Backup Ref</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {job.operation_logs.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-4 text-center text-muted-foreground">
                        No operation logs recorded.
                      </td>
                    </tr>
                  ) : (
                    job.operation_logs.map((op, idx) => (
                      <tr key={op.id || idx} className="hover:bg-muted/20">
                        <td className="py-2.5 px-3 text-center text-muted-foreground font-mono">
                          {idx + 1}
                        </td>
                        <td className="py-2.5 px-3">{getOpBadge(op.operation)}</td>
                        <td className="py-2.5 px-3 font-mono text-foreground break-all max-w-[200px]">
                          {op.source_path_snapshot || <span className="text-muted-foreground italic">—</span>}
                        </td>
                        <td className="py-2.5 px-3 text-center text-muted-foreground">
                          <ArrowRight size={13} />
                        </td>
                        <td className="py-2.5 px-3 font-mono text-foreground break-all max-w-[200px]">
                          {op.destination_path_snapshot || <span className="text-muted-foreground italic">—</span>}
                        </td>
                        <td className="py-2.5 px-3">
                          {op.status === "completed" && (
                            <span className="inline-flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-medium">
                              <CheckCircle2 size={13} />
                              Completed
                            </span>
                          )}
                          {op.status === "rollback_completed" && (
                            <span className="inline-flex items-center gap-1 text-amber-600 dark:text-amber-400 font-medium">
                              <RotateCcw size={13} />
                              Rolled Back
                            </span>
                          )}
                          {op.status === "failed" && (
                            <span
                              title={op.error_message || "Failed"}
                              className="inline-flex items-center gap-1 text-rose-600 dark:text-rose-400 font-medium"
                            >
                              <AlertTriangle size={13} />
                              Failed
                            </span>
                          )}
                          {op.status === "rollback_failed" && (
                            <span className="inline-flex items-center gap-1 text-rose-700 font-bold">
                              <ShieldAlert size={13} />
                              Rollback Error
                            </span>
                          )}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-[11px] text-muted-foreground">
                          {op.backup_reference || "—"}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-border bg-muted/30 flex flex-wrap items-center justify-between gap-3">
          <div className="flex-1 min-w-0 text-xs">
            {undoResult && (
              <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400 font-medium">
                <CheckCircle2 size={14} className="shrink-0" />
                <span>
                  Undo {undoResult.status}: {undoResult.reverted_count} reverted,{" "}
                  {undoResult.skipped_count} skipped, {undoResult.failed_count} failed.
                </span>
              </div>
            )}
            {undoError && (
              <div className="flex items-center gap-2 text-rose-600 dark:text-rose-400 font-medium">
                <AlertTriangle size={14} className="shrink-0" />
                <span>{undoError}</span>
              </div>
            )}
          </div>

          <div className="flex items-center gap-2">
            {canUndo && !confirmUndo && (
              <button
                type="button"
                onClick={() => setConfirmUndo(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold border border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-300 hover:bg-amber-500/20 transition-colors"
              >
                <RotateCcw size={13} />
                <span>Undo Execution</span>
              </button>
            )}
            {canUndo && confirmUndo && (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={isUndoing}
                  onClick={handleUndo}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-amber-600 text-white hover:bg-amber-700 transition-colors disabled:opacity-50"
                >
                  <RotateCcw size={13} className={isUndoing ? "animate-spin" : ""} />
                  <span>{isUndoing ? "Reverting..." : "Confirm Revert Ops"}</span>
                </button>
                <button
                  type="button"
                  disabled={isUndoing}
                  onClick={() => setConfirmUndo(false)}
                  className="px-2.5 py-1.5 rounded-md text-xs border border-border bg-background hover:bg-muted"
                >
                  Cancel
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
