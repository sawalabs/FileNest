import React, { useState, useEffect } from "react";
import { FolderInput, Copy, Folder, X, ChevronRight } from "lucide-react";
import { ApiService } from "@/services/api";
import type { FileItemMetadata } from "@/types";

interface MoveCopyModalProps {
  isOpen: boolean;
  mode: "move" | "copy";
  onClose: () => void;
  onSubmit: (sourcePaths: string[], destinationDirectory: string) => Promise<void>;
  items: FileItemMetadata[];
  managedFolderId: string;
}

interface FolderOption {
  name: string;
  relative_path: string;
}

export const MoveCopyModal: React.FC<MoveCopyModalProps> = ({
  isOpen,
  mode,
  onClose,
  onSubmit,
  items,
  managedFolderId,
}) => {
  const [availableFolders, setAvailableFolders] = useState<FolderOption[]>([]);
  const [selectedDest, setSelectedDest] = useState<string>("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen && managedFolderId) {
      loadFolders();
    }
  }, [isOpen, managedFolderId]);

  const loadFolders = async () => {
    try {
      setIsLoading(true);
      setError(null);
      // Browse root to list directories
      const rootRes = await ApiService.browseDirectory(managedFolderId, "");
      const dirs: FolderOption[] = [
        { name: "Root Folder", relative_path: "" },
        ...rootRes.entries
          .filter((i) => i.item_type === "directory")
          .map((i) => ({ name: i.name, relative_path: i.relative_path })),
      ];
      setAvailableFolders(dirs);
      setSelectedDest("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load destination folders");
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen || items.length === 0) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      setError(null);
      await onSubmit(
        items.map((i) => i.relative_path),
        selectedDest
      );
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : `Failed to ${mode} items`);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2 text-foreground font-semibold">
            {mode === "move" ? (
              <FolderInput size={20} className="text-primary" />
            ) : (
              <Copy size={20} className="text-primary" />
            )}
            <span>
              {mode === "move" ? "Move" : "Copy"} {items.length} Item
              {items.length > 1 ? "s" : ""}
            </span>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-medium text-foreground">
              Select Destination Directory
            </label>
            {isLoading ? (
              <div className="p-4 text-center text-xs text-muted-foreground">
                Loading folders...
              </div>
            ) : (
              <div className="max-h-52 overflow-y-auto rounded-md border border-border bg-background divide-y divide-border/60">
                {availableFolders.map((folder) => {
                  const isSelected = selectedDest === folder.relative_path;
                  return (
                    <button
                      key={folder.relative_path}
                      type="button"
                      onClick={() => setSelectedDest(folder.relative_path)}
                      className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs text-left transition-colors ${
                        isSelected
                          ? "bg-primary/10 text-primary font-semibold"
                          : "hover:bg-muted text-foreground"
                      }`}
                    >
                      <Folder
                        size={16}
                        className={
                          isSelected ? "text-primary" : "text-amber-500 fill-amber-500/20"
                        }
                      />
                      <span className="flex-1 truncate">{folder.name}</span>
                      {isSelected && <ChevronRight size={14} />}
                    </button>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground">
              Destination: {selectedDest ? `/${selectedDest}` : "/ (Root)"}
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
              disabled={isSubmitting}
              className="px-4 py-2 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {isSubmitting
                ? `${mode === "move" ? "Moving" : "Copying"}...`
                : mode === "move"
                ? "Move Here"
                : "Copy Here"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
