import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Sparkles,
  AlertTriangle,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ApiService } from "@/services/api";
import type { DashboardOverviewResponse, DashboardJobItemData, NavItem } from "@/types";
import { DashboardSummaryCards } from "./DashboardSummaryCards";
import { StorageUsageDonut } from "./StorageUsageDonut";
import { FolderDistributionList } from "./FolderDistributionList";
import { DashboardManagedFoldersTable } from "./DashboardManagedFoldersTable";
import { RecentActivitiesFeed } from "./RecentActivitiesFeed";
import { RecommendationsWidget } from "./RecommendationsWidget";
import { JobStatusMonitor } from "./JobStatusMonitor";
import { StorageHistoryChart } from "./StorageHistoryChart";
import { AnalyzeFolderModal } from "./AnalyzeFolderModal";

interface DashboardManagerProps {
  onNavigate: (tab: NavItem) => void;
}

export const DashboardManager: React.FC<DashboardManagerProps> = ({ onNavigate }) => {
  const [data, setData] = useState<DashboardOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);
  const [isAnalyzeModalOpen, setIsAnalyzeModalOpen] = useState(false);
  const [folderToRemove, setFolderToRemove] = useState<{ id: string; name: string } | null>(null);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setIsRefreshing(true);
    } else {
      setIsLoading(true);
    }
    setError(null);
    try {
      const res = await ApiService.getDashboardOverview();
      setData(res);
    } catch (err: any) {
      setError(err.message || "Gagal memuat ringkasan dashboard.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboardData();
  }, [fetchDashboardData]);

  // Native folder selection or dialog fallback
  const handleAddFolder = async () => {
    try {
      let selectedPath: string | null = null;
      try {
        const { open } = await import("@tauri-apps/plugin-dialog");
        const result = await open({
          directory: true,
          multiple: false,
          title: "Pilih Folder untuk Dikelola",
        });
        if (typeof result === "string") {
          selectedPath = result;
        }
      } catch {
        // Fallback prompt for browser / non-Tauri dev mode
        selectedPath = window.prompt("Masukkan path absolut folder di Windows:");
      }

      if (!selectedPath) return;

      const folderName = selectedPath.split(/[\\/]/).filter(Boolean).pop() || "Folder Baru";
      await ApiService.registerFolder({
        name: folderName,
        root_path: selectedPath,
      });

      setSuccessBanner(`Folder "${folderName}" berhasil didaftarkan.`);
      setTimeout(() => setSuccessBanner(null), 4000);
      fetchDashboardData(true);
    } catch (err: any) {
      setError(err.message || "Gagal mendaftarkan folder.");
    }
  };

  const handleToggleMonitoring = async (folderId: string, currentStatus: boolean) => {
    try {
      if (currentStatus) {
        await ApiService.stopWatcher(folderId);
        setSuccessBanner("Monitoring dinonaktifkan untuk folder ini.");
      } else {
        await ApiService.startWatcher(folderId);
        setSuccessBanner("Monitoring diaktifkan untuk folder ini.");
      }
      setTimeout(() => setSuccessBanner(null), 3000);
      fetchDashboardData(true);
    } catch (err: any) {
      setError(err.message || "Gagal memperbarui status monitoring.");
    }
  };

  const handleScanFolder = async (folderId: string) => {
    try {
      await ApiService.triggerDashboardAnalyze({
        folder_id: folderId,
        mode: "metadata",
      });
      setSuccessBanner("Pemindaian folder berhasil diselesaikan.");
      setTimeout(() => setSuccessBanner(null), 3000);
      fetchDashboardData(true);
    } catch (err: any) {
      setError(err.message || "Gagal memindai folder.");
    }
  };

  const handleOpenFolderInExplorer = (rootPath: string) => {
    try {
      window.open(`file:///${rootPath.replace(/\\/g, "/")}`);
    } catch {
      // Ignored
    }
  };

  const handleConfirmRemoveFolder = async () => {
    if (!folderToRemove) return;
    try {
      await ApiService.unregisterFolder(folderToRemove.id);
      setSuccessBanner(`Folder "${folderToRemove.name}" berhasil dihapus dari kelolaan.`);
      setFolderToRemove(null);
      setTimeout(() => setSuccessBanner(null), 3000);
      fetchDashboardData(true);
    } catch (err: any) {
      setError(err.message || "Gagal menghapus folder.");
    }
  };

  const handleAnalysisTriggered = (job: DashboardJobItemData) => {
    setSuccessBanner(`Pekerjaan "${job.job_name}" berhasil diproses.`);
    setTimeout(() => setSuccessBanner(null), 4000);
    fetchDashboardData(true);
  };

  return (
    <div className="space-y-6 pb-12 animate-in fade-in-50">
      {/* Page Header */}
      <PageHeader
        title="Overview"
        description="Ringkasan penyimpanan, aktivitas, dan status pengelolaan folder."
      >
        <div className="flex items-center gap-2">
          {/* Refresh Button */}
          <button
            type="button"
            onClick={() => fetchDashboardData(true)}
            disabled={isRefreshing || isLoading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50"
            title="Muat ulang ringkasan dari database tanpa memindai filesystem"
          >
            <RefreshCw size={14} className={isRefreshing ? "animate-spin" : ""} />
            <span>Segarkan</span>
          </button>

          {/* Analyze Folder Button */}
          <button
            type="button"
            onClick={() => setIsAnalyzeModalOpen(true)}
            className="inline-flex items-center gap-2 px-3.5 py-1.5 text-xs font-medium rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
          >
            <Sparkles size={14} />
            <span>Analisis Folder</span>
          </button>
        </div>
      </PageHeader>

      {/* Success Notification Banner */}
      {successBanner && (
        <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 text-xs flex items-center justify-between animate-in fade-in-50">
          <div className="flex items-center gap-2">
            <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0" />
            <span>{successBanner}</span>
          </div>
          <button
            type="button"
            onClick={() => setSuccessBanner(null)}
            className="text-emerald-600 hover:text-emerald-800 dark:text-emerald-400 text-xs font-semibold"
          >
            Tutup
          </button>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <AlertTriangle size={16} className="flex-shrink-0" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            onClick={() => fetchDashboardData(true)}
            className="px-2.5 py-1 rounded bg-destructive/15 text-destructive font-semibold hover:bg-destructive/25 transition-colors"
          >
            Coba Lagi
          </button>
        </div>
      )}

      {/* Stale Warning Banner */}
      {data?.is_stale && !isLoading && (
        <div className="p-3.5 rounded-xl bg-amber-500/10 border border-amber-500/25 text-amber-700 dark:text-amber-400 text-xs flex items-center justify-between animate-in fade-in-50">
          <div className="flex items-center gap-2">
            <AlertTriangle size={15} className="text-amber-500 shrink-0" />
            <span>Folder terdaftar belum pernah dipindai. Jalankan Analisis Folder untuk mengindeks file dan menghitung ukuran riil.</span>
          </div>
          <button
            type="button"
            onClick={() => setIsAnalyzeModalOpen(true)}
            className="px-2.5 py-1 rounded bg-amber-500/20 text-amber-800 dark:text-amber-300 font-semibold hover:bg-amber-500/30 transition-colors shrink-0"
          >
            Pindai Sekarang
          </button>
        </div>
      )}

      {isLoading && !data ? (
        <div className="py-24 flex flex-col items-center justify-center text-muted-foreground">
          <Loader2 size={32} className="animate-spin text-primary mb-3" />
          <p className="text-sm font-medium text-foreground">Memuat data dashboard...</p>
          <p className="text-xs text-muted-foreground mt-1">Mengambil statistik dari basis data lokal</p>
        </div>
      ) : data ? (
        <>
          {/* 1. Summary Cards */}
          <DashboardSummaryCards
            cards={data.summary_cards}
            onNavigate={onNavigate}
          />

          {/* 2. Middle Row: Storage Donut, Folder Distribution & Managed Folders (3-Column Grid) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <StorageUsageDonut
              categories={data.storage_categories}
              totalBytes={data.summary_cards.total_size_bytes}
              onSelectCategory={() => onNavigate("storage")}
            />
            <FolderDistributionList
              folders={data.folder_distribution}
              totalFoldersCount={data.summary_cards.managed_folders_count}
              onOpenFolder={() => onNavigate("files")}
              onViewAll={() => onNavigate("managed-folders")}
            />
            <DashboardManagedFoldersTable
              folders={data.managed_folders}
              onAddFolder={handleAddFolder}
              onOpenFolderInFiles={() => onNavigate("files")}
              onOpenFolderInExplorer={handleOpenFolderInExplorer}
              onScanFolder={handleScanFolder}
              onToggleMonitoring={handleToggleMonitoring}
              onRemoveFolder={(id, name) => setFolderToRemove({ id, name })}
              onNavigate={onNavigate}
            />
          </div>

          {/* 3. Lower Row: Recent Activities, Recommendations & Job Status (3-Column Grid) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <RecentActivitiesFeed
              activities={data.recent_activities}
              onViewAll={() => onNavigate("history")}
            />
            <RecommendationsWidget
              recommendations={data.recommendations}
              onNavigate={onNavigate}
            />
            <JobStatusMonitor
              jobs={data.jobs}
              onRefreshJobs={() => fetchDashboardData(true)}
            />
          </div>

          {/* 4. Bottom Row: Storage History Trend (2 Cols) + 7-Day Changes Summary Metrics (1 Col) */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2">
              <StorageHistoryChart
                historyPoints={data.storage_history}
              />
            </div>
            <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between">
              <div className="pb-3 border-b border-border/50">
                <h3 className="font-semibold text-sm text-foreground">
                  Perubahan (7 Hari Terakhir)
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Ringkasan aktivitas mutasi filesystem
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 my-auto py-2">
                <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                  <span className="text-xs text-emerald-700 dark:text-emerald-400 font-bold block">
                    +248
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    File Ditambahkan
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                  <span className="text-xs text-amber-700 dark:text-amber-400 font-bold block">
                    132
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    File Diubah Nama
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
                  <span className="text-xs text-blue-700 dark:text-blue-400 font-bold block">
                    24
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    File Dipindahkan
                  </span>
                </div>
                <div className="p-3 rounded-lg bg-rose-500/10 border border-rose-500/20">
                  <span className="text-xs text-rose-700 dark:text-rose-400 font-bold block">
                    0
                  </span>
                  <span className="text-[11px] text-muted-foreground">
                    File Dihapus
                  </span>
                </div>
              </div>

              <div className="text-[11px] text-muted-foreground pt-2 border-t border-border/50 flex justify-between items-center">
                <span>Seluruh mutasi tercatat audit</span>
                <button
                  type="button"
                  onClick={() => onNavigate("history")}
                  className="text-primary hover:underline font-semibold"
                >
                  Lihat Riwayat &rarr;
                </button>
              </div>
            </div>
          </div>
        </>
      ) : null}

      {/* Analyze Modal */}
      <AnalyzeFolderModal
        isOpen={isAnalyzeModalOpen}
        folders={data?.managed_folders || []}
        onClose={() => setIsAnalyzeModalOpen(false)}
        onAnalysisTriggered={handleAnalysisTriggered}
      />

      {/* Remove Confirmation Modal */}
      {folderToRemove && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4 animate-in fade-in-50">
          <div className="w-full max-w-sm rounded-xl border border-border bg-card p-5 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-destructive/10 text-destructive">
                <AlertTriangle size={20} />
              </div>
              <div>
                <h4 className="font-semibold text-sm text-foreground">Hapus Folder Kelolaan?</h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Folder &quot;{folderToRemove.name}&quot; akan dihapus dari aplikasi.
                </p>
              </div>
            </div>
            <p className="text-xs text-muted-foreground bg-muted/50 p-2.5 rounded-lg border border-border/50">
              File dan folder fisik Anda di disk Windows tidak akan dihapus. Hanya data registrasi dan riwayat indeks lokal yang dilepaskan.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2">
              <button
                type="button"
                onClick={() => setFolderToRemove(null)}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg border border-border hover:bg-muted text-muted-foreground transition-colors"
              >
                Batal
              </button>
              <button
                type="button"
                onClick={handleConfirmRemoveFolder}
                className="px-3.5 py-1.5 text-xs font-medium rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors shadow-sm"
              >
                Hapus Registrasi
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
