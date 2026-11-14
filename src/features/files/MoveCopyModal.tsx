import React, { useState, useEffect } from "react";
import { FolderInput, Copy, Folder, HardDrive, X, ChevronRight, ShieldCheck, AlertCircle } from "lucide-react";
import { ApiService } from "@/services/api";
import type { FileItemMetadata, ManagedFolder } from "@/types";

interface MoveCopyModalProps {
  isOpen: boolean;
  mode: "move" | "copy";
  onClose: () => void;
  onSubmit: (
    sourcePaths: string[],
    destinationDirectory: string,
    targetFolderId?: string,
    conflictResolution?: "fail" | "rename" | "skip"
  ) => Promise<void>;
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
  const [allFolders, setAllFolders] = useState<ManagedFolder[]>([]);
  const [targetFolderId, setTargetFolderId] = useState<string>(managedFolderId);
  const [availableFolders, setAvailableFolders] = useState<FolderOption[]>([]);
  const [selectedDest, setSelectedDest] = useState<string>("");
  const [conflictResolution, setConflictResolution] = useState<"fail" | "rename" | "skip">("rename");
  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setTargetFolderId(managedFolderId);
      loadAllManagedFolders();
    }
  }, [isOpen, managedFolderId]);

  useEffect(() => {
    if (isOpen && targetFolderId) {
      loadSubfolders(targetFolderId);
    }
  }, [isOpen, targetFolderId]);

  const loadAllManagedFolders = async () => {
    try {
      const folders = await ApiService.listFolders(true);
      setAllFolders(folders);
    } catch (err: unknown) {
      console.error("Failed to load managed folders:", err);
    }
  };

  const loadSubfolders = async (folderId: string) => {
    try {
      setIsLoading(true);
      setError(null);
      const rootRes = await ApiService.browseDirectory(folderId, "");
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

  const currentFolder = allFolders.find((f) => f.id === managedFolderId);
  const targetFolder = allFolders.find((f) => f.id === targetFolderId) || currentFolder;

  const currentDrive = currentFolder?.root_path ? currentFolder.root_path.slice(0, 2).toUpperCase() : "";
  const targetDrive = targetFolder?.root_path ? targetFolder.root_path.slice(0, 2).toUpperCase() : "";
  const isCrossDrive = Boolean(currentDrive && targetDrive && currentDrive !== targetDrive);
  const isCrossFolder = targetFolderId !== managedFolderId;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setIsSubmitting(true);
      setError(null);
      await onSubmit(
        items.map((i) => i.relative_path),
        selectedDest,
        targetFolderId,
        conflictResolution
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
      <div className="w-full max-w-lg rounded-xl border border-border bg-card p-6 shadow-xl space-y-4">
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
          {/* Target Managed Folder Picker */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-foreground flex items-center justify-between">
              <span>Target Managed Folder / Drive</span>
              {mode === "move" && (
                isCrossDrive ? (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-purple-500/10 text-purple-600 dark:text-purple-400 font-medium border border-purple-500/20">
                    Cross-Drive Staged
                  </span>
                ) : isCrossFolder ? (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-blue-500/10 text-blue-600 dark:text-blue-400 font-medium border border-blue-500/20">
                    Cross-Folder
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[10px] bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 font-medium border border-emerald-500/20">
                    Same-Folder
                  </span>
                )
              )}
            </label>
            <select
              value={targetFolderId}
              onChange={(e) => setTargetFolderId(e.target.value)}
              className="w-full px-3 py-2 text-xs rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
            >
              {allFolders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.root_type === "drive" ? "💾 " : "📁 "}
                  {f.name} ({f.root_path})
                </option>
              ))}
            </select>
          </div>

          {/* Destination Directory Inside Folder */}
          <div className="space-y-2">
            <label className="text-xs font-medium text-foreground">
              Select Subdirectory
            </label>
            {isLoading ? (
              <div className="p-4 text-center text-xs text-muted-foreground">
                Loading directories...
              </div>
            ) : (
              <div className="max-h-40 overflow-y-auto rounded-md border border-border bg-background divide-y divide-border/60">
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
                      {targetFolder?.root_type === "drive" && !folder.relative_path ? (
                        <HardDrive size={16} className={isSelected ? "text-primary" : "text-muted-foreground"} />
                      ) : (
                        <Folder
                          size={16}
                          className={
                            isSelected ? "text-primary" : "text-amber-500 fill-amber-500/20"
                          }
                        />
                      )}
                      <span className="flex-1 truncate">{folder.name}</span>
                      {isSelected && <ChevronRight size={14} />}
                    </button>
                  );
                })}
              </div>
            )}
            <p className="text-[11px] text-muted-foreground flex items-center justify-between">
              <span>Path: {targetFolder?.name}{selectedDest ? ` / ${selectedDest}` : " / (Root)"}</span>
              {isCrossDrive && (
                <span className="text-[10px] text-purple-600 dark:text-purple-400 flex items-center gap-1">
                  <ShieldCheck size={12} /> SHA-256 verified copy & quarantine
                </span>
              )}
            </p>
          </div>

          {/* Conflict Resolution Strategy */}
          {mode === "move" && (
            <div className="space-y-1.5 pt-1">
              <label className="text-xs font-medium text-foreground">
                If Destination File Already Exists:
              </label>
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => setConflictResolution("rename")}
                  className={`px-2.5 py-1.5 rounded-md text-xs border text-left transition-colors ${
                    conflictResolution === "rename"
                      ? "border-primary bg-primary/10 text-primary font-medium"
                      : "border-border bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  <div className="font-semibold text-[11px]">Auto-Rename</div>
                  <div className="text-[10px] opacity-80">file (1).ext</div>
                </button>
                <button
                  type="button"
                  onClick={() => setConflictResolution("fail")}
                  className={`px-2.5 py-1.5 rounded-md text-xs border text-left transition-colors ${
                    conflictResolution === "fail"
                      ? "border-rose-500 bg-rose-500/10 text-rose-600 dark:text-rose-400 font-medium"
                      : "border-border bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  <div className="font-semibold text-[11px]">Fail & Abort</div>
                  <div className="text-[10px] opacity-80">Stop on conflict</div>
                </button>
                <button
                  type="button"
                  onClick={() => setConflictResolution("skip")}
                  className={`px-2.5 py-1.5 rounded-md text-xs border text-left transition-colors ${
                    conflictResolution === "skip"
                      ? "border-amber-500 bg-amber-500/10 text-amber-600 dark:text-amber-400 font-medium"
                      : "border-border bg-background text-muted-foreground hover:bg-muted"
                  }`}
                >
                  <div className="font-semibold text-[11px]">Skip Safely</div>
                  <div className="text-[10px] opacity-80">Leave unchanged</div>
                </button>
              </div>
            </div>
          )}

          {error && (
            <div className="p-2.5 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
              <AlertCircle size={15} className="shrink-0" />
              <span>{error}</span>
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
