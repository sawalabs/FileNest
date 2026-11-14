import React, { useState, useEffect } from "react";
import { Pencil, X } from "lucide-react";
import type { FileItemMetadata } from "@/types";

interface RenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (sourcePath: string, newName: string) => Promise<void>;
  item: FileItemMetadata | null;
}

export const RenameModal: React.FC<RenameModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  item,
}) => {
  const [newName, setNewName] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (item) {
      setNewName(item.name);
      setError(null);
    }
  }, [item]);

  if (!isOpen || !item) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newName.trim();
    if (!trimmed) {
      setError("Name cannot be empty");
      return;
    }
    if (trimmed === item.name) {
      onClose();
      return;
    }
    if (/[\\/:*?"<>|]/.test(trimmed)) {
      setError("Name cannot contain \\ / : * ? \" < > |");
      return;
    }

    try {
      setIsSubmitting(true);
      setError(null);
      await onSubmit(item.relative_path, trimmed);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to rename");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2 text-foreground font-semibold">
            <Pencil size={20} className="text-primary" />
            <span>Rename {item.item_type === "directory" ? "Folder" : "File"}</span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground">
              New Name
            </label>
            <input
              type="text"
              autoFocus
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                if (error) setError(null);
              }}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary"
            />
            <p className="text-[11px] text-muted-foreground">
              Original: {item.name}
            </p>
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
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium rounded-md border border-border bg-muted/50 hover:bg-muted text-foreground transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting || !newName.trim()}
              className="px-4 py-2 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isSubmitting ? "Renaming..." : "Rename"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
