import React, { useState } from "react";
import {
  X,
  Sparkles,
  RefreshCw,
  Layers,
  Database,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";
import type { DashboardManagedFolderItemData, DashboardJobItemData } from "@/types";
import { ApiService } from "@/services/api";

interface AnalyzeFolderModalProps {
  isOpen: boolean;
  folders: DashboardManagedFolderItemData[];
  onClose: () => void;
  onAnalysisTriggered: (job: DashboardJobItemData) => void;
}

export const AnalyzeFolderModal: React.FC<AnalyzeFolderModalProps> = ({
  isOpen,
  folders,
  onClose,
  onAnalysisTriggered,
}) => {
  const [selectedFolderId, setSelectedFolderId] = useState<string>("all");
  const [selectedMode, setSelectedMode] = useState<"metadata" | "deep">("metadata");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleStartAnalysis = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const folderId = selectedFolderId === "all" ? null : selectedFolderId;
      const job = await ApiService.triggerDashboardAnalyze({
        folder_id: folderId,
        mode: selectedMode,
      });
      onAnalysisTriggered(job);
      onClose();
    } catch (err: any) {
      setError(err.message || "Gagal memulai analisis");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in-50">
      <div className="w-full max-w-md rounded-xl border border-border bg-card shadow-2xl overflow-hidden animate-in zoom-in-95">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border bg-muted/30">
          <div className="flex items-center gap-2">
            <div className="p-1.5 rounded-lg bg-primary/10 text-primary">
              <Sparkles size={18} />
            </div>
            <div>
              <h3 className="font-semibold text-sm text-foreground">
                Mulai Analisis Folder
              </h3>
              <p className="text-xs text-muted-foreground">
                Pilih cakupan dan kedalaman pemindaian
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Modal Content */}
        <div className="p-5 space-y-4 text-xs">
          {error && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-2">
              <AlertTriangle size={15} className="flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {/* Scope Selection */}
          <div>
            <label className="font-semibold text-foreground block mb-1.5">
              Pilih Target Folder
            </label>
            <div className="space-y-2">
              <label
                className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedFolderId === "all"
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border hover:bg-muted/40"
                }`}
              >
                <input
                  type="radio"
                  name="scope"
                  value="all"
                  checked={selectedFolderId === "all"}
                  onChange={() => setSelectedFolderId("all")}
                  className="sr-only"
                />
                <Layers size={16} className={selectedFolderId === "all" ? "text-primary" : "text-muted-foreground"} />
                <div className="flex-1">
                  <span className="font-medium text-foreground block">Semua Managed Folders</span>
                  <span className="text-[11px] text-muted-foreground">
                    Memproses seluruh {folders.length} folder yang terdaftar dan aktif
                  </span>
                </div>
                {selectedFolderId === "all" && <CheckCircle2 size={15} className="text-primary" />}
              </label>

              {folders.length > 0 && (
                <div className="pt-1">
                  <label className="text-[11px] font-medium text-muted-foreground block mb-1">
                    Atau pilih folder spesifik:
                  </label>
                  <select
                    value={selectedFolderId === "all" ? "" : selectedFolderId}
                    onChange={(e) => {
                      if (e.target.value) {
                        setSelectedFolderId(e.target.value);
                      }
                    }}
                    className="w-full px-3 py-2 rounded-lg border border-border bg-background text-foreground text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="" disabled>-- Pilih salah satu folder --</option>
                    {folders.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name} ({f.root_path})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>

          {/* Mode Selection */}
          <div>
            <label className="font-semibold text-foreground block mb-1.5">
              Kedalaman Analisis
            </label>
            <div className="grid grid-cols-2 gap-2">
              <label
                className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedMode === "metadata"
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border hover:bg-muted/40"
                }`}
              >
                <input
                  type="radio"
                  name="mode"
                  value="metadata"
                  checked={selectedMode === "metadata"}
                  onChange={() => setSelectedMode("metadata")}
                  className="sr-only"
                />
                <div className="flex items-center justify-between mb-1">
                  <Database size={15} className={selectedMode === "metadata" ? "text-primary" : "text-muted-foreground"} />
                  {selectedMode === "metadata" && <CheckCircle2 size={13} className="text-primary" />}
                </div>
                <span className="font-semibold text-foreground">Scan Metadata</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">
                  Cepat. Tidak menghitung hash konten file.
                </span>
              </label>

              <label
                className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-all ${
                  selectedMode === "deep"
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border hover:bg-muted/40"
                }`}
              >
                <input
                  type="radio"
                  name="mode"
                  value="deep"
                  checked={selectedMode === "deep"}
                  onChange={() => setSelectedMode("deep")}
                  className="sr-only"
                />
                <div className="flex items-center justify-between mb-1">
                  <Sparkles size={15} className={selectedMode === "deep" ? "text-primary" : "text-muted-foreground"} />
                  {selectedMode === "deep" && <CheckCircle2 size={13} className="text-primary" />}
                </div>
                <span className="font-semibold text-foreground">Analisis Mendalam</span>
                <span className="text-[10px] text-muted-foreground mt-0.5">
                  Hitung hash, deteksi file duplikat & empty folders.
                </span>
              </label>
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border bg-muted/20">
          <button
            type="button"
            onClick={onClose}
            disabled={isLoading}
            className="px-3.5 py-1.5 text-xs font-medium rounded-lg border border-border hover:bg-muted text-muted-foreground transition-colors"
          >
            Batal
          </button>
          <button
            type="button"
            onClick={handleStartAnalysis}
            disabled={isLoading || (selectedFolderId !== "all" && !selectedFolderId)}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm disabled:opacity-50"
          >
            {isLoading ? (
              <>
                <RefreshCw size={13} className="animate-spin" />
                <span>Memproses...</span>
              </>
            ) : (
              <>
                <Sparkles size={13} />
                <span>Jalankan Analisis</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
