import React, { useState, useEffect } from "react";
import { Sparkles, X, Check, Loader2, AlertCircle, FileText, ArrowRight } from "lucide-react";
import { ApiService } from "@/services/api";
import type { FileItemMetadata } from "@/types";

interface OCRRenameModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (sourcePath: string, newName: string) => Promise<void>;
  item: FileItemMetadata | null;
  folderId: string;
}

export const OCRRenameModal: React.FC<OCRRenameModalProps> = ({
  isOpen,
  onClose,
  onSubmit,
  item,
  folderId,
}) => {
  const [loading, setLoading] = useState<boolean>(true);
  const [extractedText, setExtractedText] = useState<string | null>(null);
  const [proposedName, setProposedName] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState<boolean>(false);

  useEffect(() => {
    if (!isOpen || !item || !folderId) {
      setLoading(false);
      setExtractedText(null);
      setProposedName("");
      setError(null);
      return;
    }

    let isMounted = true;
    setLoading(true);
    setError(null);
    setExtractedText(null);
    setProposedName("");

    ApiService.quickSuggestOCRRename(folderId, item.relative_path)
      .then((res) => {
        if (!isMounted) return;
        if (res.success) {
          setProposedName(res.proposed_name);
          setExtractedText(res.extracted_text || null);
        } else {
          setError(res.error_message || "Gagal menghasilkan saran nama OCR.");
          setProposedName(item.name);
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setError(err.message || "Gagal menghubungkan ke layanan OCR + AI.");
        setProposedName(item.name);
      })
      .finally(() => {
        if (isMounted) setLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [isOpen, item, folderId]);

  if (!isOpen || !item) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = proposedName.trim();
    if (!trimmed) {
      setError("Nama berkas baru tidak boleh kosong.");
      return;
    }
    if (trimmed === item.name) {
      onClose();
      return;
    }
    if (/[\\/:*?"<>|]/.test(trimmed)) {
      setError("Nama berkas tidak boleh mengandung karakter \\ / : * ? \" < > |");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      await onSubmit(item.relative_path, trimmed);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Gagal mengganti nama berkas.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div
        className="w-full max-w-md rounded-xl bg-card text-card-foreground border border-border shadow-2xl overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-md bg-amber-500/10 text-amber-600 dark:text-amber-400">
              <Sparkles size={18} />
            </div>
            <div>
              <h2 className="text-sm font-semibold">Rename Otomatis (OCR + AI)</h2>
              <p className="text-[11px] text-muted-foreground">
                Membaca teks dari dokumen/gambar untuk membuat nama baru yang deskriptif
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4">
          {error && (
            <div className="flex items-start gap-2 p-3 text-xs text-destructive bg-destructive/10 border border-destructive/20 rounded-lg">
              <AlertCircle size={15} className="shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="py-8 flex flex-col items-center justify-center gap-3 text-center">
              <Loader2 size={28} className="animate-spin text-primary" />
              <div>
                <p className="text-xs font-medium text-foreground">
                  Sedang membaca berkas dengan OCR...
                </p>
                <p className="text-[11px] text-muted-foreground mt-0.5">
                  Mengekstrak teks & merumuskan nama baru dengan AI
                </p>
              </div>
            </div>
          ) : (
            <>
              {/* Original Name */}
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-muted-foreground">
                  Nama Berkas Asli
                </label>
                <div className="px-3 py-2 text-xs bg-muted/50 rounded-lg border border-border/60 text-muted-foreground font-mono truncate">
                  {item.name}
                </div>
              </div>

              {/* Extracted OCR snippet if available */}
              {extractedText && (
                <div className="space-y-1">
                  <div className="flex items-center gap-1.5 text-[11px] font-medium text-amber-600 dark:text-amber-400">
                    <FileText size={13} />
                    <span>Teks Terdeteksi via OCR:</span>
                  </div>
                  <div className="p-2.5 text-xs bg-amber-500/5 dark:bg-amber-500/10 border border-amber-500/20 rounded-lg max-h-24 overflow-y-auto text-foreground/80 font-mono text-[11px] leading-relaxed select-text">
                    "{extractedText}"
                  </div>
                </div>
              )}

              {/* Proposed Name Input */}
              <div className="space-y-1.5 pt-1">
                <div className="flex items-center justify-between">
                  <label
                    htmlFor="proposed-ocr-name"
                    className="text-xs font-semibold flex items-center gap-1.5 text-foreground"
                  >
                    <ArrowRight size={13} className="text-primary" />
                    Saran Nama Baru (AI)
                  </label>
                  <span className="text-[10px] text-muted-foreground">Dapat disunting</span>
                </div>
                <input
                  id="proposed-ocr-name"
                  type="text"
                  value={proposedName}
                  onChange={(e) => setProposedName(e.target.value)}
                  placeholder="Nama berkas baru..."
                  className="w-full px-3 py-2 text-xs bg-background border border-primary/50 focus:border-primary rounded-lg focus:outline-hidden focus:ring-1 focus:ring-primary font-medium text-foreground transition-all shadow-xs"
                  autoFocus
                />
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border/80">
                <button
                  type="button"
                  onClick={onClose}
                  disabled={submitting}
                  className="px-3 py-1.5 text-xs rounded-lg border border-border hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
                >
                  Batal
                </button>
                <button
                  type="submit"
                  disabled={submitting || !proposedName.trim() || proposedName.trim() === item.name}
                  className="flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {submitting ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Check size={13} />
                  )}
                  <span>Terapkan Rename</span>
                </button>
              </div>
            </>
          )}
        </form>
      </div>
    </div>
  );
};
