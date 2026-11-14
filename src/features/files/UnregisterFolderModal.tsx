import React, { useState } from "react";
import { Trash2, Folder, ShieldCheck, X, Loader2 } from "lucide-react";
import type { ManagedFolder } from "@/types";

interface UnregisterFolderModalProps {
  isOpen: boolean;
  onClose: () => void;
  folder: ManagedFolder | null;
  onConfirm: (folder: ManagedFolder, permanent: boolean) => Promise<void>;
}

export const UnregisterFolderModal: React.FC<UnregisterFolderModalProps> = ({
  isOpen,
  onClose,
  folder,
  onConfirm,
}) => {
  const [isDeleting, setIsDeleting] = useState(false);
  const [permanent, setPermanent] = useState(true);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !folder) return null;

  const handleConfirm = async () => {
    try {
      setIsDeleting(true);
      setError(null);
      await onConfirm(folder, permanent);
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Gagal menghapus folder");
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-md rounded-xl border border-border bg-card p-6 shadow-2xl space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border pb-3">
          <div className="flex items-center gap-2 text-destructive font-semibold text-sm">
            <Trash2 size={18} />
            <span>Hapus dari Managed Folders</span>
          </div>
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted transition-colors disabled:opacity-50"
          >
            <X size={16} />
          </button>
        </div>

        {/* Folder Info */}
        <div className="space-y-3">
          <div className="p-3 rounded-lg border border-border bg-muted/40 space-y-1.5">
            <div className="flex items-center gap-2">
              <Folder size={16} className="text-amber-500 fill-amber-500/20 shrink-0" />
              <span className="font-semibold text-foreground text-xs truncate">
                {folder.name}
              </span>
            </div>
            <p className="font-mono text-[11px] text-muted-foreground break-all bg-background/60 p-1.5 rounded border border-border/50">
              {folder.root_path}
            </p>
          </div>

          {/* Safety Notice */}
          <div className="flex items-start gap-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-800 dark:text-emerald-300">
            <ShieldCheck size={18} className="shrink-0 mt-0.5 text-emerald-600 dark:text-emerald-400" />
            <div className="space-y-0.5">
              <span className="font-semibold block">Berkas Fisik Aman</span>
              <p className="text-[11px] leading-relaxed text-emerald-700 dark:text-emerald-300/90">
                Tindakan ini hanya menghapus folder dari daftar pengelolaan FileNest. Seluruh berkas asli di hard drive Anda <strong>TIDAK</strong> akan dihapus atau dimodifikasi.
              </p>
            </div>
          </div>

          {/* Permanent Checkbox */}
          <label className="flex items-center gap-2 pt-1 text-xs text-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={permanent}
              onChange={(e) => setPermanent(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary cursor-pointer"
            />
            <span>Hapus permanen dari riwayat database FileNest</span>
          </label>
        </div>

        {error && (
          <div className="p-2.5 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2 pt-2 border-t border-border">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-4 py-2 text-xs font-medium rounded-md border border-border bg-muted/50 hover:bg-muted text-foreground transition-colors disabled:opacity-50"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isDeleting}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-medium rounded-md bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors shadow-xs disabled:opacity-50"
          >
            {isDeleting ? (
              <>
                <Loader2 size={13} className="animate-spin" />
                <span>Menghapus...</span>
              </>
            ) : (
              <>
                <Trash2 size={13} />
                <span>Hapus Folder</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};

