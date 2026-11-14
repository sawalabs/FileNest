import React, { useEffect, useState } from "react";
import {
  ShieldCheck,
  Sparkles,
  Plus,
  Lock,
  Unlock,
  Trash2,
  Folder,
  RefreshCw,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { cn } from "@/lib/utils";
import type { ProtectedSubfolderItem } from "@/types";

interface ProtectedFoldersCardProps {
  folderId: string;
}

const CATEGORY_LABELS: Record<string, string> = {
  tool_bundle: "Tool / DLL Bundle",
  code_project: "Code Project",
  sdk_runtime: "SDK / Runtime",
  custom: "Manual Flag",
};

const SOURCE_LABELS: Record<string, string> = {
  ai: "AI Detect",
  smart_detect: "Smart Detect",
  manual: "Manual",
};

export const ProtectedFoldersCard: React.FC<ProtectedFoldersCardProps> = ({
  folderId,
}) => {
  const [items, setItems] = useState<ProtectedSubfolderItem[]>([]);
  const [availableSubfolders, setAvailableSubfolders] = useState<string[]>([]);
  const [manualPath, setManualPath] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isDetecting, setIsDetecting] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadProtectedFolders = async (targetFolderId: string) => {
    if (!targetFolderId) return;
    setIsLoading(true);
    setError(null);
    try {
      const res = await ApiService.getProtectedFolders(targetFolderId);
      setItems(res.protected_folders);
      setAvailableSubfolders(res.available_subfolders);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal memuat daftar folder terlindungi.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    setFeedback(null);
    setManualPath("");
    if (folderId) {
      loadProtectedFolders(folderId);
    } else {
      setItems([]);
      setAvailableSubfolders([]);
    }
  }, [folderId]);

  const handleSmartDetect = async () => {
    if (!folderId) return;
    setIsDetecting(true);
    setError(null);
    setFeedback(null);
    try {
      const res = await ApiService.detectProtectedFolders(folderId, true);
      setItems(res.protected_folders);
      setAvailableSubfolders(res.available_subfolders);
      const modeLabel = res.detection_mode === "hybrid_ai" ? "Smart + AI" : "Smart Scan";
      setFeedback(
        res.newly_flagged_count > 0
          ? `${modeLabel}: ${res.newly_flagged_count} folder project/tool baru otomatis ditandai terlindungi.`
          : `${modeLabel}: semua folder aman (${res.total_protected_count} folder aktif terlindungi).`
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal menjalankan deteksi otomatis.");
    } finally {
      setIsDetecting(false);
    }
  };

  const handleAddManualFlag = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleaned = manualPath.trim();
    if (!folderId || !cleaned) return;
    setIsAdding(true);
    setError(null);
    setFeedback(null);
    try {
      await ApiService.addProtectedFolder(folderId, cleaned);
      setManualPath("");
      await loadProtectedFolders(folderId);
      setFeedback(`Folder "${cleaned}" ditandai agar isinya tidak ikut dipindah saat Organize.`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal menandai folder.");
    } finally {
      setIsAdding(false);
    }
  };

  const handleToggleItem = async (item: ProtectedSubfolderItem) => {
    if (!folderId) return;
    setError(null);
    try {
      const updated = await ApiService.toggleProtectedFolder(
        folderId,
        item.id,
        !item.is_protected
      );
      setItems((prev) => prev.map((it) => (it.id === updated.id ? updated : it)));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal mengubah status proteksi folder.");
    }
  };

  const handleRemoveItem = async (item: ProtectedSubfolderItem) => {
    if (!folderId) return;
    setError(null);
    try {
      await ApiService.deleteProtectedFolder(folderId, item.id);
      await loadProtectedFolders(folderId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal menghapus flag folder.");
    }
  };

  const activeCount = items.filter((it) => it.is_protected).length;

  return (
    <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
      {/* Header + Smart/AI Detect Action */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2.5 border-b border-border/60">
        <div className="flex items-start gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0 mt-0.5">
            <ShieldCheck size={16} />
          </div>
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-xs font-semibold text-foreground">
                Protected Project & Tool Folders (Do Not Organize)
              </h3>
              <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold bg-primary/10 text-primary">
                {activeCount} active
              </span>
            </div>
            <p className="text-[11px] text-muted-foreground">
              Folder bertanda di sini (misal platform-tools, bundle .dll/.exe, atau repo project) tidak akan dipecah isinya saat Organize.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={handleSmartDetect}
          disabled={!folderId || isDetecting}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold bg-primary/10 text-primary hover:bg-primary/20 border border-primary/20 transition-colors disabled:opacity-50 shrink-0"
        >
          {isDetecting ? (
            <RefreshCw size={13} className="animate-spin" />
          ) : (
            <Sparkles size={13} />
          )}
          <span>{isDetecting ? "Scanning..." : "Smart / AI Detect"}</span>
        </button>
      </div>

      {/* Manual Flag Input Row */}
      <form onSubmit={handleAddManualFlag} className="flex items-center gap-2">
        <div className="relative flex-1 min-w-0">
          <input
            type="text"
            list={`protected-subfolder-options-${folderId}`}
            value={manualPath}
            onChange={(e) => setManualPath(e.target.value)}
            disabled={!folderId || isAdding}
            placeholder={
              availableSubfolders.length > 0
                ? "Pilih atau ketik subfolder (contoh: platform-tools)..."
                : "Ketik nama subfolder yang ingin dikecualikan..."
            }
            className="w-full px-3 py-1.5 rounded-md border border-border bg-muted/40 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <datalist id={`protected-subfolder-options-${folderId}`}>
            {availableSubfolders.map((sub) => (
              <option key={sub} value={sub} />
            ))}
          </datalist>
        </div>
        <button
          type="submit"
          disabled={!folderId || !manualPath.trim() || isAdding}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50 shrink-0"
        >
          <Plus size={13} />
          <span>{isAdding ? "Flagging..." : "Flag Folder"}</span>
        </button>
      </form>

      {/* Feedback / Errors */}
      {feedback && (
        <p className="text-[11px] text-emerald-700 dark:text-emerald-300 bg-emerald-500/10 border border-emerald-500/20 rounded-md px-2.5 py-1.5">
          {feedback}
        </p>
      )}
      {error && (
        <p className="text-[11px] text-destructive bg-destructive/10 border border-destructive/20 rounded-md px-2.5 py-1.5">
          {error}
        </p>
      )}

      {/* Protected Subfolders List */}
      {isLoading ? (
        <p className="text-[11px] text-muted-foreground py-2">Memuat daftar proteksi...</p>
      ) : items.length === 0 ? (
        <p className="text-[11px] text-muted-foreground py-1">
          Belum ada subfolder yang di-flag manual. Folder berisi <code className="text-foreground">.dll</code>, bundle aplikasi, atau project code juga akan otomatis dideteksi saat membuat Organize Plan.
        </p>
      ) : (
        <div className="space-y-1.5 max-h-48 overflow-y-auto pr-0.5">
          {items.map((item) => (
            <div
              key={item.id}
              className={cn(
                "flex items-center justify-between gap-2 px-2.5 py-2 rounded-lg border text-xs transition-colors",
                item.is_protected
                  ? "bg-muted/30 border-border/80"
                  : "bg-muted/10 border-border/40 opacity-60"
              )}
            >
              <div className="flex items-start gap-2 min-w-0">
                <Folder size={14} className="text-amber-500 shrink-0 mt-0.5" />
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-mono font-semibold text-foreground truncate">
                      {item.relative_path}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-secondary text-secondary-foreground border border-border/60">
                      {CATEGORY_LABELS[item.category] || item.category}
                    </span>
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-primary/10 text-primary">
                      {SOURCE_LABELS[item.source] || item.source}
                    </span>
                  </div>
                  <p className="text-[11px] text-muted-foreground truncate" title={item.reason}>
                    {item.reason}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  onClick={() => handleToggleItem(item)}
                  title={item.is_protected ? "Protected (klik untuk pause)" : "Paused (klik untuk proteksi)"}
                  className={cn(
                    "inline-flex items-center gap-1 px-2 py-1 rounded text-[11px] font-medium border transition-colors",
                    item.is_protected
                      ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20"
                      : "bg-muted text-muted-foreground border-border hover:text-foreground"
                  )}
                >
                  {item.is_protected ? <Lock size={11} /> : <Unlock size={11} />}
                  <span>{item.is_protected ? "Protected" : "Paused"}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleRemoveItem(item)}
                  title="Hapus flag"
                  className="p-1.5 rounded text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
