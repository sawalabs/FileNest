import React, { useState } from "react";
import {
  X,
  AlertTriangle,
  FileText,
  Folder,
  Save,
  Loader2,
  FolderInput,
  FilePenLine,
  Trash2,
  FolderPlus,
  Copy,
} from "lucide-react";
import type { ChangePlanItemResponse } from "@/types";

interface ChangeDetailsModalProps {
  planId: string;
  item: ChangePlanItemResponse;
  isOpen: boolean;
  onClose: () => void;
  onItemUpdated: () => void;
  updatePlanItem: (planId: string, itemId: string, newDest: string) => Promise<any>;
}

export const ChangeDetailsModal: React.FC<ChangeDetailsModalProps> = ({
  planId,
  item,
  isOpen,
  onClose,
  onItemUpdated,
  updatePlanItem,
}) => {
  const [destinationPath, setDestinationPath] = useState(
    item.destination_relative_path || ""
  );
  const [isSaving, setIsSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!destinationPath.trim()) {
      setSaveError("Destination path cannot be empty");
      return;
    }
    setIsSaving(true);
    setSaveError(null);
    try {
      await updatePlanItem(planId, item.id, destinationPath.trim());
      onItemUpdated();
      onClose();
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : "Failed to update item path");
    } finally {
      setIsSaving(false);
    }
  };

  const getOperationIcon = (op: string) => {
    switch (op) {
      case "move":
        return <FolderInput size={16} className="text-blue-500" />;
      case "rename":
        return <FilePenLine size={16} className="text-amber-500" />;
      case "delete_to_recycle_bin":
        return <Trash2 size={16} className="text-rose-500" />;
      case "create_directory":
        return <FolderPlus size={16} className="text-emerald-500" />;
      case "copy":
        return <Copy size={16} className="text-blue-500" />;
      default:
        return <FileText size={16} className="text-muted-foreground" />;
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-card border border-border w-full max-w-2xl rounded-xl shadow-xl overflow-hidden flex flex-col">
        {/* Modal Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-muted border border-border">
              {getOperationIcon(item.operation)}
            </div>
            <div>
              <h3 className="font-semibold text-sm capitalize">
                {item.operation.replace(/_/g, " ")} Details
              </h3>
              <p className="text-xs text-muted-foreground">
                Step #{item.sequence_no} — Item ID: {item.id.slice(0, 8)}...
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
        <div className="p-5 space-y-5 overflow-y-auto max-h-[70vh]">
          {/* Conflict Alert (if any) */}
          {item.conflict_reason && (
            <div className="p-3.5 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400 text-xs flex items-start gap-2.5">
              <AlertTriangle size={16} className="shrink-0 mt-0.5 text-rose-600 dark:text-rose-400" />
              <div>
                <span className="font-semibold block">Validation Conflict Detected</span>
                <span>{item.conflict_reason}</span>
              </div>
            </div>
          )}

          {/* Side-by-Side Path Diff / Preview */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Operation Path Diff
            </label>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-3.5 rounded-lg border border-border bg-muted/20">
              {/* Source */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
                  <FileText size={13} />
                  Original Source Path
                </span>
                <div className="p-2.5 rounded bg-background border border-border text-xs font-mono break-all min-h-[42px] flex items-center">
                  {item.source_relative_path || <span className="text-muted-foreground italic">(None — Directory creation)</span>}
                </div>
              </div>

              {/* Destination */}
              <div className="space-y-1.5">
                <span className="text-[11px] font-medium text-muted-foreground flex items-center gap-1.5">
                  <Folder size={13} />
                  Proposed Destination Path
                </span>
                <div className="p-2.5 rounded bg-background border border-border text-xs font-mono break-all min-h-[42px] flex items-center">
                  {item.destination_relative_path || <span className="text-muted-foreground italic">(Recycle Bin)</span>}
                </div>
              </div>
            </div>
          </div>

          {/* Edit Destination Field */}
          {item.destination_relative_path && item.status !== "completed" && (
            <div className="space-y-2">
              <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Modify Proposed Destination
              </label>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={destinationPath}
                  onChange={(e) => setDestinationPath(e.target.value)}
                  placeholder="new/folder/path/filename.ext"
                  className="flex-1 px-3 py-2 rounded-md border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
                />
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving || destinationPath === item.destination_relative_path}
                  className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
                  <span>Save Path</span>
                </button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Modifying the destination re-evaluates collision checks and resets conflict status.
              </p>
              {saveError && (
                <p className="text-xs text-rose-600 dark:text-rose-400">{saveError}</p>
              )}
            </div>
          )}

          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 pt-2 border-t border-border text-xs">
            <div>
              <span className="text-muted-foreground block text-[11px]">Execution Status</span>
              <span className="font-medium capitalize">{item.status}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px]">Sequence Order</span>
              <span className="font-medium">Step #{item.sequence_no}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px]">Expected Size</span>
              <span className="font-medium">
                {item.expected_size_bytes != null
                  ? `${(item.expected_size_bytes / 1024).toFixed(1)} KB`
                  : "N/A"}
              </span>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-3 border-t border-border bg-muted/30 flex justify-end">
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
  );
};
