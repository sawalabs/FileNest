import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  Settings,
  Sparkles,
  FolderTree,
  Activity,
  ShieldCheck,
  HardDrive,
  Info,
  Save,
  RotateCcw,
  CheckCircle2,
  CircleX,
  Eye,
  EyeOff,
  Trash2,
  Terminal,
  Database,
  X,
  Search,
  RefreshCw,
  Server,
  ChevronRight,
  ArrowRightLeft,
  Download,
  FolderOpen,
  PackageCheck,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { ApiService } from "@/services/api";
import { usePreferences } from "@/contexts/PreferencesContext";
import type {
  AllSettingsResponse,
  AppUpdateStatusResponse,
  MaintenanceActionResult,
  TestConnectionResponse,
  ModelInfo,
} from "@/types";
import { cn } from "@/lib/utils";

type SettingsTab =
  | "general"
  | "ai"
  | "organization"
  | "monitoring"
  | "security"
  | "storage"
  | "about";

interface SubmenuItem {
  id: string;
  label: string;
}

const CATEGORIES: { id: SettingsTab; label: string; icon: React.ElementType }[] = [
  { id: "general", label: "General", icon: Settings },
  { id: "ai", label: "Analysis & AI", icon: Sparkles },
  { id: "organization", label: "Organization", icon: FolderTree },
  { id: "monitoring", label: "Monitoring", icon: Activity },
  { id: "security", label: "Security & Access", icon: ShieldCheck },
  { id: "storage", label: "Storage & Database", icon: HardDrive },
  { id: "about", label: "About", icon: Info },
];

const SUBMENU_MAP: Record<SettingsTab, SubmenuItem[]> = {
  general: [
    { id: "all", label: "All Settings" },
    { id: "startup", label: "Startup & Behavior" },
    { id: "ui", label: "User Interface" },
    { id: "notifications", label: "Notifications" },
  ],
  ai: [
    { id: "all", label: "All Settings" },
    { id: "gateway", label: "9Router Gateway" },
    { id: "models", label: "Model Selection" },
    { id: "parameters", label: "Parameters & Tuning" },
    { id: "privacy", label: "Privacy & Data" },
  ],
  organization: [
    { id: "all", label: "All Settings" },
    { id: "structure", label: "Folder Structure" },
    { id: "conflicts", label: "Conflict Handling" },
  ],
  monitoring: [
    { id: "all", label: "All Settings" },
    { id: "processing", label: "Event Processing" },
    { id: "ignores", label: "Ignore Patterns" },
  ],
  security: [
    { id: "all", label: "All Settings" },
    { id: "mandatory", label: "Mandatory Policies" },
    { id: "approvals", label: "Approval & Safety" },
  ],
  storage: [
    { id: "all", label: "All Settings" },
    { id: "diagnostics", label: "Database Metrics" },
    { id: "maintenance", label: "Maintenance Tools" },
  ],
  about: [
    { id: "all", label: "All Settings" },
    { id: "info", label: "Application Details" },
    { id: "stack", label: "Technology Stack" },
  ],
};

export const SettingsManager: React.FC = () => {
  const {
    setTheme,
    setDefaultFileView,
    setDefaultTableDensity,
    setShowFileExtensions,
    setShowHiddenFiles,
    updateGeneralPreferences,
  } = usePreferences();

  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [activeSubmenu, setActiveSubmenu] = useState<string>("all");
  const [settings, setSettings] = useState<AllSettingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [lastSavedTime, setLastSavedTime] = useState<string | null>(null);

  // Unsaved changes tracking per category
  const [editedGeneral, setEditedGeneral] = useState<Record<string, any>>({});
  const [editedAI, setEditedAI] = useState<Record<string, any>>({});
  const [editedOrg, setEditedOrg] = useState<Record<string, any>>({});
  const [editedMon, setEditedMon] = useState<Record<string, any>>({});
  const [editedSec, setEditedSec] = useState<Record<string, any>>({});

  // 9Router API Key input state
  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showApiKey, setShowApiKey] = useState(false);

  // Testing connection state
  const [isTesting9Router, setIsTesting9Router] = useState(false);
  const [routerTestResult, setRouterTestResult] = useState<TestConnectionResponse | null>(null);

  // OpenRouter Fallback state
  const [openRouterKeyInput, setOpenRouterKeyInput] = useState("");
  const [showOpenRouterKey, setShowOpenRouterKey] = useState(false);
  const [isTestingOpenRouter, setIsTestingOpenRouter] = useState(false);
  const [openRouterTestResult, setOpenRouterTestResult] = useState<TestConnectionResponse | null>(null);

  const [availableModels, setAvailableModels] = useState<string[]>([]);

  // Model list and checkbox selection state
  const [modelList, setModelList] = useState<ModelInfo[]>([]);
  const [isLoadingModels, setIsLoadingModels] = useState(false);
  const [modelSearchQuery, setModelSearchQuery] = useState("");
  const [modelFilterTab, setModelFilterTab] = useState<"all" | "selected" | "vision">("all");
  const [selectedModelIds, setSelectedModelIds] = useState<string[]>([]);
  const [isSavingModels, setIsSavingModels] = useState(false);
  const [modelSaveSuccess, setModelSaveSuccess] = useState(false);

  // Database maintenance state
  const [maintenanceOutput, setMaintenanceOutput] = useState<MaintenanceActionResult | null>(null);
  const [isPerformingMaintenance, setIsPerformingMaintenance] = useState(false);

  // Application update & installer state
  const [updateStatus, setUpdateStatus] = useState<AppUpdateStatusResponse | null>(null);
  const [isCheckingUpdates, setIsCheckingUpdates] = useState(false);
  const [isApplyingUpdate, setIsApplyingUpdate] = useState(false);
  const [customInstallerPath, setCustomInstallerPath] = useState("");

  // Toast feedback
  const [toastMessage, setToastMessage] = useState<{
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

  const handleCheckUpdates = useCallback(async () => {
    setIsCheckingUpdates(true);
    try {
      const status = await ApiService.getUpdateStatus();
      setUpdateStatus(status);
    } catch (err: unknown) {
      setToastMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to check installer/update status",
      });
    } finally {
      setIsCheckingUpdates(false);
    }
  }, []);

  const handleBrowseInstaller = async () => {
    try {
      if (typeof window !== "undefined" && "__TAURI_INTERNALS__" in window) {
        const { open } = await import("@tauri-apps/plugin-dialog");
        const selected = await open({
          multiple: false,
          filters: [{ name: "Windows Installers", extensions: ["exe", "msi"] }],
        });
        if (typeof selected === "string" && selected) {
          setCustomInstallerPath(selected);
        }
      }
    } catch (err: unknown) {
      setToastMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Could not open file picker",
      });
    }
  };

  const handleApplyInstallerUpdate = async (installerPath?: string) => {
    setIsApplyingUpdate(true);
    try {
      const res = await ApiService.applyInstallerUpdate(installerPath);
      setToastMessage({ type: "success", text: res.message });
    } catch (err: unknown) {
      setToastMessage({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to launch installer",
      });
    } finally {
      setIsApplyingUpdate(false);
    }
  };

  useEffect(() => {
    if (activeTab === "about" && !updateStatus) {
      handleCheckUpdates();
    }
  }, [activeTab, updateStatus, handleCheckUpdates]);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const data = await ApiService.getAllSettings();
      setSettings(data);
      setEditedGeneral(data.general);
      setEditedAI(data.ai);
      setEditedOrg(data.organization);
      setEditedMon(data.monitoring);
      setEditedSec(data.security);

      // Load models from 9Router using URL & Bearer Token
      const modelsData = await ApiService.getAvailableModels().catch(() => ({ models: [] }));
      if (modelsData.models && modelsData.models.length > 0) {
        setModelList(modelsData.models);
        setAvailableModels(modelsData.models.map((m) => m.id));
        const activeIds =
          data.ai.enabled_models && data.ai.enabled_models.length > 0
            ? data.ai.enabled_models
            : [data.ai.default_model, data.ai.analysis_model].filter(Boolean);
        setSelectedModelIds(activeIds);
      } else {
        const configured = [data.ai.default_model, data.ai.analysis_model].filter(Boolean);
        setAvailableModels(configured);
        setSelectedModelIds(
          data.ai.enabled_models && data.ai.enabled_models.length > 0
            ? data.ai.enabled_models
            : configured
        );
      }
    } catch (err: unknown) {
      console.error("Failed to load settings", err);
      setToastMessage({ type: "error", text: "Failed to load application settings" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Compute dirty unsaved status
  const hasUnsavedChanges = useMemo(() => {
    if (!settings) return false;
    if (activeTab === "general") {
      return JSON.stringify(editedGeneral) !== JSON.stringify(settings.general);
    }
    if (activeTab === "ai") {
      if (apiKeyInput.trim().length > 0 || openRouterKeyInput.trim().length > 0) return true;
      return JSON.stringify(editedAI) !== JSON.stringify(settings.ai);
    }
    if (activeTab === "organization") {
      return JSON.stringify(editedOrg) !== JSON.stringify(settings.organization);
    }
    if (activeTab === "monitoring") {
      return JSON.stringify(editedMon) !== JSON.stringify(settings.monitoring);
    }
    if (activeTab === "security") {
      return JSON.stringify(editedSec) !== JSON.stringify(settings.security);
    }
    return false;
  }, [activeTab, settings, editedGeneral, editedAI, editedOrg, editedMon, editedSec, apiKeyInput, openRouterKeyInput]);

  // Save current active tab changes
  const handleSaveActiveTab = async () => {
    setSaving(true);
    setToastMessage(null);
    try {
      if (activeTab === "general") {
        await updateGeneralPreferences(editedGeneral);
      } else if (activeTab === "ai") {
        const payload: Record<string, any> = { ...editedAI };
        if (apiKeyInput.trim()) {
          payload.router_api_key = apiKeyInput.trim();
        }
        if (openRouterKeyInput.trim()) {
          payload.openrouter_api_key = openRouterKeyInput.trim();
        }
        await ApiService.updateCategorySettings("ai", payload);
        setApiKeyInput("");
        setOpenRouterKeyInput("");
      } else if (activeTab === "organization") {
        await ApiService.updateCategorySettings("organization", editedOrg);
      } else if (activeTab === "monitoring") {
        await ApiService.updateCategorySettings("monitoring", editedMon);
      } else if (activeTab === "security") {
        await ApiService.updateCategorySettings("security", editedSec);
      }

      const now = new Date().toLocaleTimeString();
      setLastSavedTime(now);
      setToastMessage({
        type: "success",
        text: `Settings for '${activeTab.toUpperCase()}' saved successfully at ${now}!`,
      });
      loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save settings";
      setToastMessage({ type: "error", text: msg });
    } finally {
      setSaving(false);
    }
  };

  // Reset category
  const handleResetCategory = async () => {
    if (
      !window.confirm(
        `Reset '${activeTab.toUpperCase()}' settings to factory default values?\nThis cannot be undone.`
      )
    ) {
      return;
    }

    try {
      await ApiService.resetCategorySettings(activeTab);
      setToastMessage({
        type: "success",
        text: `Category '${activeTab}' reset to defaults.`,
      });
      loadAll();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Reset failed";
      setToastMessage({ type: "error", text: msg });
    }
  };

  // Test 9Router
  const handleTest9Router = async () => {
    setIsTesting9Router(true);
    setRouterTestResult(null);
    try {
      const res = await ApiService.test9RouterConnection(
        editedAI.router_endpoint,
        apiKeyInput.trim() || undefined
      );
      setRouterTestResult(res);
      if (res.success) {
        fetchModels(editedAI.router_endpoint);
      }
    } catch (err: unknown) {
      setRouterTestResult({
        success: false,
        status: "error",
        message: err instanceof Error ? err.message : "Connection failed",
      });
    } finally {
      setIsTesting9Router(false);
    }
  };

  // Clear 9Router API Key
  const handleClearApiKey = async () => {
    if (!window.confirm("Remove stored 9Router API key from Windows Credential Manager?")) return;
    try {
      await ApiService.updateCategorySettings("ai", { clear_router_api_key: true });
      setToastMessage({
        type: "success",
        text: "API key removed from Windows Credential Manager",
      });
      loadAll();
    } catch (err: unknown) {
      setToastMessage({ type: "error", text: "Failed to remove key" });
    }
  };

  // Test OpenRouter
  const handleTestOpenRouter = async () => {
    setIsTestingOpenRouter(true);
    setOpenRouterTestResult(null);
    try {
      const res = await ApiService.testOpenRouterConnection(
        editedAI.openrouter_endpoint,
        openRouterKeyInput.trim() || undefined
      );
      setOpenRouterTestResult(res);
    } catch (err: unknown) {
      setOpenRouterTestResult({
        success: false,
        status: "error",
        message: err instanceof Error ? err.message : "Connection failed",
      });
    } finally {
      setIsTestingOpenRouter(false);
    }
  };

  // Clear OpenRouter API Key
  const handleClearOpenRouterKey = async () => {
    if (!window.confirm("Remove stored OpenRouter API key from Windows Credential Manager?")) return;
    try {
      await ApiService.updateCategorySettings("ai", { clear_openrouter_api_key: true });
      setToastMessage({
        type: "success",
        text: "OpenRouter API key removed from Windows Credential Manager",
      });
      loadAll();
    } catch (err: unknown) {
      setToastMessage({ type: "error", text: "Failed to remove OpenRouter key" });
    }
  };

  // Fetch dynamic models from 9Router via URL and Bearer token
  const fetchModels = async (endpoint?: string) => {
    setIsLoadingModels(true);
    try {
      const res = await ApiService.getAvailableModels(endpoint);
      if (res.models && res.models.length > 0) {
        setModelList(res.models);
        setAvailableModels(res.models.map((m) => m.id));
        setSelectedModelIds((prev) => {
          if (prev.length > 0) return prev;
          const initial = [editedAI.default_model, editedAI.analysis_model].filter(Boolean);
          return initial.length > 0 ? initial : [res.models[0].id];
        });
        setToastMessage({
          type: "success",
          text: `Fetched ${res.models.length} models from 9Router (${res.source || "remote"})!`,
        });
      }
    } catch (err: unknown) {
      console.error("Failed to fetch models", err);
      setToastMessage({
        type: "error",
        text: "Could not fetch dynamic models from 9Router.",
      });
    } finally {
      setIsLoadingModels(false);
    }
  };

  // Toggle model checkbox
  const handleToggleModel = (modelId: string) => {
    setSelectedModelIds((prev) => {
      if (prev.includes(modelId)) {
        const next = prev.filter((id) => id !== modelId);
        if (editedAI.default_model === modelId && next.length > 0) {
          setEditedAI((a) => ({ ...a, default_model: next[0] }));
        }
        return next;
      } else {
        const next = [...prev, modelId];
        if (!editedAI.default_model) {
          setEditedAI((a) => ({ ...a, default_model: modelId }));
        }
        return next;
      }
    });
  };

  // Set default model
  const handleSetDefaultModel = (modelId: string) => {
    if (!selectedModelIds.includes(modelId)) {
      setSelectedModelIds((prev) => [...prev, modelId]);
    }
    setEditedAI((prev) => ({ ...prev, default_model: modelId }));
  };

  // Save selected models
  const handleSaveModelSelection = async () => {
    setIsSavingModels(true);
    setModelSaveSuccess(false);
    try {
      const activeIds =
        selectedModelIds.length > 0
          ? selectedModelIds
          : [editedAI.default_model || "gpt-4o-mini"];
      const primaryDefault =
        editedAI.default_model && activeIds.includes(editedAI.default_model)
          ? editedAI.default_model
          : activeIds[0];
      const primaryAnalysis =
        editedAI.analysis_model && activeIds.includes(editedAI.analysis_model)
          ? editedAI.analysis_model
          : primaryDefault;

      const payload: Record<string, any> = {
        ...editedAI,
        enabled_models: activeIds,
        default_model: primaryDefault,
        analysis_model: primaryAnalysis,
      };

      await ApiService.updateCategorySettings("ai", payload);
      setEditedAI((prev) => ({
        ...prev,
        enabled_models: activeIds,
        default_model: primaryDefault,
        analysis_model: primaryAnalysis,
      }));
      setModelSaveSuccess(true);
      setToastMessage({
        type: "success",
        text: `Model selection saved (${activeIds.length} models active, Default: ${primaryDefault})!`,
      });
      setTimeout(() => setModelSaveSuccess(false), 4000);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save models";
      setToastMessage({ type: "error", text: msg });
    } finally {
      setIsSavingModels(false);
    }
  };

  // Database maintenance actions
  const handleIntegrityCheck = async () => {
    setIsPerformingMaintenance(true);
    try {
      const res = await ApiService.checkDatabaseIntegrity();
      setMaintenanceOutput(res);
    } catch (err: unknown) {
      setMaintenanceOutput({
        success: false,
        action: "integrity_check",
        message: String(err),
        details: {},
      });
    } finally {
      setIsPerformingMaintenance(false);
    }
  };

  const handleCompactDatabase = async () => {
    if (!window.confirm("Run VACUUM to compact SQLite database? This may take a few seconds.")) {
      return;
    }
    setIsPerformingMaintenance(true);
    try {
      const res = await ApiService.compactDatabase();
      setMaintenanceOutput(res);
      loadAll();
    } catch (err: unknown) {
      setMaintenanceOutput({
        success: false,
        action: "compact_database",
        message: String(err),
        details: {},
      });
    } finally {
      setIsPerformingMaintenance(false);
    }
  };

  const handleClearCache = async () => {
    setIsPerformingMaintenance(true);
    try {
      const res = await ApiService.clearCache();
      setMaintenanceOutput(res);
    } catch (err: unknown) {
      setMaintenanceOutput({
        success: false,
        action: "clear_cache",
        message: String(err),
        details: {},
      });
    } finally {
      setIsPerformingMaintenance(false);
    }
  };

  if (loading && !settings) {
    return (
      <div className="p-12 text-center text-muted-foreground text-xs space-y-2">
        <Settings size={28} className="mx-auto animate-spin opacity-40" />
        <p>Loading application settings...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-12">
      {/* Page Header */}
      <PageHeader
        title="Settings"
        description="Configure FileNest, manage AI integrations, security policies, and system preferences."
      >
        <div className="flex items-center gap-2">
          {activeTab !== "about" && (
            <>
              <button
                type="button"
                onClick={handleResetCategory}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors"
              >
                <RotateCcw size={13} />
                <span>Reset Defaults</span>
              </button>
              <button
                type="button"
                onClick={handleSaveActiveTab}
                disabled={saving || !hasUnsavedChanges}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-md text-xs font-medium bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50"
              >
                <Save size={13} />
                <span>{saving ? "Saving..." : "Save Changes"}</span>
              </button>
            </>
          )}
        </div>
      </PageHeader>

      {/* Toast */}
      {toastMessage && (
        <div
          className={cn(
            "p-3 rounded-lg border text-xs flex items-center justify-between",
            toastMessage.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-600"
              : "bg-rose-500/10 border-rose-500/30 text-rose-600"
          )}
        >
          <div className="flex items-center gap-2">
            {toastMessage.type === "success" ? <CheckCircle2 size={15} /> : <CircleX size={15} />}
            <span className="font-medium">{toastMessage.text}</span>
          </div>
          <button
            type="button"
            onClick={() => setToastMessage(null)}
            className="text-muted-foreground hover:text-foreground"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {/* Tier 1: Top Horizontal Category Tabs */}
      <div className="flex items-center gap-1.5 border-b border-border overflow-x-auto pb-2 scrollbar-thin">
        {CATEGORIES.map((cat) => {
          const Icon = cat.icon;
          const isActive = activeTab === cat.id;
          return (
            <button
              key={cat.id}
              type="button"
              onClick={() => {
                setActiveTab(cat.id);
                setActiveSubmenu("all");
                setToastMessage(null);
              }}
              className={cn(
                "inline-flex items-center gap-2 px-3.5 py-2 rounded-lg text-xs font-medium transition-all whitespace-nowrap",
                isActive
                  ? "bg-primary text-primary-foreground font-semibold shadow-xs"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/70"
              )}
            >
              <Icon size={15} />
              <span>{cat.label}</span>
            </button>
          );
        })}
      </div>

      {/* Main 3-Tier Layout: Tier 2 (Left Submenus) + Center Content + Tier 3 (Right Telemetry) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Tier 2: Left Submenu Navigation (col-span-2) */}
        <div className="lg:col-span-2 space-y-1">
          <div className="text-[10px] uppercase font-bold tracking-wider text-muted-foreground px-2.5 mb-1.5">
            {CATEGORIES.find((c) => c.id === activeTab)?.label}
          </div>
          {(SUBMENU_MAP[activeTab] || []).map((sub) => {
            const isSubActive = activeSubmenu === sub.id;
            return (
              <button
                key={sub.id}
                type="button"
                onClick={() => setActiveSubmenu(sub.id)}
                className={cn(
                  "w-full flex items-center justify-between px-3 py-2 rounded-md text-xs font-medium transition-colors text-left",
                  isSubActive
                    ? "bg-secondary text-secondary-foreground font-semibold border border-border shadow-2xs"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                )}
              >
                <span>{sub.label}</span>
                {isSubActive && <div className="w-1.5 h-1.5 rounded-full bg-primary" />}
              </button>
            );
          })}
        </div>

        {/* Center Content Panel (col-span-7) */}
        <div className="lg:col-span-7 space-y-5">
          {/* 1. General Settings */}
          {activeTab === "general" && (
            <div className="space-y-5">
              {/* Startup & Background */}
              {(activeSubmenu === "all" || activeSubmenu === "startup") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Startup & Background Behavior</h3>
                    <p className="text-xs text-muted-foreground">
                      Configure how FileNest behaves on system launch and window close.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <label className="flex items-center gap-2 p-2.5 rounded-md border border-border bg-background cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.start_on_startup ?? false}
                        onChange={(e) =>
                          setEditedGeneral({ ...editedGeneral, start_on_startup: e.target.checked })
                        }
                        className="rounded border-border text-primary"
                      />
                      <div>
                        <div className="font-medium text-foreground">Start on Windows Launch</div>
                        <div className="text-[10px] text-muted-foreground">Launch on OS logon</div>
                      </div>
                    </label>

                    <label className="flex items-center gap-2 p-2.5 rounded-md border border-border bg-background cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.run_in_background ?? true}
                        onChange={(e) =>
                          setEditedGeneral({ ...editedGeneral, run_in_background: e.target.checked })
                        }
                        className="rounded border-border text-primary"
                      />
                      <div>
                        <div className="font-medium text-foreground">Run in Background</div>
                        <div className="text-[10px] text-muted-foreground">Stay active when closed</div>
                      </div>
                    </label>

                    <label className="flex items-center gap-2 p-2.5 rounded-md border border-border bg-background cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.minimize_to_tray ?? true}
                        onChange={(e) =>
                          setEditedGeneral({ ...editedGeneral, minimize_to_tray: e.target.checked })
                        }
                        className="rounded border-border text-primary"
                      />
                      <div>
                        <div className="font-medium text-foreground">Minimize to System Tray</div>
                        <div className="text-[10px] text-muted-foreground">Dock to Windows task tray</div>
                      </div>
                    </label>

                    <label className="flex items-center gap-2 p-2.5 rounded-md border border-border bg-background cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.start_monitoring_on_launch ?? true}
                        onChange={(e) =>
                          setEditedGeneral({
                            ...editedGeneral,
                            start_monitoring_on_launch: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <div>
                        <div className="font-medium text-foreground">Auto-Start Watchers</div>
                        <div className="text-[10px] text-muted-foreground">Resume active watchers</div>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {/* User Interface */}
              {(activeSubmenu === "all" || activeSubmenu === "ui") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">User Interface Preferences</h3>
                    <p className="text-xs text-muted-foreground">
                      Personalize color themes, table layout density, and file manager display.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Color Theme</label>
                      <select
                        value={editedGeneral.theme || "system"}
                        onChange={(e) => {
                          const val = e.target.value as "system" | "light" | "dark";
                          setTheme(val);
                          setEditedGeneral({ ...editedGeneral, theme: val });
                        }}
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
                      >
                        <option value="system">System Default</option>
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Table Density</label>
                      <select
                        value={editedGeneral.default_table_density || "comfortable"}
                        onChange={(e) => {
                          const val = e.target.value as "comfortable" | "compact";
                          setDefaultTableDensity(val);
                          setEditedGeneral({
                            ...editedGeneral,
                            default_table_density: val,
                          });
                        }}
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
                      >
                        <option value="comfortable">Comfortable</option>
                        <option value="compact">Compact</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Default File View</label>
                      <select
                        value={editedGeneral.default_file_view || "list"}
                        onChange={(e) => {
                          const val = e.target.value as "list" | "grid";
                          setDefaultFileView(val);
                          setEditedGeneral({ ...editedGeneral, default_file_view: val });
                        }}
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
                      >
                        <option value="list">List View</option>
                        <option value="grid">Grid View</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs pt-1">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.show_file_extensions ?? true}
                        onChange={(e) => {
                          setShowFileExtensions(e.target.checked);
                          setEditedGeneral({
                            ...editedGeneral,
                            show_file_extensions: e.target.checked,
                          });
                        }}
                        className="rounded border-border text-primary"
                      />
                      <span>Display file extensions in tables</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.show_hidden_files ?? false}
                        onChange={(e) => {
                          setShowHiddenFiles(e.target.checked);
                          setEditedGeneral({
                            ...editedGeneral,
                            show_hidden_files: e.target.checked,
                          });
                        }}
                        className="rounded border-border text-primary"
                      />
                      <span>Show hidden files and dotfiles</span>
                    </label>
                  </div>
                </div>
              )}

              {/* Notifications */}
              {(activeSubmenu === "all" || activeSubmenu === "notifications") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Windows Notifications</h3>
                    <p className="text-xs text-muted-foreground">
                      Configure desktop toast notifications for jobs and file operations.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.desktop_notifications ?? true}
                        onChange={(e) =>
                          setEditedGeneral({
                            ...editedGeneral,
                            desktop_notifications: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Show Windows desktop notifications</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedGeneral.job_notifications ?? true}
                        onChange={(e) =>
                          setEditedGeneral({
                            ...editedGeneral,
                            job_notifications: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Notify on completed background operations</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 2. Analysis & AI Settings */}
          {activeTab === "ai" && (
            <div className="space-y-5">
              {/* Architecture Alert */}
              <div className="p-3.5 rounded-md border border-primary/20 bg-primary/5 flex items-start gap-2.5 text-xs">
                <Sparkles size={16} className="text-primary shrink-0 mt-0.5" />
                <div>
                  <span className="font-semibold text-foreground">
                    AI Safety Architecture:
                  </span>{" "}
                  <span className="text-muted-foreground">
                    AI models provide classification, clustering, contextual assistance, and structured rename plans.
                    Direct file mutations are strictly prohibited for AI — execution passes through
                    the backend Transaction Manager.
                  </span>
                </div>
              </div>

              {/* Gateway & Credentials */}
              {(activeSubmenu === "all" || activeSubmenu === "gateway") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-semibold text-sm">9Router Model Gateway & Credentials</h3>
                      <p className="text-xs text-muted-foreground">
                        Configure gateway endpoint URL and Windows Credential Manager integration.
                      </p>
                    </div>
                    {routerTestResult && (
                      <span
                        className={cn(
                          "text-[10px] font-semibold px-2 py-0.5 rounded",
                          routerTestResult.success
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-rose-500/10 text-rose-600"
                        )}
                      >
                        {routerTestResult.status.toUpperCase()} (
                        {routerTestResult.latency_ms}ms)
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">9Router Endpoint</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editedAI.router_endpoint || ""}
                          onChange={(e) =>
                            setEditedAI({ ...editedAI, router_endpoint: e.target.value })
                          }
                          placeholder="http://127.0.0.1:20128/v1"
                          className="flex-1 px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs"
                        />
                        <button
                          type="button"
                          onClick={handleTest9Router}
                          disabled={isTesting9Router}
                          className="px-2.5 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-medium"
                        >
                          {isTesting9Router ? "Testing..." : "Test"}
                        </button>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="font-medium text-foreground">API Key (Secure Vault)</label>
                        {settings?.ai.has_router_api_key && (
                          <span className="text-[10px] text-emerald-600 font-medium">
                            Configured ({settings.ai.masked_router_api_key})
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="relative flex-1">
                          <input
                            type={showApiKey ? "text" : "password"}
                            value={apiKeyInput}
                            onChange={(e) => setApiKeyInput(e.target.value)}
                            placeholder={
                              settings?.ai.has_router_api_key
                                ? "Key stored securely. Enter new to update."
                                : "Enter API key..."
                            }
                            className="w-full px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs pr-8"
                          />
                          <button
                            type="button"
                            onClick={() => setShowApiKey(!showApiKey)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                        {settings?.ai.has_router_api_key && (
                          <button
                            type="button"
                            onClick={handleClearApiKey}
                            title="Remove stored key"
                            className="p-1.5 rounded-md text-rose-600 hover:bg-rose-500/10 border border-rose-500/30"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 pt-1">
                    <ShieldCheck size={13} className="text-emerald-500" />
                    <span>
                      Secrets are stored in Windows Credential Manager and never written to SQLite.
                    </span>
                  </div>
                </div>
              )}

              {/* OpenRouter Automatic Fallback Configuration */}
              {(activeSubmenu === "all" || activeSubmenu === "gateway") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="p-1.5 rounded-md bg-secondary text-secondary-foreground border border-border">
                        <ArrowRightLeft size={16} />
                      </div>
                      <div>
                        <h3 className="font-semibold text-sm">OpenRouter Automatic Fallback</h3>
                        <p className="text-xs text-muted-foreground">
                          Otomatis beralih ke OpenRouter saat koneksi 9Router utama tidak dapat diakses atau offline.
                        </p>
                      </div>
                    </div>
                    {openRouterTestResult && (
                      <span
                        className={cn(
                          "text-[10px] font-semibold px-2 py-0.5 rounded",
                          openRouterTestResult.success
                            ? "bg-emerald-500/10 text-emerald-600"
                            : "bg-rose-500/10 text-rose-600"
                        )}
                      >
                        {openRouterTestResult.status.toUpperCase()} (
                        {openRouterTestResult.latency_ms}ms)
                      </span>
                    )}
                  </div>

                  <div className="flex items-center justify-between p-3 rounded-md bg-secondary/50 border border-border/60">
                    <div>
                      <div className="text-xs font-medium text-foreground">Aktifkan Auto-Fallback ke OpenRouter</div>
                      <div className="text-[11px] text-muted-foreground">
                        Jika 9Router mengalami kendala / HTTP 5xx / timeout, permintaan AI otomatis diteruskan ke OpenRouter tanpa interupsi.
                      </div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedAI.auto_fallback_enabled ?? true}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, auto_fallback_enabled: e.target.checked })
                        }
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-muted peer-focus:outline-hidden rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">OpenRouter Endpoint</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editedAI.openrouter_endpoint || "https://openrouter.ai/api/v1"}
                          onChange={(e) =>
                            setEditedAI({ ...editedAI, openrouter_endpoint: e.target.value })
                          }
                          placeholder="https://openrouter.ai/api/v1"
                          className="flex-1 px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs"
                        />
                        <button
                          type="button"
                          onClick={handleTestOpenRouter}
                          disabled={isTestingOpenRouter}
                          className="px-2.5 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 font-medium"
                        >
                          {isTestingOpenRouter ? "Testing..." : "Test"}
                        </button>
                      </div>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Fallback Model</label>
                      <input
                        type="text"
                        value={editedAI.openrouter_model || "google/gemini-2.5-flash"}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, openrouter_model: e.target.value })
                        }
                        placeholder="google/gemini-2.5-flash"
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs"
                      />
                    </div>

                    <div className="space-y-1">
                      <div className="flex items-center justify-between">
                        <label className="font-medium text-foreground">OpenRouter API Key</label>
                        {settings?.ai.has_openrouter_api_key && (
                          <span className="text-[10px] text-emerald-600 font-medium">
                            Configured ({settings.ai.masked_openrouter_api_key})
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="relative flex-1">
                          <input
                            type={showOpenRouterKey ? "text" : "password"}
                            value={openRouterKeyInput}
                            onChange={(e) => setOpenRouterKeyInput(e.target.value)}
                            placeholder={
                              settings?.ai.has_openrouter_api_key
                                ? "Key stored securely. Enter new to update."
                                : "Enter OpenRouter API Key..."
                            }
                            className="w-full px-3 py-1.5 rounded-md border border-border bg-background font-mono text-xs pr-8"
                          />
                          <button
                            type="button"
                            onClick={() => setShowOpenRouterKey(!showOpenRouterKey)}
                            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                          >
                            {showOpenRouterKey ? <EyeOff size={14} /> : <Eye size={14} />}
                          </button>
                        </div>
                        {settings?.ai.has_openrouter_api_key && (
                          <button
                            type="button"
                            onClick={handleClearOpenRouterKey}
                            title="Remove stored OpenRouter key"
                            className="p-1.5 rounded-md text-rose-600 hover:bg-rose-500/10 border border-rose-500/30"
                          >
                            <Trash2 size={13} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="text-[11px] text-muted-foreground flex items-center gap-1.5 pt-1">
                    <ShieldCheck size={13} className="text-emerald-500" />
                    <span>
                      API Key OpenRouter disimpan aman di Windows Credential Manager.
                    </span>
                  </div>
                </div>
              )}

              {/* Model Selection via List and Checkbox */}
              {(activeSubmenu === "all" || activeSubmenu === "models") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div>
                      <h3 className="font-semibold text-sm">Model Selection (List & Checkbox)</h3>
                      <p className="text-xs text-muted-foreground">
                        Select and enable models discovered from 9Router Gateway.
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => fetchModels(editedAI.router_endpoint)}
                        disabled={isLoadingModels}
                        className="px-2.5 py-1.5 rounded-md border border-border bg-secondary hover:bg-secondary/80 text-xs font-medium flex items-center gap-1.5"
                        title="Ambil ulang model dari 9Router"
                      >
                        <RefreshCw size={13} className={isLoadingModels ? "animate-spin text-primary" : ""} />
                        {isLoadingModels ? "Fetching..." : "Refresh Models"}
                      </button>
                      {modelList.length > 0 && (
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-primary/10 text-primary">
                          {modelList.length} Models
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Search & Filter Toolbar */}
                  <div className="flex flex-col sm:flex-row gap-2 pt-1">
                    <div className="relative flex-1">
                      <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground" />
                      <input
                        type="text"
                        placeholder="Search models (e.g. claude, gpt-4o, llama, deepseek, gemini)..."
                        value={modelSearchQuery}
                        onChange={(e) => setModelSearchQuery(e.target.value)}
                        className="w-full pl-8 pr-7 py-1.5 rounded-md border border-border bg-background text-xs font-mono"
                      />
                      {modelSearchQuery && (
                        <button
                          type="button"
                          onClick={() => setModelSearchQuery("")}
                          className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                        >
                          <X size={13} />
                        </button>
                      )}
                    </div>

                    {/* Filter Pills */}
                    <div className="flex items-center gap-1 bg-secondary/50 p-0.5 rounded-md border border-border text-[11px]">
                      <button
                        type="button"
                        onClick={() => setModelFilterTab("all")}
                        className={cn(
                          "px-2.5 py-1 rounded font-medium transition-colors",
                          modelFilterTab === "all"
                            ? "bg-background text-foreground shadow-xs"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        Semua ({modelList.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setModelFilterTab("selected")}
                        className={cn(
                          "px-2.5 py-1 rounded font-medium transition-colors",
                          modelFilterTab === "selected"
                            ? "bg-background text-foreground shadow-xs"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        Dipilih ({selectedModelIds.length})
                      </button>
                      <button
                        type="button"
                        onClick={() => setModelFilterTab("vision")}
                        className={cn(
                          "px-2.5 py-1 rounded font-medium transition-colors",
                          modelFilterTab === "vision"
                            ? "bg-background text-foreground shadow-xs"
                            : "text-muted-foreground hover:text-foreground"
                        )}
                      >
                        Vision ({modelList.filter((m) => m.supports_vision).length})
                      </button>
                    </div>
                  </div>

                  {/* Quick actions row */}
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground px-1">
                    <span>
                      Menampilkan <strong className="text-foreground">{
                        modelList.filter((m) => {
                          const matchesSearch =
                            modelSearchQuery.trim() === "" ||
                            m.id.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                            m.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                            m.provider.toLowerCase().includes(modelSearchQuery.toLowerCase());
                          if (!matchesSearch) return false;
                          if (modelFilterTab === "selected") return selectedModelIds.includes(m.id);
                          if (modelFilterTab === "vision") return m.supports_vision;
                          return true;
                        }).length
                      }</strong> model:
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          const filtered = modelList.filter((m) => {
                            const matchesSearch =
                              modelSearchQuery.trim() === "" ||
                              m.id.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                              m.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                              m.provider.toLowerCase().includes(modelSearchQuery.toLowerCase());
                            if (!matchesSearch) return false;
                            if (modelFilterTab === "selected") return selectedModelIds.includes(m.id);
                            if (modelFilterTab === "vision") return m.supports_vision;
                            return true;
                          });
                          const newIds = Array.from(new Set([...selectedModelIds, ...filtered.map((m) => m.id)]));
                          setSelectedModelIds(newIds);
                        }}
                        className="hover:underline text-primary"
                      >
                        Pilih Semua Hasil
                      </button>
                      <span>•</span>
                      <button
                        type="button"
                        onClick={() => setSelectedModelIds([])}
                        className="hover:underline text-rose-500"
                      >
                        Hapus Pilihan
                      </button>
                    </div>
                  </div>

                  {/* Model Checkbox List Container */}
                  <div className="max-h-64 overflow-y-auto rounded-md border border-border bg-background/50 divide-y divide-border/60">
                    {(() => {
                      const filtered = modelList.filter((m) => {
                        const matchesSearch =
                          modelSearchQuery.trim() === "" ||
                          m.id.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                          m.name.toLowerCase().includes(modelSearchQuery.toLowerCase()) ||
                          m.provider.toLowerCase().includes(modelSearchQuery.toLowerCase());
                        if (!matchesSearch) return false;
                        if (modelFilterTab === "selected") return selectedModelIds.includes(m.id);
                        if (modelFilterTab === "vision") return m.supports_vision;
                        return true;
                      });

                      if (filtered.length === 0) {
                        return (
                          <div className="p-6 text-center text-xs text-muted-foreground">
                            {modelList.length === 0 ? (
                              <div className="space-y-2">
                                <p>Belum ada model yang dimuat dari 9Router.</p>
                                <button
                                  type="button"
                                  onClick={() => fetchModels(editedAI.router_endpoint)}
                                  className="px-3 py-1.5 rounded border border-border bg-secondary hover:bg-secondary/80 font-medium inline-flex items-center gap-1.5"
                                >
                                  <RefreshCw size={12} /> Ambil Model dari 9Router
                                </button>
                              </div>
                            ) : (
                              <p>Tidak ada model yang cocok dengan pencarian "{modelSearchQuery}".</p>
                            )}
                          </div>
                        );
                      }

                      return filtered.map((m) => {
                        const isSelected = selectedModelIds.includes(m.id);
                        const isDefault = editedAI.default_model === m.id;

                        return (
                          <div
                            key={m.id}
                            className={cn(
                              "px-3 py-2 flex items-center justify-between gap-3 text-xs transition-colors hover:bg-muted/40",
                              isSelected && "bg-primary/5"
                            )}
                          >
                            <label className="flex items-center gap-2.5 min-w-0 cursor-pointer flex-1">
                              <input
                                type="checkbox"
                                checked={isSelected}
                                onChange={() => handleToggleModel(m.id)}
                                className="rounded border-border text-primary shrink-0 focus:ring-primary h-4 w-4"
                              />
                              <div className="min-w-0 flex-1">
                                <div className="flex items-center gap-2 flex-wrap">
                                  <span className={cn(
                                    "font-mono text-xs truncate",
                                    isSelected ? "font-semibold text-foreground" : "text-muted-foreground"
                                  )}>
                                    {m.id}
                                  </span>
                                  {m.provider && (
                                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-secondary text-secondary-foreground">
                                      {m.provider}
                                    </span>
                                  )}
                                  {m.supports_vision && (
                                    <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-500/10 text-sky-600 font-medium">
                                      Vision
                                    </span>
                                  )}
                                  {m.context_length > 0 && (
                                    <span className="text-[10px] text-muted-foreground">
                                      {Math.round(m.context_length / 1000)}k ctx
                                    </span>
                                  )}
                                </div>
                              </div>
                            </label>

                            <div className="shrink-0 flex items-center gap-2">
                              {isDefault ? (
                                <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-primary/10 text-primary flex items-center gap-1 border border-primary/20">
                                  <CheckCircle2 size={12} /> Default Model
                                </span>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleSetDefaultModel(m.id)}
                                  className="text-[10px] text-muted-foreground hover:text-foreground px-2 py-0.5 rounded border border-border hover:border-primary/40 transition-colors"
                                  title="Jadikan sebagai Default Model"
                                >
                                  Set Default
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      });
                    })()}
                  </div>

                  {/* Save Selected Models Footer Button */}
                  <div className="p-3 rounded-md bg-secondary/30 border border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                    <div className="text-xs">
                      <span className="text-muted-foreground">Model Terpilih: </span>
                      <strong className="text-foreground">{selectedModelIds.length} model</strong>
                      {editedAI.default_model && (
                        <span className="text-muted-foreground">
                          {" "}• Default: <code className="font-mono text-foreground font-semibold px-1.5 py-0.5 bg-background rounded border border-border">{editedAI.default_model}</code>
                        </span>
                      )}
                      {modelSaveSuccess && (
                        <span className="ml-2 text-emerald-600 font-semibold inline-flex items-center gap-1">
                          <CheckCircle2 size={13} /> Tersimpan!
                        </span>
                      )}
                    </div>

                    <button
                      type="button"
                      onClick={handleSaveModelSelection}
                      disabled={isSavingModels}
                      className="px-3.5 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-semibold flex items-center justify-center gap-1.5 shadow-xs transition-colors shrink-0"
                    >
                      <Save size={13} />
                      {isSavingModels ? "Menyimpan Model..." : `Simpan Model (${selectedModelIds.length})`}
                    </button>
                  </div>
                </div>
              )}

              {/* Parameters & Tuning */}
              {(activeSubmenu === "all" || activeSubmenu === "parameters") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Model Parameters & Execution</h3>
                    <p className="text-xs text-muted-foreground">
                      Configure secondary models, token generation caps, and temperature sampling.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Analysis Model</label>
                      <select
                        value={editedAI.analysis_model || editedAI.default_model || "gpt-4o"}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, analysis_model: e.target.value })
                        }
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background font-mono"
                      >
                        {(selectedModelIds.length > 0 ? selectedModelIds : availableModels).length === 0 ? (
                          <option value={editedAI.analysis_model || editedAI.default_model || ""}>
                            {editedAI.analysis_model || editedAI.default_model || "No model configured"}
                          </option>
                        ) : (
                          (selectedModelIds.length > 0 ? selectedModelIds : availableModels).map((m) => (
                            <option key={m} value={m}>
                              {m}
                            </option>
                          ))
                        )}
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Max Tokens</label>
                      <input
                        type="number"
                        value={editedAI.max_tokens || 4096}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, max_tokens: parseInt(e.target.value, 10) })
                        }
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Temperature ({editedAI.temperature ?? 0.2})</label>
                      <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.05"
                        value={editedAI.temperature ?? 0.2}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, temperature: parseFloat(e.target.value) })
                        }
                        className="w-full"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Privacy Controls */}
              {(activeSubmenu === "all" || activeSubmenu === "privacy") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Privacy & Data Sharing</h3>
                    <p className="text-xs text-muted-foreground">
                      Control remote gateway transmission and limit analysis strictly to metadata.
                    </p>
                  </div>
                  <div className="space-y-2 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedAI.allow_remote_ai_processing ?? false}
                        onChange={(e) =>
                          setEditedAI({
                            ...editedAI,
                            allow_remote_ai_processing: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>
                        Allow remote AI processing through 9Router (disabled by default for privacy)
                      </span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedAI.metadata_only ?? true}
                        onChange={(e) =>
                          setEditedAI({ ...editedAI, metadata_only: e.target.checked })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Restrict AI processing to file names and metadata only</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 3. Organization Settings */}
          {activeTab === "organization" && (
            <div className="space-y-5">
              {(activeSubmenu === "all" || activeSubmenu === "structure") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Folder Structure & Naming</h3>
                    <p className="text-xs text-muted-foreground">
                      Define organizational strategies, folder casing formats, and archive buckets.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Default Strategy</label>
                      <select
                        value={editedOrg.default_strategy || "file_type"}
                        onChange={(e) =>
                          setEditedOrg({ ...editedOrg, default_strategy: e.target.value })
                        }
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
                      >
                        <option value="file_type">By File Type (Documents, Images...)</option>
                        <option value="project_structure">By Project Structure</option>
                        <option value="custom">Custom Hierarchy</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Naming Convention</label>
                      <select
                        value={editedOrg.default_folder_naming || "kebab-case"}
                        onChange={(e) =>
                          setEditedOrg({ ...editedOrg, default_folder_naming: e.target.value })
                        }
                        className="w-full px-2.5 py-1.5 rounded-md border border-border bg-background"
                      >
                        <option value="kebab-case">kebab-case</option>
                        <option value="snake_case">snake_case</option>
                        <option value="PascalCase">PascalCase</option>
                        <option value="numbered">Numbered (01_Docs)</option>
                      </select>
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Archive Folder</label>
                      <input
                        type="text"
                        value={editedOrg.default_archive_folder_name || "Archive"}
                        onChange={(e) =>
                          setEditedOrg({
                            ...editedOrg,
                            default_archive_folder_name: e.target.value,
                          })
                        }
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background"
                      />
                    </div>
                  </div>
                </div>
              )}

              {(activeSubmenu === "all" || activeSubmenu === "conflicts") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Destination Conflict Handling</h3>
                    <p className="text-xs text-muted-foreground">
                      Collision mitigation and automatic review requirements for ambiguous renames.
                    </p>
                  </div>
                  <div className="space-y-2 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedOrg.detect_destination_conflicts ?? true}
                        disabled
                        className="rounded border-border text-primary"
                      />
                      <span className="font-medium">
                        Detect Destination Collisions (Mandatory safety rule)
                      </span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedOrg.require_review_for_ambiguous ?? true}
                        onChange={(e) =>
                          setEditedOrg({
                            ...editedOrg,
                            require_review_for_ambiguous: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Send ambiguous conflict items to Review Changes</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 4. Monitoring Settings */}
          {activeTab === "monitoring" && (
            <div className="space-y-5">
              {(activeSubmenu === "all" || activeSubmenu === "processing") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Event Processing Parameters</h3>
                    <p className="text-xs text-muted-foreground">
                      Sliding debounce windows, in-memory queue limits, and batch ingestion sizes.
                    </p>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Debounce Interval (ms)</label>
                      <input
                        type="number"
                        min={100}
                        step={100}
                        value={editedMon.debounce_interval_ms || 1000}
                        onChange={(e) =>
                          setEditedMon({
                            ...editedMon,
                            debounce_interval_ms: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Max Event Queue</label>
                      <input
                        type="number"
                        value={editedMon.max_queue_size || 5000}
                        onChange={(e) =>
                          setEditedMon({
                            ...editedMon,
                            max_queue_size: parseInt(e.target.value, 10),
                          })
                        }
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background"
                      />
                    </div>

                    <div className="space-y-1">
                      <label className="font-medium text-foreground">Batch Size</label>
                      <input
                        type="number"
                        value={editedMon.batch_size || 100}
                        onChange={(e) =>
                          setEditedMon({ ...editedMon, batch_size: parseInt(e.target.value, 10) })
                        }
                        className="w-full px-3 py-1.5 rounded-md border border-border bg-background"
                      />
                    </div>
                  </div>
                </div>
              )}

              {(activeSubmenu === "all" || activeSubmenu === "ignores") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Default Global Ignore Patterns</h3>
                    <p className="text-xs text-muted-foreground">
                      Common temporary files and version control directories automatically filtered across all watchers.
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {(editedMon.global_ignore_patterns || []).map((pat: string) => (
                      <span
                        key={pat}
                        className="px-2 py-0.5 rounded-md font-mono text-[11px] bg-muted border border-border"
                      >
                        {pat}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 5. Security & Access Settings */}
          {activeTab === "security" && (
            <div className="space-y-5">
              {(activeSubmenu === "all" || activeSubmenu === "mandatory") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div className="flex items-center gap-2">
                    <ShieldCheck size={16} className="text-emerald-500" />
                    <div>
                      <h3 className="font-semibold text-sm">Mandatory Safety Constraints (Immutable)</h3>
                      <p className="text-xs text-muted-foreground">
                        Filesystem safety invariants enforced strictly across the application.
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {(settings?.security.mandatory_policies || []).map((p) => (
                      <div
                        key={p.policy_id}
                        className="p-3 rounded-lg border border-emerald-500/20 bg-emerald-500/5 flex items-start justify-between text-xs gap-3"
                      >
                        <div className="space-y-0.5">
                          <div className="font-semibold text-foreground flex items-center gap-1.5">
                            <CheckCircle2 size={13} className="text-emerald-600" />
                            <span>{p.name}</span>
                          </div>
                          <p className="text-muted-foreground text-[11px]">{p.description}</p>
                        </div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/15 text-emerald-600 uppercase shrink-0">
                          Enforced
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(activeSubmenu === "all" || activeSubmenu === "approvals") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Approval & Confirmation Policies</h3>
                    <p className="text-xs text-muted-foreground">
                      Define manual confirmation requirements prior to destructive changes or unregistration.
                    </p>
                  </div>
                  <div className="space-y-2 text-xs">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedSec.require_confirmation_before_execution ?? true}
                        onChange={(e) =>
                          setEditedSec({
                            ...editedSec,
                            require_confirmation_before_execution: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Require explicit user approval before executing any file operation</span>
                    </label>

                    <label className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={editedSec.require_confirmation_before_folder_remove ?? true}
                        onChange={(e) =>
                          setEditedSec({
                            ...editedSec,
                            require_confirmation_before_folder_remove: e.target.checked,
                          })
                        }
                        className="rounded border-border text-primary"
                      />
                      <span>Confirm before unregistering Managed Folders</span>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 6. Storage & Database Settings */}
          {activeTab === "storage" && (
            <div className="space-y-5">
              {(activeSubmenu === "all" || activeSubmenu === "diagnostics") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">SQLite Database Metrics</h3>
                    <p className="text-xs text-muted-foreground">
                      Internal database size, active write-ahead log footprint, and table records.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="p-3 rounded-lg border border-border bg-muted/20">
                      <div className="text-[10px] uppercase font-bold text-muted-foreground">
                        Engine
                      </div>
                      <div className="font-semibold mt-1">SQLite 3 (WAL)</div>
                    </div>

                    <div className="p-3 rounded-lg border border-border bg-muted/20">
                      <div className="text-[10px] uppercase font-bold text-muted-foreground">
                        DB File Size
                      </div>
                      <div className="font-semibold mt-1 font-mono">
                        {formatBytes(settings?.storage.database.size_bytes || 0)}
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-border bg-muted/20">
                      <div className="text-[10px] uppercase font-bold text-muted-foreground">
                        WAL Log Size
                      </div>
                      <div className="font-semibold mt-1 font-mono">
                        {formatBytes(settings?.storage.database.wal_size_bytes || 0)}
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-border bg-muted/20">
                      <div className="text-[10px] uppercase font-bold text-muted-foreground">
                        Tables Count
                      </div>
                      <div className="font-semibold mt-1">
                        {settings?.storage.database.tables_count} Tables
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {(activeSubmenu === "all" || activeSubmenu === "maintenance") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Database & Cache Maintenance</h3>
                    <p className="text-xs text-muted-foreground">
                      Run low-level vacuum compaction, integrity diagnostics, and purge cached assets.
                    </p>
                  </div>
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={handleIntegrityCheck}
                      disabled={isPerformingMaintenance}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                    >
                      <Terminal size={14} />
                      <span>Check Database Integrity</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleCompactDatabase}
                      disabled={isPerformingMaintenance}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                    >
                      <Database size={14} />
                      <span>Compact Database (VACUUM)</span>
                    </button>

                    <button
                      type="button"
                      onClick={handleClearCache}
                      disabled={isPerformingMaintenance}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                    >
                      <Trash2 size={14} />
                      <span>Clear Cache</span>
                    </button>
                  </div>

                  {maintenanceOutput && (
                    <div className="p-4 rounded-lg border border-border bg-muted/30 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground">
                          Result: {maintenanceOutput.action}
                        </span>
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded text-[10px] font-bold uppercase",
                            maintenanceOutput.success
                              ? "bg-emerald-500/10 text-emerald-600"
                              : "bg-rose-500/10 text-rose-600"
                          )}
                        >
                          {maintenanceOutput.success ? "Success" : "Failed"}
                        </span>
                      </div>
                      <p className="font-mono text-muted-foreground">{maintenanceOutput.message}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* 7. About Settings */}
          {activeTab === "about" && (
            <div className="space-y-5">
              {(activeSubmenu === "all" || activeSubmenu === "info") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-primary text-primary-foreground flex items-center justify-center font-bold text-lg shadow-sm">
                      FN
                    </div>
                    <div>
                      <h3 className="font-bold text-base leading-tight">
                        {settings?.about.app_name}
                      </h3>
                      <p className="text-xs text-muted-foreground">
                        Version {settings?.about.version} ({settings?.about.build_number})
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2 pt-2 border-t border-border text-xs text-muted-foreground leading-relaxed">
                    <p>
                      FileNest is a safe Windows desktop application designed to catalog, organize, and
                      automate storage workflows with AI assistance and guaranteed transaction safety.
                    </p>
                    <p>
                      OS: {settings?.about.os_name} {settings?.about.os_version} (
                      {settings?.about.architecture})
                    </p>
                  </div>
                </div>
              )}

              {(activeSubmenu === "all" || activeSubmenu === "stack") && (
                <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                  <div>
                    <h3 className="font-semibold text-sm">Installed Technology Stack</h3>
                    <p className="text-xs text-muted-foreground">
                      Core runtimes and runtime libraries powering FileNest.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                    <div className="p-2.5 rounded border border-border bg-background">
                      <div className="text-[10px] text-muted-foreground uppercase">Shell</div>
                      <div className="font-semibold mt-0.5">Tauri v{settings?.about.tauri_version}</div>
                    </div>
                    <div className="p-2.5 rounded border border-border bg-background">
                      <div className="text-[10px] text-muted-foreground uppercase">UI</div>
                      <div className="font-semibold mt-0.5">React v{settings?.about.react_version}</div>
                    </div>
                    <div className="p-2.5 rounded border border-border bg-background">
                      <div className="text-[10px] text-muted-foreground uppercase">Backend</div>
                      <div className="font-semibold mt-0.5">Python v{settings?.about.python_version}</div>
                    </div>
                    <div className="p-2.5 rounded border border-border bg-background">
                      <div className="text-[10px] text-muted-foreground uppercase">Database</div>
                      <div className="font-semibold mt-0.5">SQLite v{settings?.about.sqlite_version}</div>
                    </div>
                  </div>
                </div>
              )}

              <div className="p-5 rounded-lg border border-border bg-card shadow-xs space-y-4">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <PackageCheck size={16} className="text-primary" />
                    <div>
                      <h3 className="font-semibold text-sm">Application Update & Installer</h3>
                      <p className="text-xs text-muted-foreground">
                        Install or update FileNest in-place while preserving your SQLite database and credentials.
                      </p>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={handleCheckUpdates}
                    disabled={isCheckingUpdates}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50"
                  >
                    <RefreshCw size={12} className={isCheckingUpdates ? "animate-spin" : ""} />
                    <span>{isCheckingUpdates ? "Checking..." : "Check Installers"}</span>
                  </button>
                </div>

                {updateStatus && (
                  <div className="space-y-3 text-xs">
                    <div className="p-3 rounded-md border border-border bg-muted/30 space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-foreground">{updateStatus.message}</span>
                        <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-secondary text-foreground">
                          v{updateStatus.current_version}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground font-mono break-all">
                        User Data Preserved at: {updateStatus.data_directory}
                      </p>
                    </div>

                    {updateStatus.installers.length > 0 && (
                      <div className="space-y-2">
                        <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                          Available Windows Packages
                        </div>
                        {updateStatus.installers.map((inst) => (
                          <div
                            key={inst.path}
                            className="flex items-center justify-between gap-3 p-2.5 rounded-md border border-border bg-background"
                          >
                            <div className="min-w-0">
                              <div className="font-medium text-foreground truncate">{inst.filename}</div>
                              <div className="text-[11px] text-muted-foreground font-mono truncate">
                                {inst.installer_type.toUpperCase()} • {formatBytes(inst.size_bytes)}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => handleApplyInstallerUpdate(inst.path)}
                              disabled={isApplyingUpdate}
                              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shrink-0"
                            >
                              <Download size={12} />
                              <span>Run Update</span>
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="pt-2 border-t border-border space-y-2">
                  <label className="text-[11px] font-medium text-muted-foreground block">
                    Or apply an installer package (.exe / .msi) from disk:
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={customInstallerPath}
                      onChange={(e) => setCustomInstallerPath(e.target.value)}
                      placeholder="C:\...\FileNest_0.1.0_x64-setup.exe"
                      className="flex-1 text-xs px-3 py-1.5 rounded-md border border-border bg-background text-foreground focus:outline-none focus:ring-1 focus:ring-primary font-mono"
                    />
                    <button
                      type="button"
                      onClick={handleBrowseInstaller}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors"
                    >
                      <FolderOpen size={13} />
                      <span>Browse</span>
                    </button>
                    <button
                      type="button"
                      onClick={() => handleApplyInstallerUpdate(customInstallerPath)}
                      disabled={isApplyingUpdate || !customInstallerPath.trim()}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
                    >
                      <Download size={13} />
                      <span>Install / Update</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Tier 3: Right Telemetry & Maintenance Panel (col-span-3) */}
        <div className="lg:col-span-3 space-y-4">
          {/* Card 1: Application Telemetry */}
          <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-border">
              <Server size={15} className="text-primary" />
              <h4 className="text-xs font-semibold text-foreground">Application Status</h4>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">App Name:</span>
                <span className="font-medium text-foreground">{settings?.about.app_name || "FileNest"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Version:</span>
                <span className="font-mono text-[11px] bg-secondary px-1.5 py-0.5 rounded">v{settings?.about.version || "1.0.0"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Architecture:</span>
                <span className="text-foreground">{settings?.about.architecture || "x86_64"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Platform:</span>
                <span className="text-foreground">{settings?.about.os_name || "Windows"} {settings?.about.os_version || ""}</span>
              </div>
            </div>
          </div>

          {/* Card 2: SQLite Storage Footprint */}
          <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-border">
              <div className="flex items-center gap-2">
                <Database size={15} className="text-emerald-500" />
                <h4 className="text-xs font-semibold text-foreground">Database Storage</h4>
              </div>
              <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600">
                WAL Mode
              </span>
            </div>
            <div className="space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Database Size:</span>
                <span className="font-mono font-medium text-foreground">
                  {formatBytes(settings?.storage.database.size_bytes || 0)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">WAL Journal:</span>
                <span className="font-mono text-muted-foreground">
                  {formatBytes(settings?.storage.database.wal_size_bytes || 0)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Active Tables:</span>
                <span className="font-medium text-foreground">
                  {settings?.storage.database.tables_count || 0} tables
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Status:</span>
                <span className="text-emerald-600 font-semibold flex items-center gap-1">
                  <CheckCircle2 size={12} /> Connected
                </span>
              </div>
            </div>
          </div>

          {/* Card 3: Quick Maintenance Tools */}
          <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3">
            <div className="flex items-center gap-2 pb-2 border-b border-border">
              <Terminal size={15} className="text-primary" />
              <h4 className="text-xs font-semibold text-foreground">Maintenance Actions</h4>
            </div>
            <div className="space-y-2">
              <button
                type="button"
                onClick={handleCompactDatabase}
                disabled={isPerformingMaintenance}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
              >
                <span className="flex items-center gap-2">
                  <Database size={13} className="text-primary" />
                  <span>Compact DB (VACUUM)</span>
                </span>
                {isPerformingMaintenance ? (
                  <RefreshCw size={12} className="animate-spin text-muted-foreground" />
                ) : (
                  <ChevronRight size={12} className="text-muted-foreground" />
                )}
              </button>

              <button
                type="button"
                onClick={handleIntegrityCheck}
                disabled={isPerformingMaintenance}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
              >
                <span className="flex items-center gap-2">
                  <ShieldCheck size={13} className="text-emerald-500" />
                  <span>Check Integrity</span>
                </span>
                {isPerformingMaintenance ? (
                  <RefreshCw size={12} className="animate-spin text-muted-foreground" />
                ) : (
                  <ChevronRight size={12} className="text-muted-foreground" />
                )}
              </button>

              <button
                type="button"
                onClick={handleClearCache}
                disabled={isPerformingMaintenance}
                className="w-full flex items-center justify-between px-3 py-2 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors disabled:opacity-50 cursor-pointer"
              >
                <span className="flex items-center gap-2">
                  <Trash2 size={13} className="text-rose-500" />
                  <span>Clear Cache</span>
                </span>
                {isPerformingMaintenance ? (
                  <RefreshCw size={12} className="animate-spin text-muted-foreground" />
                ) : (
                  <ChevronRight size={12} className="text-muted-foreground" />
                )}
              </button>
            </div>

            {/* Compact Maintenance feedback */}
            {maintenanceOutput && (
              <div className="mt-2 p-2.5 rounded border border-border bg-muted/40 text-[11px] space-y-1">
                <div className="flex items-center justify-between font-semibold">
                  <span className="truncate">{maintenanceOutput.action}</span>
                  <span
                    className={cn(
                      "px-1.5 py-0.2 rounded text-[9px] font-bold uppercase",
                      maintenanceOutput.success ? "text-emerald-600 bg-emerald-500/10" : "text-rose-600 bg-rose-500/10"
                    )}
                  >
                    {maintenanceOutput.success ? "OK" : "Err"}
                  </span>
                </div>
                <p className="font-mono text-muted-foreground text-[10px] break-all">
                  {maintenanceOutput.message}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Sticky Bottom Status and Save Bar */}
      <div className="sticky bottom-0 z-20 mt-8 -mx-6 px-6 py-3 bg-card/95 backdrop-blur border-t border-border shadow-lg flex items-center justify-between">
        <div className="flex items-center gap-3 text-xs">
          {hasUnsavedChanges ? (
            <span className="flex items-center gap-1.5 text-amber-500 font-medium">
              <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
              Unsaved changes in {activeTab.toUpperCase()}
            </span>
          ) : (
            <span className="flex items-center gap-1.5 text-muted-foreground">
              <CheckCircle2 size={13} className="text-emerald-500" />
              {lastSavedTime ? `Last saved at ${lastSavedTime}` : "All settings persisted to SQLite"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeTab !== "about" && (
            <>
              <button
                type="button"
                onClick={handleResetCategory}
                disabled={saving}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors disabled:opacity-50 cursor-pointer"
              >
                <RotateCcw size={13} />
                <span>Reset to Defaults</span>
              </button>
              <button
                type="button"
                onClick={handleSaveActiveTab}
                disabled={saving || !hasUnsavedChanges}
                className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-md text-xs font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50 cursor-pointer"
              >
                <Save size={13} />
                <span>{saving ? "Saving..." : "Save Changes"}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsManager;
