import React, { useState, useEffect, useCallback } from "react";
import {
  RefreshCw,
  Play,
  Clock,
  HardDrive,
  FileWarning,
  Copy,
  FolderX,
  FileCode,
  LayoutDashboard,
  AlertCircle,
  FolderTree,
  ChevronDown,
} from "lucide-react";
import { ApiService } from "@/services/api";
import { formatDate } from "@/lib/utils";
import type { ManagedFolder, StorageAnalysisResult } from "@/types";
import { StorageSummaryCards, type StorageTab } from "./StorageSummaryCards";
import { StorageOverviewTab } from "./StorageOverviewTab";
import { LargeFilesTab } from "./LargeFilesTab";
import { DuplicatesTab } from "./DuplicatesTab";
import { FileTypesTab } from "./FileTypesTab";
import { EmptyFoldersTab } from "./EmptyFoldersTab";

interface StorageAnalyzerProps {
  onNavigateToFiles?: (folderId: string, relativePath: string) => void;
  onNavigateToReviewChanges?: () => void;
}

export const StorageAnalyzer: React.FC<StorageAnalyzerProps> = ({
  onNavigateToFiles,
  onNavigateToReviewChanges,
}) => {
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>("all");
  const [analysisResult, setAnalysisResult] = useState<StorageAnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState<StorageTab>("overview");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");

  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isAnalyzeMenuOpen, setIsAnalyzeMenuOpen] = useState(false);

  // Load registered folders
  const loadFolders = useCallback(async () => {
    try {
      const list = await ApiService.listFolders();
      setFolders(list);
    } catch (err: unknown) {
      console.error("Failed to load folders:", err);
    }
  }, []);

  // Fetch cached analysis result from database
  const loadAnalysis = useCallback(
    async (folderId: string = selectedFolderId) => {
      setIsLoading(true);
      setErrorMessage(null);
      try {
        const idParam = folderId === "all" ? undefined : folderId;
        const result = await ApiService.getLatestStorageAnalysis(idParam);
        setAnalysisResult(result);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to load storage analysis";
        setErrorMessage(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [selectedFolderId]
  );

  // Initial load
  useEffect(() => {
    loadFolders();
    loadAnalysis("all");
  }, [loadFolders, loadAnalysis]);

  // When folder selection changes, reload cached analysis
  const handleFolderSelect = (folderId: string) => {
    setSelectedFolderId(folderId);
    loadAnalysis(folderId);
  };

  // Run new storage analysis
  const handleRunAnalysis = async (targetFolderId?: string) => {
    setIsAnalyzeMenuOpen(false);
    setIsAnalyzing(true);
    setErrorMessage(null);
    try {
      const folderIdParam = targetFolderId === "all" ? undefined : targetFolderId;
      const result = await ApiService.triggerStorageAnalysis({
        managed_folder_id: folderIdParam,
        large_file_threshold_bytes: 100 * 1024 * 1024, // 100 MB
        calculate_hashes: true,
      });
      setAnalysisResult(result);
      if (targetFolderId !== undefined) {
        setSelectedFolderId(targetFolderId);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Storage analysis execution failed";
      setErrorMessage(msg);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleSelectTabWithFilter = (tab: StorageTab, category?: string) => {
    setActiveTab(tab);
    if (category) {
      setCategoryFilter(category);
    }
  };

  const handleOpenFolderInFiles = (folderId: string, relativePath: string) => {
    if (onNavigateToFiles) {
      onNavigateToFiles(folderId, relativePath);
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-border">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2.5">
            <HardDrive size={22} className="text-primary" />
            <span>Storage Analyzer</span>
          </h1>
          <p className="text-xs text-muted-foreground mt-1">
            Analyze storage usage and discover opportunities to free up space across managed folders.
          </p>
        </div>

        {/* Controls: Folder Select, Last Analyzed, Refresh, Analyze Button */}
        <div className="flex flex-wrap items-center gap-2.5">
          {/* Managed Folder Selector */}
          <div className="flex items-center gap-1.5 bg-card border border-border rounded-lg px-2.5 py-1.5 text-xs shadow-xs">
            <FolderTree size={14} className="text-muted-foreground" />
            <select
              value={selectedFolderId}
              onChange={(e) => handleFolderSelect(e.target.value)}
              className="bg-transparent font-medium text-foreground focus:outline-none cursor-pointer"
            >
              <option value="all">All Managed Folders</option>
              {folders.map((f) => (
                <option key={f.id} value={f.id}>
                  {f.name}
                </option>
              ))}
            </select>
          </div>

          {/* Last Analyzed Info */}
          {analysisResult?.analyzed_at && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground px-2">
              <Clock size={13} />
              <span>
                Analyzed: <strong className="text-foreground">{formatDate(analysisResult.analyzed_at)}</strong>
              </span>
            </div>
          )}

          {/* Refresh Button */}
          <button
            onClick={() => loadAnalysis(selectedFolderId)}
            disabled={isLoading || isAnalyzing}
            title="Reload analysis results from database"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50 shadow-xs"
          >
            <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>

          {/* Analyze Now Split / Dropdown Button */}
          <div className="relative">
            <div className="inline-flex rounded-lg shadow-xs overflow-hidden border border-primary">
              <button
                onClick={() => handleRunAnalysis(selectedFolderId)}
                disabled={isAnalyzing}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                <Play size={13} className={isAnalyzing ? "animate-spin" : "fill-current"} />
                <span>{isAnalyzing ? "Analyzing..." : "Analyze Now"}</span>
              </button>
              <button
                onClick={() => setIsAnalyzeMenuOpen(!isAnalyzeMenuOpen)}
                disabled={isAnalyzing}
                className="px-2 py-1.5 bg-primary/95 text-primary-foreground border-l border-primary-foreground/20 hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                <ChevronDown size={14} />
              </button>
            </div>

            {/* Dropdown Menu */}
            {isAnalyzeMenuOpen && (
              <div className="absolute right-0 mt-1 w-56 rounded-lg bg-card border border-border shadow-lg z-30 py-1 text-xs">
                <button
                  onClick={() => handleRunAnalysis("all")}
                  className="w-full text-left px-3 py-2 hover:bg-muted font-medium transition-colors flex items-center justify-between"
                >
                  <span>Analyze All Managed Folders</span>
                </button>
                {selectedFolderId !== "all" && (
                  <button
                    onClick={() => handleRunAnalysis(selectedFolderId)}
                    className="w-full text-left px-3 py-2 hover:bg-muted font-medium transition-colors border-t border-border/40"
                  >
                    <span>Analyze Current Folder</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Error Alert */}
      {errorMessage && (
        <div className="p-4 rounded-xl bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle size={16} className="shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button
            onClick={() => loadAnalysis(selectedFolderId)}
            className="px-2.5 py-1 rounded bg-destructive/20 hover:bg-destructive/30 text-destructive font-semibold transition-colors"
          >
            Retry
          </button>
        </div>
      )}

      {/* Analyzing Banner State */}
      {isAnalyzing && (
        <div className="p-4 rounded-xl border border-primary/30 bg-primary/5 flex items-center gap-3 text-xs text-primary animate-pulse">
          <RefreshCw size={18} className="animate-spin text-primary shrink-0" />
          <div className="space-y-0.5">
            <p className="font-semibold text-foreground">
              Running deep storage scan & progressive hash duplicate detection...
            </p>
            <p className="text-muted-foreground">
              Traversing files safely within registered folder boundaries without filesystem mutations.
            </p>
          </div>
        </div>
      )}

      {/* Empty State when no analysis has run */}
      {!isLoading && !isAnalyzing && !analysisResult && (
        <div className="p-12 text-center border border-dashed border-border rounded-2xl bg-card/50 space-y-4">
          <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto">
            <HardDrive size={24} />
          </div>
          <div className="max-w-md mx-auto space-y-1.5">
            <h3 className="font-semibold text-base text-foreground">
              Storage Has Not Been Analyzed
            </h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Run an initial storage scan to inspect size distribution, uncover large files, calculate duplicate candidates with content hashing, and detect empty folders.
            </p>
          </div>
          <button
            onClick={() => handleRunAnalysis(selectedFolderId)}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-sm"
          >
            <Play size={14} className="fill-current" />
            <span>Analyze Storage Now</span>
          </button>
        </div>
      )}

      {/* Summary Cards */}
      {analysisResult && (
        <StorageSummaryCards
          data={analysisResult}
          activeTab={activeTab}
          onSelectTab={setActiveTab}
        />
      )}

      {/* Navigation Tabs Bar */}
      {analysisResult && (
        <div className="border-b border-border flex items-center gap-1 overflow-x-auto text-xs">
          <button
            onClick={() => setActiveTab("overview")}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === "overview"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <LayoutDashboard size={15} />
            <span>Overview</span>
          </button>

          <button
            onClick={() => setActiveTab("large_files")}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === "large_files"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <FileWarning size={15} />
            <span>Large Files</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-muted font-bold">
              {analysisResult.large_files_count}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("duplicates")}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === "duplicates"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <Copy size={15} />
            <span>Duplicates</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-muted font-bold">
              {analysisResult.duplicate_groups_count}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("file_types")}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === "file_types"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <FileCode size={15} />
            <span>File Types</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-muted font-bold">
              {analysisResult.file_types.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("empty_folders")}
            className={`flex items-center gap-2 px-4 py-2.5 font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === "empty_folders"
                ? "border-primary text-primary font-semibold"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            }`}
          >
            <FolderX size={15} />
            <span>Empty Folders</span>
            <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-muted font-bold">
              {analysisResult.empty_folders_count}
            </span>
          </button>
        </div>
      )}

      {/* Tab Panels */}
      {analysisResult && (
        <div>
          {activeTab === "overview" && (
            <StorageOverviewTab
              data={analysisResult}
              onSelectTab={handleSelectTabWithFilter}
              onOpenFolderInFiles={(folderId, path) =>
                handleOpenFolderInFiles(folderId, path)
              }
            />
          )}

          {activeTab === "large_files" && (
            <LargeFilesTab
              files={analysisResult.large_files}
              managedFolderId={analysisResult.managed_folder_id || undefined}
              onNavigateToReviewChanges={onNavigateToReviewChanges}
              onOpenLocation={(relPath, itemFolderId) => {
                const targetFolderId = itemFolderId || analysisResult.managed_folder_id;
                if (targetFolderId) {
                  handleOpenFolderInFiles(targetFolderId, relPath);
                }
              }}
            />
          )}

          {activeTab === "duplicates" && (
            <DuplicatesTab
              groups={analysisResult.duplicate_groups}
              managedFolderId={analysisResult.managed_folder_id || undefined}
              onNavigateToReviewChanges={onNavigateToReviewChanges}
              onOpenLocation={(relPath, itemFolderId) => {
                const targetFolderId = itemFolderId || analysisResult.managed_folder_id;
                if (targetFolderId) {
                  handleOpenFolderInFiles(targetFolderId, relPath);
                }
              }}
            />
          )}

          {activeTab === "file_types" && (
            <FileTypesTab
              fileTypes={analysisResult.file_types}
              initialCategoryFilter={categoryFilter}
            />
          )}

          {activeTab === "empty_folders" && (
            <EmptyFoldersTab
              folders={analysisResult.empty_folders}
              managedFolderId={analysisResult.managed_folder_id || undefined}
              onNavigateToReviewChanges={onNavigateToReviewChanges}
              onOpenFolder={(relPath, itemFolderId) => {
                const targetFolderId = itemFolderId || analysisResult.managed_folder_id;
                if (targetFolderId) {
                  handleOpenFolderInFiles(targetFolderId, relPath);
                }
              }}
            />
          )}
        </div>
      )}
    </div>
  );
};
