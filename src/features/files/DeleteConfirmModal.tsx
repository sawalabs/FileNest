import React, { useState } from "react";
import { Trash2, AlertTriangle, X } from "lucide-react";
import { FileIcon } from "./FileIcon";
import type { FileItemMetadata } from "@/types";

interface DeleteConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (relativePaths: string[]) => Promise<void>;
  items: FileItemMetadata[];
}

export const DeleteConfirmModal: React.FC<DeleteConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  items,
}) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || items.length === 0) return null;

  const handleConfirm = async () => {
    try {
      setIsDeleting(true);
      setError(null);
      await onConfirm(items.map((i) => i.relative_path));
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to delete items");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2 text-destructive font-semibold">
            <Trash2 size={20} />
            <span>Delete Confirmation</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <div className="space-y-3">
          <div className="flex items-start gap-3 rounded-md bg-amber-500/10 border border-amber-500/20 p-3 text-xs text-amber-700 dark:text-amber-400">
            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
            <span>
              This action will move {items.length} item{items.length > 1 ? "s" : ""} to the <strong>Windows Recycle Bin</strong>. Items can be restored from the Recycle Bin if needed.
            </span>
          </div>

          <div className="max-h-48 overflow-y-auto rounded-md border border-border bg-muted/30 p-2 divide-y divide-border/60">
            {items.map((item) => (
              <div
                key={item.relative_path}
                className="flex items-center gap-2.5 py-1.5 px-2 text-xs"
              >
                <FileIcon
                  itemType={item.item_type}
                  category={item.category}
                  extension={item.extension}
                  size={16}
                />
                <span className="font-medium text-foreground truncate flex-1">
                  {item.name}
                </span>
                <span className="text-muted-foreground text-[11px]">
                  {item.item_type === "directory" ? "Folder" : `${Math.round(item.size_bytes / 1024)} KB`}
                </span>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="p-2.5 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs">
            {error}
          </div>
        )}

        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-4 py-2 text-xs font-medium rounded-md border border-border bg-muted/50 hover:bg-muted text-foreground transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting}
            className="px-4 py-2 text-xs font-medium rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors disabled:opacity-50"
          >
            {isDeleting ? "Deleting..." : "Delete"}
          </button>
        </div>
      </div>
    </div>
  );
};
