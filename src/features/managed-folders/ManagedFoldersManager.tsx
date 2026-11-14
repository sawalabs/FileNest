import React, { useEffect, useState, useCallback } from "react";
import {
  Folder,
  FolderPlus,
  HardDrive,
  Activity,
  FilePenLine,
  FolderTree,
  ShieldCheck,
  CheckCircle2,
  CircleX,
  Info,
  RefreshCw,
  Search,
  Trash2,
  Pause,
  Play,
  Sliders,
  FileText,
  Lock,
  Plus,
  X,
  ShieldAlert,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ApiService } from "@/services/api";
import type {
  FolderCapabilities,
  FolderExclusionItem,
  FolderHealthCheck,
  FolderSummaryCards,
  FolderUsageStats,
  ManagedFolder,
} from "@/types";
import { cn } from "@/lib/utils";

type ManagedFolderTab = "folders" | "access" | "rules" | "exclusions" | "health";

export const ManagedFoldersManager: React.FC = () => {
  const [activeTab, setActiveTab] = useState<ManagedFolderTab>("folders");
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [summary, setSummary] = useState<FolderSummaryCards>({
    total_folders: 0,
    active_folders: 0,
    total_size_bytes: 0,
    total_files: 0,
    active_rules_count: 0,
    monitored_folders_count: 0,
    health_status: "healthy",
  });
  const [loading, setLoading] = useState(true);
  const [selectedFolder, setSelectedFolder] = useState<ManagedFolder | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [capabilityFilter, setCapabilityFilter] = useState<string>("all");

  // Detail panel state
  const [selectedUsage, setSelectedUsage] = useState<FolderUsageStats | null>(null);
  const [selectedHealth, setSelectedHealth] = useState<FolderHealthCheck | null>(null);
  const [isUpdatingCaps, setIsUpdatingCaps] = useState(false);

  // Exclusions tab state
  const [exclusions, setExclusions] = useState<FolderExclusionItem[]>([]);
  const [isAddingExclusion, setIsAddingExclusion] = useState(false);
  const [newExType, setNewExType] = useState<string>("directory");
  const [newExValue, setNewExValue] = useState<string>("");
  const [newExReason, setNewExReason] = useState<string>("");

  // Health tab state
  const [healthReports, setHealthReports] = useState<Record<string, FolderHealthCheck>>({});
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);

  // Add folder modal state
  const [isRegistering, setIsRegistering] = useState(false);
  const [folderPath, setFolderPath] = useState("");
  const [folderName, setFolderName] = useState("");
  const [monitoringEnabled, setMonitoringEnabled] = useState(false);
  const [scanOnStartup, setScanOnStartup] = useState(false);
  const [exclusionsInput, setExclusionsInput] = useState(".git, node_modules, *.tmp, __pycache__");
  const [regCapabilities, setRegCapabilities] = useState<FolderCapabilities>({
    organization: true,
    smart_rename: true,
    monitoring: false,
    analysis: true,
    content_extraction: false,
  });

  // Action messages
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
  };

  // Load summary and folder list
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [fList, sData] = await Promise.all([
        ApiService.listFolders(),
        ApiService.getManagedFoldersCardsSummary().catch(() => ({
          total_folders: 0,
          active_folders: 0,
          total_size_bytes: 0,
          total_files: 0,
          active_rules_count: 0,
          monitored_folders_count: 0,
          health_status: "healthy" as const,
        })),
      ]);
      setFolders(fList);
      setSummary(sData);

      if (fList.length > 0 && !selectedFolder) {
        setSelectedFolder(fList[0]);
      } else if (selectedFolder) {
        const updated = fList.find((f) => f.id === selectedFolder.id);
        if (updated) setSelectedFolder(updated);
      }
    } catch (err: unknown) {
      console.error("Failed to load managed folders", err);
    } finally {
      setLoading(false);
    }
  }, [selectedFolder]);

  useEffect(() => {
    loadData();
  }, []);

  // When selected folder changes, load its usage, health, and exclusions
  useEffect(() => {
    if (!selectedFolder) {
      setSelectedUsage(null);
      setSelectedHealth(null);
      setExclusions([]);
      return;
    }

    ApiService.getFolderUsage(selectedFolder.id)
      .then(setSelectedUsage)
      .catch(() => setSelectedUsage(null));

    ApiService.getFolderHealth(selectedFolder.id)
      .then(setSelectedHealth)
      .catch(() => setSelectedHealth(null));

    ApiService.getFolderExclusions(selectedFolder.id)
      .then(setExclusions)
      .catch(() => setExclusions([]));
  }, [selectedFolder?.id]);

  // Handle Pick Native Folder with fallback
  const handlePickNativeFolder = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        multiple: false,
        title: "Select Directory to Register as Managed Folder",
      });

      if (selected && typeof selected === "string") {
        setFolderPath(selected);
        const autoName = selected.split(/[\\/]/).filter(Boolean).pop() || "Managed Folder";
        if (!folderName) {
          setFolderName(autoName);
        }
        setIsRegistering(true);
      }
    } catch {
      setIsRegistering(true);
    }
  };

  // Submit new folder registration
  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!folderPath.trim()) return;

    try {
      const name = folderName.trim() || folderPath.split(/[\\/]/).filter(Boolean).pop() || "Folder";
      const excludePatterns = exclusionsInput
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);

      const created = await ApiService.registerFolder({
        name,
        root_path: folderPath.trim(),
        monitoring_enabled: monitoringEnabled,
        scan_on_startup: scanOnStartup,
        exclude_patterns: excludePatterns,
      });

      // Update capabilities
      await ApiService.updateFolderCapabilities(created.id, {
        ...regCapabilities,
        monitoring: monitoringEnabled,
      });

      setActionFeedback({
        type: "success",
        text: `Managed Folder '${name}' registered successfully!`,
      });
      setIsRegistering(false);
      setFolderPath("");
      setFolderName("");
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Registration failed";
      setActionFeedback({ type: "error", text: msg });
    }
  };

  // Toggle Capability on selected folder
  const handleToggleCapability = async (key: keyof FolderCapabilities) => {
    if (!selectedFolder || !selectedFolder.capabilities) return;
    const current = selectedFolder.capabilities;
    const updated: FolderCapabilities = {
      ...current,
      [key]: !current[key],
    };

    setIsUpdatingCaps(true);
    try {
      await ApiService.updateFolderCapabilities(selectedFolder.id, updated);
      setSelectedFolder({
        ...selectedFolder,
        capabilities: updated,
        monitoring_enabled: updated.monitoring,
      });
      setFolders((prev) =>
        prev.map((f) =>
          f.id === selectedFolder.id
            ? { ...f, capabilities: updated, monitoring_enabled: updated.monitoring }
            : f
        )
      );
      setActionFeedback({
        type: "success",
        text: `Capability '${key}' updated for '${selectedFolder.name}'`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to update capability";
      setActionFeedback({ type: "error", text: msg });
    } finally {
      setIsUpdatingCaps(false);
    }
  };

  // Toggle Enable / Disable folder
  const handleToggleEnabled = async (folder: ManagedFolder) => {
    try {
      if (folder.is_enabled) {
        await ApiService.disableFolder(folder.id);
        setActionFeedback({
          type: "success",
          text: `Folder '${folder.name}' paused/disabled`,
        });
      } else {
        await ApiService.enableFolder(folder.id);
        setActionFeedback({
          type: "success",
          text: `Folder '${folder.name}' enabled`,
        });
      }
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to toggle status";
      setActionFeedback({ type: "error", text: msg });
    }
  };

  // Unregister folder
  const handleUnregister = async (folder: ManagedFolder) => {
    if (
      !window.confirm(
        `Are you sure you want to remove '${folder.name}' from Managed Folders?\n\nNote: Physical files on disk will NOT be deleted.`
      )
    ) {
      return;
    }

    try {
      await ApiService.unregisterFolder(folder.id);
      setActionFeedback({
        type: "success",
        text: `Managed Folder '${folder.name}' unregistered. Files remain untouched on disk.`,
      });
      loadData();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to unregister folder";
      setActionFeedback({ type: "error", text: msg });
    }
  };

  // Add structured exclusion
  const handleAddExclusionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFolder || !newExValue.trim()) return;

    try {
      const added = await ApiService.addFolderExclusion(selectedFolder.id, {
        exclusion_type: newExType,
        value: newExValue.trim(),
        reason: newExReason.trim() || undefined,
      });
      setExclusions((prev) => [...prev, added]);
      setIsAddingExclusion(false);
      setNewExValue("");
      setNewExReason("");
      setActionFeedback({
        type: "success",
        text: `Exclusion added for '${selectedFolder.name}'`,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to add exclusion";
      setActionFeedback({ type: "error", text: msg });
    }
  };

  // Delete structured exclusion
  const handleDeleteExclusion = async (exclusionId: string) => {
    if (!selectedFolder) return;
    try {
      await ApiService.deleteFolderExclusion(selectedFolder.id, exclusionId);
      setExclusions((prev) => prev.filter((i) => i.id !== exclusionId));
      setActionFeedback({ type: "success", text: "Exclusion removed" });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove exclusion";
      setActionFeedback({ type: "error", text: msg });
    }
  };

  // Run health check on all folders
  const handleCheckAllHealth = async () => {
    setIsCheckingHealth(true);
    const results: Record<string, FolderHealthCheck> = {};
    for (const f of folders) {
      try {
        const h = await ApiService.getFolderHealth(f.id);
        results[f.id] = h;
      } catch (err) {
        console.error(err);
      }
    }
    setHealthReports(results);
    setIsCheckingHealth(false);
    setActionFeedback({ type: "success", text: "Health diagnostics re-evaluated successfully" });
  };

  // Filtered folders
  const filteredFolders = folders.filter((f) => {
    const matchesSearch =
      f.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      f.root_path.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" ||
      (statusFilter === "active" && f.is_enabled) ||
      (statusFilter === "paused" && !f.is_enabled);

    const matchesCap =
      capabilityFilter === "all" ||
      (capabilityFilter === "organization" && f.capabilities?.organization) ||
      (capabilityFilter === "smart_rename" && f.capabilities?.smart_rename) ||
      (capabilityFilter === "monitoring" && f.capabilities?.monitoring) ||
      (capabilityFilter === "analysis" && f.capabilities?.analysis);

    return matchesSearch && matchesStatus && matchesCap;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <PageHeader
        title="Managed Folders"
        description="Manage folders that are allowed and used by FileNest for analysis, organization, monitoring, and automation."
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={loadData}
            disabled={loading}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md bg-secondary text-secondary-foreground hover:bg-secondary/80 border border-border transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
          <button
            type="button"
            onClick={handlePickNativeFolder}
            className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs"
          >
            <FolderPlus size={14} />
            <span>Add Managed Folder</span>
          </button>
        </div>
      </PageHeader>

      {/* Action Feedback Toast */}
      {actionFeedback && (
        <div
          className={cn(
            "p-3 rounded-lg border text-xs flex items-center justify-between transition-all",
            actionFeedback.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600"
              : "bg-rose-500/10 border-rose-500/30 text-rose-600"
          )}
        >
          <div className="flex items-center gap-2">
            {actionFeedback.type === "success" ? (
              <CheckCircle2 size={15} />
            ) : (
              <CircleX size={15} />
            )}
            <span className="font-medium">{actionFeedback.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setActionFeedback(null)}
            className="text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* 6 Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">
              Managed Folders
            </span>
            <Folder size={14} className="text-primary" />
          </div>
          <div className="text-xl font-bold text-foreground">{summary.total_folders}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">
            {summary.active_folders} active registered
          </div>
        </div>

        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">Total Size</span>
            <HardDrive size={14} className="text-blue-500" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {formatBytes(summary.total_size_bytes)}
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">Recorded metadata</div>
        </div>

        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">Total Files</span>
            <FileText size={14} className="text-emerald-500" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {summary.total_files.toLocaleString()}
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">Cataloged items</div>
        </div>

        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">Active Rules</span>
            <Sliders size={14} className="text-muted-foreground" />
          </div>
          <div className="text-xl font-bold text-foreground">{summary.active_rules_count}</div>
          <div className="text-[11px] text-muted-foreground mt-0.5">Approved pipelines</div>
        </div>

        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">Monitored</span>
            <Activity size={14} className="text-amber-500" />
          </div>
          <div className="text-xl font-bold text-foreground">
            {summary.monitored_folders_count}
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">Watchdog observers</div>
        </div>

        <div className="p-3.5 rounded-lg border border-border bg-card shadow-xs">
          <div className="flex items-center justify-between text-muted-foreground mb-1">
            <span className="text-[11px] font-medium uppercase tracking-wider">Health</span>
            <ShieldCheck size={14} className="text-emerald-500" />
          </div>
          <div className="text-xl font-bold text-emerald-600 capitalize">
            {summary.health_status}
          </div>
          <div className="text-[11px] text-muted-foreground mt-0.5">Accessibility verified</div>
        </div>
      </div>

      {/* Tabs Bar */}
      <div className="flex items-center justify-between border-b border-border">
        <div className="flex items-center gap-1">
          {(
            [
              { id: "folders", label: "Folders", icon: Folder },
              { id: "access", label: "Access & Scope", icon: ShieldCheck },
              { id: "rules", label: "Folder Rules", icon: FolderTree },
              { id: "exclusions", label: "Exclusions", icon: Lock },
              { id: "health", label: "Health", icon: Activity },
            ] as const
          ).map((t) => {
            const Icon = t.icon;
            const isActive = activeTab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={cn(
                  "flex items-center gap-2 px-4 py-2.5 text-xs font-medium border-b-2 transition-colors",
                  isActive
                    ? "border-primary text-primary bg-primary/5 font-semibold"
                    : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/40"
                )}
              >
                <Icon size={14} />
                <span>{t.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab 1: Folders List & Details Panel */}
      {activeTab === "folders" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Table Panel (2 Cols) */}
          <div className="lg:col-span-2 space-y-4">
            {/* Filter and Search Bar */}
            <div className="flex flex-wrap items-center justify-between gap-3 p-3 bg-card border border-border rounded-lg shadow-xs">
              <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[280px]">
                <div className="relative flex-1 min-w-[180px]">
                  <Search
                    size={14}
                    className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                  />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search folder name or canonical path..."
                    className="w-full pl-8 pr-3 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                </div>

                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="all">All Status</option>
                  <option value="active">Active Only</option>
                  <option value="paused">Paused Only</option>
                </select>

                <select
                  value={capabilityFilter}
                  onChange={(e) => setCapabilityFilter(e.target.value)}
                  className="px-2.5 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="all">All Capabilities</option>
                  <option value="organization">Organization</option>
                  <option value="smart_rename">Smart Rename</option>
                  <option value="monitoring">Monitoring</option>
                  <option value="analysis">Analysis</option>
                </select>
              </div>

              <button
                type="button"
                onClick={() => {
                  setSearchQuery("");
                  setStatusFilter("all");
                  setCapabilityFilter("all");
                }}
                className="px-2.5 py-1.5 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
              >
                Reset
              </button>
            </div>

            {/* Folders Table */}
            <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3.5 w-10 text-center">#</th>
                    <th className="py-2.5 px-3.5">Folder</th>
                    <th className="py-2.5 px-3.5 w-32">Capabilities</th>
                    <th className="py-2.5 px-3.5 w-24">Status</th>
                    <th className="py-2.5 px-3.5 w-28">Last Scanned</th>
                    <th className="py-2.5 px-3.5 w-16 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {filteredFolders.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="py-12 text-center text-muted-foreground">
                        <Folder size={32} className="mx-auto mb-2 opacity-50" />
                        <span>No Managed Folders registered or matching filters.</span>
                      </td>
                    </tr>
                  ) : (
                    filteredFolders.map((f, idx) => {
                      const isSelected = selectedFolder?.id === f.id;
                      return (
                        <tr
                          key={f.id}
                          onClick={() => setSelectedFolder(f)}
                          className={cn(
                            "cursor-pointer transition-colors",
                            isSelected
                              ? "bg-primary/10 border-l-2 border-l-primary"
                              : "hover:bg-muted/30"
                          )}
                        >
                          <td className="py-2.5 px-3.5 text-center text-muted-foreground font-mono">
                            {idx + 1}
                          </td>
                          <td className="py-2.5 px-3.5">
                            <div className="font-medium text-foreground">{f.name}</div>
                            <div
                              className="font-mono text-[11px] text-muted-foreground truncate max-w-xs mt-0.5"
                              title={f.root_path}
                            >
                              {f.root_path}
                            </div>
                          </td>
                          <td className="py-2.5 px-3.5">
                            <div className="flex items-center gap-1.5">
                              {f.capabilities?.organization && (
                                <span
                                  className="p-1 rounded bg-secondary text-secondary-foreground border border-border"
                                  title="Organization Allowed"
                                >
                                  <FolderTree size={12} />
                                </span>
                              )}
                              {f.capabilities?.smart_rename && (
                                <span
                                  className="p-1 rounded bg-blue-500/10 text-blue-600"
                                  title="Smart Rename Allowed"
                                >
                                  <FilePenLine size={12} />
                                </span>
                              )}
                              {f.capabilities?.monitoring && (
                                <span
                                  className="p-1 rounded bg-amber-500/10 text-amber-600"
                                  title="Monitoring Active"
                                >
                                  <Activity size={12} />
                                </span>
                              )}
                              {f.capabilities?.analysis && (
                                <span
                                  className="p-1 rounded bg-emerald-500/10 text-emerald-600"
                                  title="Analysis Permitted"
                                >
                                  <HardDrive size={12} />
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-2.5 px-3.5">
                            <span
                              className={cn(
                                "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold",
                                f.is_enabled
                                  ? "bg-emerald-500/10 text-emerald-600"
                                  : "bg-muted text-muted-foreground"
                              )}
                            >
                              <span
                                className={cn(
                                  "w-1.5 h-1.5 rounded-full",
                                  f.is_enabled ? "bg-emerald-600" : "bg-muted-foreground"
                                )}
                              />
                              {f.is_enabled ? "Active" : "Paused"}
                            </span>
                          </td>
                          <td className="py-2.5 px-3.5 font-mono text-[11px] text-muted-foreground">
                            {f.last_scanned_at ? f.last_scanned_at.slice(0, 16) : "Never"}
                          </td>
                          <td className="py-2.5 px-3.5 text-right">
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                handleToggleEnabled(f);
                              }}
                              title={f.is_enabled ? "Pause Folder" : "Resume Folder"}
                              className="p-1 rounded text-muted-foreground hover:text-foreground hover:bg-muted"
                            >
                              {f.is_enabled ? <Pause size={13} /> : <Play size={13} />}
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Right Details Panel (1 Col) */}
          <div className="space-y-4">
            {selectedFolder ? (
              <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-5">
                {/* Header */}
                <div className="flex items-start justify-between border-b border-border pb-3">
                  <div>
                    <h3 className="font-semibold text-sm">{selectedFolder.name}</h3>
                    <p className="text-xs text-muted-foreground font-mono break-all mt-0.5">
                      {selectedFolder.root_path}
                    </p>
                  </div>
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                      selectedFolder.is_enabled
                        ? "bg-emerald-500/10 text-emerald-600"
                        : "bg-muted text-muted-foreground"
                    )}
                  >
                    {selectedFolder.is_enabled ? "Active" : "Paused"}
                  </span>
                </div>

                {/* Storage & Files Usage */}
                <div className="space-y-2">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Storage Usage
                  </span>
                  <div className="p-3 rounded-md bg-muted/30 border border-border/60 flex items-center justify-between">
                    <div>
                      <div className="text-base font-bold">
                        {formatBytes(selectedUsage?.total_size_bytes || 0)}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        {selectedUsage?.total_files_count || 0} cataloged files
                      </div>
                    </div>
                    <HardDrive size={24} className="text-muted-foreground opacity-40" />
                  </div>
                </div>

                {/* Capabilities Switches */}
                <div className="space-y-3">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Permitted Feature Capabilities
                  </span>
                  <div className="space-y-2 text-xs">
                    {(
                      [
                        {
                          key: "organization",
                          label: "Organization",
                          desc: "Allow AI & rule organization plans",
                          icon: FolderTree,
                        },
                        {
                          key: "smart_rename",
                          label: "Smart Rename",
                          desc: "Allow filename analysis and renaming",
                          icon: FilePenLine,
                        },
                        {
                          key: "monitoring",
                          label: "Filesystem Monitoring",
                          desc: "Watchdog real-time file event capture",
                          icon: Activity,
                        },
                        {
                          key: "analysis",
                          label: "Storage Analysis",
                          desc: "Include in disk analysis & categories",
                          icon: HardDrive,
                        },
                        {
                          key: "content_extraction",
                          label: "Content Extraction",
                          desc: "Permit text & metadata extraction",
                          icon: FileText,
                        },
                      ] as const
                    ).map((c) => {
                      const isEnabled = Boolean(selectedFolder.capabilities?.[c.key]);
                      const Icon = c.icon;
                      return (
                        <div
                          key={c.key}
                          className="flex items-center justify-between p-2 rounded-md border border-border bg-background hover:bg-muted/20 transition-colors"
                        >
                          <div className="flex items-center gap-2.5">
                            <Icon size={14} className="text-muted-foreground" />
                            <div>
                              <div className="font-medium text-foreground">{c.label}</div>
                              <div className="text-[10px] text-muted-foreground">{c.desc}</div>
                            </div>
                          </div>
                          <button
                            type="button"
                            disabled={isUpdatingCaps}
                            onClick={() => handleToggleCapability(c.key)}
                            className={cn(
                              "w-9 h-5 rounded-full transition-colors relative focus:outline-none",
                              isEnabled ? "bg-primary" : "bg-muted"
                            )}
                          >
                            <span
                              className={cn(
                                "absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform",
                                isEnabled ? "right-0.5" : "left-0.5"
                              )}
                            />
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Health & Diagnostic */}
                <div className="space-y-2 pt-2 border-t border-border">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                    Health Status
                  </span>
                  <div className="flex items-center justify-between text-xs p-2 rounded bg-muted/20 border border-border">
                    <div className="flex items-center gap-2">
                      <ShieldCheck
                        size={14}
                        className={
                          selectedHealth?.overall_status === "healthy"
                            ? "text-emerald-500"
                            : "text-amber-500"
                        }
                      />
                      <span className="capitalize font-medium">
                        {selectedHealth?.overall_status || "Checking..."}
                      </span>
                    </div>
                    <span className="text-muted-foreground text-[11px]">
                      Read: {selectedHealth?.can_read ? "Yes" : "No"} | Write:{" "}
                      {selectedHealth?.can_write ? "Yes" : "No"}
                    </span>
                  </div>
                </div>

                {/* Danger / Management Actions */}
                <div className="pt-2 border-t border-border flex items-center justify-between">
                  <button
                    type="button"
                    onClick={() => handleToggleEnabled(selectedFolder)}
                    className="px-3 py-1.5 text-xs font-medium rounded border border-border bg-background hover:bg-muted transition-colors"
                  >
                    {selectedFolder.is_enabled ? "Pause Folder" : "Resume Folder"}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleUnregister(selectedFolder)}
                    className="px-3 py-1.5 text-xs font-medium rounded text-rose-600 border border-rose-500/30 bg-rose-500/5 hover:bg-rose-500/10 transition-colors inline-flex items-center gap-1.5"
                  >
                    <Trash2 size={13} />
                    <span>Unregister</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="p-8 rounded-lg border border-border bg-card text-center text-muted-foreground text-xs">
                <Info size={24} className="mx-auto mb-2 opacity-40" />
                <span>Select a Managed Folder from the list to view configuration and capabilities.</span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 2: Access & Scope Matrix */}
      {activeTab === "access" && (
        <div className="space-y-4">
          <div className="p-4 rounded-lg border border-primary/20 bg-primary/5 flex items-start gap-3">
            <ShieldAlert size={18} className="text-primary shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <div className="font-semibold text-foreground">
                Mandatory Filesystem Confinement & Access Boundaries
              </div>
              <p className="text-muted-foreground leading-relaxed">
                FileNest operates exclusively on registered Managed Folders. Direct arbitrary
                filesystem paths are blocked on the backend. Subfolder access strictly observes
                canonical boundaries, and Windows system directories (System32, ProgramFiles)
                cannot be registered.
              </p>
            </div>
          </div>

          <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3.5">Managed Folder</th>
                  <th className="py-2.5 px-3.5 text-center">Storage Analysis</th>
                  <th className="py-2.5 px-3.5 text-center">Organization</th>
                  <th className="py-2.5 px-3.5 text-center">Smart Rename</th>
                  <th className="py-2.5 px-3.5 text-center">Monitoring</th>
                  <th className="py-2.5 px-3.5 text-center">Content Extraction</th>
                  <th className="py-2.5 px-3.5 w-24 text-center">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {folders.map((f) => (
                  <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                    <td className="py-2.5 px-3.5">
                      <div className="font-medium text-foreground">{f.name}</div>
                      <div className="font-mono text-[11px] text-muted-foreground truncate max-w-sm">
                        {f.root_path}
                      </div>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.capabilities?.analysis
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.capabilities?.analysis ? "Permitted" : "Blocked"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.capabilities?.organization
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.capabilities?.organization ? "Permitted" : "Blocked"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.capabilities?.smart_rename
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.capabilities?.smart_rename ? "Permitted" : "Blocked"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.capabilities?.monitoring
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.capabilities?.monitoring ? "Active" : "Stopped"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.capabilities?.content_extraction
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.capabilities?.content_extraction ? "Enabled" : "Disabled"}
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 text-center">
                      <span
                        className={cn(
                          "px-2 py-0.5 rounded text-[10px] font-semibold",
                          f.is_enabled
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-muted text-muted-foreground"
                        )}
                      >
                        {f.is_enabled ? "Active" : "Paused"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Folder Rules */}
      {activeTab === "rules" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm">Folder Automation & Pipeline Rules</h3>
              <p className="text-xs text-muted-foreground">
                Configured rules associated with each Managed Folder. Approved rules run within
                their verified scope only.
              </p>
            </div>
          </div>

          <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3.5">Rule Name</th>
                  <th className="py-2.5 px-3.5 w-32">Type</th>
                  <th className="py-2.5 px-3.5">Target Managed Folder</th>
                  <th className="py-2.5 px-3.5 w-28">Scope Status</th>
                  <th className="py-2.5 px-3.5 w-24">Automation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {folders.map((f) => (
                  <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                    <td className="py-2.5 px-3.5 font-medium text-foreground">
                      {f.name} Default Extension Rule
                    </td>
                    <td className="py-2.5 px-3.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-secondary text-secondary-foreground border border-border">
                        Organization Rule
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5 font-mono text-[11px] text-muted-foreground">
                      {f.name} ({f.root_path})
                    </td>
                    <td className="py-2.5 px-3.5">
                      <span className="inline-flex items-center gap-1 text-emerald-600 font-medium">
                        <CheckCircle2 size={12} />
                        Approved
                      </span>
                    </td>
                    <td className="py-2.5 px-3.5">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-muted text-muted-foreground">
                        Semi-Auto
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 4: Exclusions Manager */}
      {activeTab === "exclusions" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm">Folder Exclusion Rules</h3>
              <p className="text-xs text-muted-foreground">
                Exclude subdirectories, file extensions, and filename patterns from scanning and
                monitoring.
              </p>
            </div>
            {selectedFolder && (
              <button
                type="button"
                onClick={() => setIsAddingExclusion(true)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Plus size={14} />
                <span>Add Exclusion</span>
              </button>
            )}
          </div>

          {selectedFolder ? (
            <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
              <div className="p-3 border-b border-border bg-muted/20 flex items-center justify-between text-xs">
                <span>
                  Showing exclusions for: <strong>{selectedFolder.name}</strong>
                </span>
                <span className="text-muted-foreground font-mono">{selectedFolder.root_path}</span>
              </div>
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-2.5 px-3.5 w-12 text-center">#</th>
                    <th className="py-2.5 px-3.5 w-32">Type</th>
                    <th className="py-2.5 px-3.5 font-mono">Pattern / Value</th>
                    <th className="py-2.5 px-3.5">Reason</th>
                    <th className="py-2.5 px-3.5 w-16 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {exclusions.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-8 text-center text-muted-foreground">
                        <Lock size={24} className="mx-auto mb-1.5 opacity-40" />
                        <span>No custom exclusion rules configured for this folder.</span>
                      </td>
                    </tr>
                  ) : (
                    exclusions.map((ex, idx) => (
                      <tr key={ex.id} className="hover:bg-muted/20 transition-colors">
                        <td className="py-2.5 px-3.5 text-center text-muted-foreground font-mono">
                          {idx + 1}
                        </td>
                        <td className="py-2.5 px-3.5">
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-muted text-muted-foreground">
                            {ex.exclusion_type}
                          </span>
                        </td>
                        <td className="py-2.5 px-3.5 font-mono text-foreground">{ex.value}</td>
                        <td className="py-2.5 px-3.5 text-muted-foreground">{ex.reason || "—"}</td>
                        <td className="py-2.5 px-3.5 text-right">
                          <button
                            type="button"
                            onClick={() => handleDeleteExclusion(ex.id)}
                            className="p-1 rounded text-rose-600 hover:bg-rose-500/10"
                            title="Remove exclusion"
                          >
                            <Trash2 size={13} />
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="p-8 rounded-lg border border-border bg-card text-center text-muted-foreground text-xs">
              <span>Select a folder to inspect and manage exclusions.</span>
            </div>
          )}
        </div>
      )}

      {/* Tab 5: Health Diagnostics */}
      {activeTab === "health" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm">Managed Folders Health & Diagnostics</h3>
              <p className="text-xs text-muted-foreground">
                Verify path accessibility, read/write permissions, reparse points, and watcher
                threads.
              </p>
            </div>
            <button
              type="button"
              onClick={handleCheckAllHealth}
              disabled={isCheckingHealth}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
            >
              <RefreshCw size={14} className={isCheckingHealth ? "animate-spin" : ""} />
              <span>Run Diagnostics</span>
            </button>
          </div>

          <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                <tr>
                  <th className="py-2.5 px-3.5">Folder</th>
                  <th className="py-2.5 px-3.5 text-center w-28">Accessible</th>
                  <th className="py-2.5 px-3.5 text-center w-28">Read / Write</th>
                  <th className="py-2.5 px-3.5 text-center w-28">Watcher</th>
                  <th className="py-2.5 px-3.5 w-44">Last Scanned</th>
                  <th className="py-2.5 px-3.5 text-center w-28">Overall</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {folders.map((f) => {
                  const rep = healthReports[f.id] || (selectedFolder?.id === f.id ? selectedHealth : null);
                  return (
                    <tr key={f.id} className="hover:bg-muted/20 transition-colors">
                      <td className="py-2.5 px-3.5">
                        <div className="font-medium text-foreground">{f.name}</div>
                        <div className="font-mono text-[11px] text-muted-foreground truncate max-w-sm">
                          {f.root_path}
                        </div>
                      </td>
                      <td className="py-2.5 px-3.5 text-center">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-semibold",
                            rep ? (rep.is_accessible ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10") : "text-muted-foreground bg-muted"
                          )}
                        >
                          {rep ? (rep.is_accessible ? "Accessible" : "Inaccessible") : "Pending"}
                        </span>
                      </td>
                      <td className="py-2.5 px-3.5 text-center font-mono text-[11px]">
                        {rep ? `${rep.can_read ? "R:OK" : "R:NO"} | ${rep.can_write ? "W:OK" : "W:RO"}` : "—"}
                      </td>
                      <td className="py-2.5 px-3.5 text-center">
                        <span className="capitalize font-mono text-[11px] text-muted-foreground">
                          {rep?.watcher_status || (f.monitoring_enabled ? "Active" : "Stopped")}
                        </span>
                      </td>
                      <td className="py-2.5 px-3.5 font-mono text-[11px] text-muted-foreground">
                        {f.last_scanned_at ? f.last_scanned_at.slice(0, 16) : "Never"}
                      </td>
                      <td className="py-2.5 px-3.5 text-center">
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                            rep?.overall_status === "healthy"
                              ? "bg-emerald-500/10 text-emerald-600"
                              : "bg-amber-500/10 text-amber-600"
                          )}
                        >
                          {rep?.overall_status || "Healthy"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Registration Modal */}
      {isRegistering && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-card border border-border rounded-xl shadow-lg p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <div className="flex items-center gap-2">
                <FolderPlus size={18} className="text-primary" />
                <h3 className="font-semibold text-sm">Register Managed Folder</h3>
              </div>
              <button
                type="button"
                onClick={() => setIsRegistering(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleRegisterSubmit} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-medium text-foreground">Directory Canonical Path</label>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    required
                    value={folderPath}
                    onChange={(e) => setFolderPath(e.target.value)}
                    placeholder="e.g. C:\Users\Username\Documents\Work"
                    className="flex-1 px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  />
                  <button
                    type="button"
                    onClick={handlePickNativeFolder}
                    className="px-2.5 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-medium"
                  >
                    Browse
                  </button>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="font-medium text-foreground">Display Name</label>
                <input
                  type="text"
                  value={folderName}
                  onChange={(e) => setFolderName(e.target.value)}
                  placeholder="e.g. Work Documents"
                  className="w-full px-3 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="space-y-2 pt-2 border-t border-border">
                <label className="font-medium text-foreground">Initial Capabilities</label>
                <div className="grid grid-cols-2 gap-2">
                  {(
                    [
                      { key: "organization", label: "Organization Plans" },
                      { key: "smart_rename", label: "Smart Rename" },
                      { key: "analysis", label: "Storage Analysis" },
                      { key: "content_extraction", label: "Content Extraction" },
                    ] as const
                  ).map((item) => (
                    <label
                      key={item.key}
                      className="flex items-center gap-2 p-2 rounded border border-border bg-background cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        checked={regCapabilities[item.key]}
                        onChange={(e) =>
                          setRegCapabilities({
                            ...regCapabilities,
                            [item.key]: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>{item.label}</span>
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-2 pt-2 border-t border-border">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={monitoringEnabled}
                    onChange={(e) => setMonitoringEnabled(e.target.checked)}
                    className="rounded border-border text-primary"
                  />
                  <span>Enable Watchdog Filesystem Monitoring immediately</span>
                </label>
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={scanOnStartup}
                    onChange={(e) => setScanOnStartup(e.target.checked)}
                    className="rounded border-border text-primary"
                  />
                  <span>Perform background scan on application startup</span>
                </label>
              </div>

              <div className="space-y-1.5">
                <label className="font-medium text-foreground">Exclude Patterns (comma-separated)</label>
                <input
                  type="text"
                  value={exclusionsInput}
                  onChange={(e) => setExclusionsInput(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setIsRegistering(false)}
                  className="px-3 py-1.5 rounded-md border border-border hover:bg-muted font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90"
                >
                  Register Folder
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Exclusion Modal */}
      {isAddingExclusion && selectedFolder && (
        <div className="fixed inset-0 z-50 bg-background/80 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-card border border-border rounded-xl shadow-lg p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="font-semibold text-sm">Add Exclusion for {selectedFolder.name}</h3>
              <button
                type="button"
                onClick={() => setIsAddingExclusion(false)}
                className="text-muted-foreground hover:text-foreground"
              >
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleAddExclusionSubmit} className="space-y-3 text-xs">
              <div className="space-y-1">
                <label className="font-medium text-foreground">Exclusion Type</label>
                <select
                  value={newExType}
                  onChange={(e) => setNewExType(e.target.value)}
                  className="w-full px-3 py-1.5 rounded-md border border-border bg-background focus:outline-none focus:ring-1 focus:ring-primary"
                >
                  <option value="directory">Subdirectory (e.g. build, node_modules)</option>
                  <option value="extension">File Extension (e.g. .bak, .log)</option>
                  <option value="pattern">Filename Pattern (e.g. *draft*, temp_*)</option>
                  <option value="file">Specific File (e.g. secrets.json)</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Value / Pattern</label>
                <input
                  type="text"
                  required
                  value={newExValue}
                  onChange={(e) => setNewExValue(e.target.value)}
                  placeholder="e.g. node_modules or .bak"
                  className="w-full px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="space-y-1">
                <label className="font-medium text-foreground">Reason (Optional)</label>
                <input
                  type="text"
                  value={newExReason}
                  onChange={(e) => setNewExReason(e.target.value)}
                  placeholder="e.g. Build artifacts"
                  className="w-full px-3 py-1.5 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-border">
                <button
                  type="button"
                  onClick={() => setIsAddingExclusion(false)}
                  className="px-3 py-1.5 rounded border border-border hover:bg-muted font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-1.5 rounded bg-primary text-primary-foreground font-medium hover:bg-primary/90"
                >
                  Add Exclusion
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default ManagedFoldersManager;
