import React, { useState, useEffect } from "react";
import {
  Folder,
  Copy,
  Pencil,
  Trash2,
  Eye,
  Check,
  ShieldCheck,
  RefreshCw,
  X,
  Sparkles,
} from "lucide-react";
import { FileIcon } from "./FileIcon";
import { ApiService } from "@/services/api";
import type { FileItemMetadata, FolderSummaryResponse, ManagedFolder } from "@/types";

interface FileDetailsPanelProps {
  item: FileItemMetadata | null;
  onClose: () => void;
  onPreview: (item: FileItemMetadata) => void;
  onRename: (item: FileItemMetadata) => void;
  onDelete: (item: FileItemMetadata) => void;
  managedFolderRoot: string;
  managedFolderId: string;
  managedFolder?: ManagedFolder | null;
  onUnregisterFolder?: () => void;
  onAskAI?: (item: FileItemMetadata) => void;
}

export const FileDetailsPanel: React.FC<FileDetailsPanelProps> = ({
  item,
  onClose,
  onPreview,
  onRename,
  onDelete,
  managedFolderRoot,
  managedFolderId,
  managedFolder,
  onUnregisterFolder,
  onAskAI,
}) => {
  const [copied, setCopied] = useState(false);
  const [folderSummary, setFolderSummary] = useState<FolderSummaryResponse | null>(null);
  const [isScanningFolder, setIsScanningFolder] = useState(false);

  useEffect(() => {
    setFolderSummary(null);
    if (item && item.item_type === "directory") {
      fetchFolderSummary();
    }
  }, [item?.relative_path]);

  const fetchFolderSummary = async () => {
    if (!item) return;
    try {
      setIsScanningFolder(true);
      const summary = await ApiService.getFolderSummary(
        managedFolderId,
        item.relative_path
      );
      setFolderSummary(summary);
    } catch {
      // Ignore background summary scan error
    } finally {
      setIsScanningFolder(false);
    }
  };

  if (!item) {
    if (managedFolder) {
      return (
        <div className="w-80 border-l border-border bg-card/60 flex flex-col h-full select-none">
          <div className="flex items-center justify-between border-b border-border p-4 bg-muted/30">
            <div className="flex items-center gap-2">
              <Folder size={18} className="text-amber-500 fill-amber-500/20" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Managed Folder
              </h3>
            </div>
            <button
              onClick={onClose}
              className="p-1 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-foreground truncate">{managedFolder.name}</h4>
              <p className="font-mono text-[11px] text-muted-foreground break-all bg-muted/40 p-2 rounded border border-border/50">
                {managedFolder.root_path}
              </p>
            </div>

            <div className="p-3 rounded-lg border border-border bg-muted/20 space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Status</span>
                <span className="font-medium text-emerald-600">Aktif & Terdaftar</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Keamanan</span>
                <span className="font-medium text-primary">Terenkapsulasi</span>
              </div>
            </div>

            {onUnregisterFolder && (
              <div className="pt-4 border-t border-border">
                <button
                  type="button"
                  onClick={onUnregisterFolder}
                  className="w-full flex items-center justify-center gap-2 px-3 py-2 text-xs font-medium rounded-md border border-destructive/30 bg-destructive/5 hover:bg-destructive text-destructive hover:text-destructive-foreground transition-colors shadow-xs"
                >
                  <Trash2 size={14} />
                  <span>Hapus dari FileNest</span>
                </button>
                <p className="text-[10px] text-muted-foreground text-center mt-1.5">
                  Berkas fisik di hard disk tidak akan dihapus.
                </p>
              </div>
            )}
          </div>
        </div>
      );
    }

    return (
      <div className="w-80 border-l border-border bg-card/60 p-6 flex flex-col items-center justify-center text-center text-muted-foreground select-none">
        <Folder size={40} className="stroke-1 text-muted-foreground/40 mb-3" />
        <h4 className="text-sm font-medium text-foreground">No item selected</h4>
        <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">
          Select a file or folder from the browser to inspect its metadata and actions.
        </p>
      </div>
    );
  }

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB (${bytes.toLocaleString()} bytes)`;
    if (bytes < 1024 * 1024 * 1024)
      return `${(bytes / (1024 * 1024)).toFixed(1)} MB (${bytes.toLocaleString()} bytes)`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB (${bytes.toLocaleString()} bytes)`;
  };

  const fullPath = `${managedFolderRoot}\\${item.relative_path.replace(/\//g, "\\")}`;

  const handleCopyPath = () => {
    navigator.clipboard.writeText(fullPath);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const isDir = item.item_type === "directory";

  return (
    <div className="w-80 border-l border-border bg-card flex flex-col h-full overflow-y-auto select-none">
      {/* Panel Header */}
      <div className="p-4 border-b border-border flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          {isDir ? "Folder Details" : "File Details"}
        </span>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-muted-foreground hover:bg-muted transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="p-5 space-y-6">
        {/* Item Hero */}
        <div className="flex items-start gap-3.5">
          <div className="p-3 rounded-xl bg-muted/60 border border-border/80 shrink-0">
            <FileIcon
              itemType={item.item_type}
              category={item.category}
              extension={item.extension}
              size={32}
            />
          </div>
          <div className="min-w-0 flex-1">
            <h3 className="font-semibold text-sm text-foreground truncate" title={item.name}>
              {item.name}
            </h3>
            <p className="text-xs text-muted-foreground capitalize mt-0.5">
              {isDir
                ? "Folder"
                : item.extension
                ? `${item.extension.toUpperCase()} File`
                : `${item.category} File`}
            </p>
          </div>
        </div>

        {/* Properties Section */}
        <div className="space-y-3 pt-2 border-t border-border/60">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Properties
          </h4>

          <div className="space-y-2.5 text-xs">
            <div>
              <span className="text-muted-foreground block text-[11px]">Location</span>
              <span
                className="font-mono text-[11px] text-foreground/80 break-all select-all block mt-0.5"
                title={fullPath}
              >
                {fullPath}
              </span>
            </div>

            <div>
              <span className="text-muted-foreground block text-[11px]">Size</span>
              <span className="font-medium text-foreground">
                {isDir
                  ? folderSummary
                    ? formatSize(folderSummary.total_size_bytes)
                    : isScanningFolder
                    ? "Calculating..."
                    : "—"
                  : formatSize(item.size_bytes)}
              </span>
            </div>

            {isDir && folderSummary && (
              <div>
                <span className="text-muted-foreground block text-[11px]">Contains</span>
                <span className="font-medium text-foreground">
                  {folderSummary.file_count} files, {folderSummary.directory_count} subfolders
                </span>
              </div>
            )}

            <div>
              <span className="text-muted-foreground block text-[11px]">Last Modified</span>
              <span className="font-medium text-foreground">
                {item.modified_at || "—"}
              </span>
            </div>

            <div>
              <span className="text-muted-foreground block text-[11px]">Scope Status</span>
              <span className="inline-flex items-center gap-1 font-medium text-emerald-600 text-xs">
                <ShieldCheck size={13} />
                <span>Protected & Verified</span>
              </span>
            </div>
          </div>
        </div>

        {/* Folder Capabilities if directory */}
        {isDir && (
          <div className="space-y-2.5 pt-2 border-t border-border/60">
            <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
              Folder Capabilities
            </h4>
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between items-center py-1">
                <span className="text-muted-foreground">Organization</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded font-semibold bg-emerald-500/10 text-emerald-600">
                  Enabled
                </span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-muted-foreground">Smart Rename</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded font-semibold bg-emerald-500/10 text-emerald-600">
                  Enabled
                </span>
              </div>
              <div className="flex justify-between items-center py-1">
                <span className="text-muted-foreground">Monitoring</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded font-semibold bg-emerald-500/10 text-emerald-600">
                  Enabled
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="space-y-2 pt-2 border-t border-border/60">
          <h4 className="text-xs font-bold uppercase tracking-wider text-muted-foreground">
            Quick Actions
          </h4>

          <div className="space-y-1.5">
            {onAskAI && item && (
              <button
                type="button"
                onClick={() => onAskAI(item)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-semibold rounded-md bg-primary/10 hover:bg-primary/20 text-primary transition-colors border border-primary/20 shadow-2xs"
              >
                <Sparkles size={15} />
                <span>Tanyakan ke AI Assistant</span>
              </button>
            )}

            {!isDir && (
              <button
                onClick={() => onPreview(item)}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md hover:bg-muted text-foreground transition-colors"
              >
                <Eye size={15} className="text-primary" />
                <span>Preview File</span>
              </button>
            )}

            <button
              onClick={handleCopyPath}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md hover:bg-muted text-foreground transition-colors"
            >
              {copied ? (
                <Check size={15} className="text-emerald-600" />
              ) : (
                <Copy size={15} className="text-muted-foreground" />
              )}
              <span>{copied ? "Path Copied!" : "Copy Full Path"}</span>
            </button>

            <button
              onClick={() => onRename(item)}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md hover:bg-muted text-foreground transition-colors"
            >
              <Pencil size={15} className="text-muted-foreground" />
              <span>Rename</span>
            </button>

            {isDir && (
              <button
                onClick={fetchFolderSummary}
                disabled={isScanningFolder}
                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md hover:bg-muted text-foreground transition-colors disabled:opacity-50"
              >
                <RefreshCw
                  size={15}
                  className={`text-muted-foreground ${isScanningFolder ? "animate-spin" : ""}`}
                />
                <span>Scan Folder Size</span>
              </button>
            )}

            <button
              onClick={() => onDelete(item)}
              className="w-full flex items-center gap-2.5 px-3 py-2 text-xs font-medium rounded-md hover:bg-destructive/10 text-destructive transition-colors"
            >
              <Trash2 size={15} />
              <span>Delete to Recycle Bin</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
