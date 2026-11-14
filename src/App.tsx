import { useEffect, useState } from "react";
import { AppLayout } from "@/components/layout/AppLayout";
import { ApiService } from "@/services/api";
import { DashboardManager } from "@/features/dashboard/DashboardManager";
import { ManagedFoldersManager } from "@/features/managed-folders/ManagedFoldersManager";
import { FilesManager } from "@/features/files/FilesManager";
import { StorageAnalyzer } from "@/features/storage/StorageAnalyzer";
import { OrganizationManager } from "@/features/organization/OrganizationManager";
import { SmartRenameManager } from "@/features/smart-rename/SmartRenameManager";
import { ReviewChangesManager } from "@/features/review-changes/ReviewChangesManager";
import { HistoryManager } from "@/features/history/HistoryManager";
import { MonitoringManager } from "@/features/monitoring/MonitoringManager";
import { SettingsManager } from "@/features/settings/SettingsManager";
import { ContextualAssistantPanel } from "@/components/assistant/ContextualAssistantPanel";
import { CommandPalette } from "@/components/layout/CommandPalette";
import type { NavItem, BackendHealth } from "@/types";

export function App() {
  const [activeItem, setActiveItem] = useState<NavItem>("dashboard");
  const [pendingFileNavigation, setPendingFileNavigation] = useState<{
    folderId: string;
    relativePath: string;
  } | null>(null);
  const [isAssistantOpen, setIsAssistantOpen] = useState<boolean>(false);
  const [assistantContext, setAssistantContext] = useState<{
    folderId?: string | null;
    targetType?: "general" | "file" | "folder" | "plan" | "analysis";
    relativePath?: string | null;
    entityId?: string | null;
    autoPrompt?: string | null;
  } | null>(null);

  const handleOpenAssistant = (context?: {
    folderId?: string | null;
    targetType?: "general" | "file" | "folder" | "plan" | "analysis";
    relativePath?: string | null;
    entityId?: string | null;
    autoPrompt?: string | null;
  }) => {
    if (context) {
      setAssistantContext(context);
    }
    setIsAssistantOpen(true);
  };

  const [backendHealth, setBackendHealth] = useState<BackendHealth>({
    status: "connecting",
  });

  const fetchHealth = async () => {
    const health = await ApiService.checkHealth();
    setBackendHealth(health);
  };

  useEffect(() => {
    ApiService.initSession().then(() => fetchHealth());
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  // Suppress browser default context menu (inspect, reload, etc.) globally across desktop app
  useEffect(() => {
    const handleGlobalContextMenu = (e: MouseEvent) => {
      e.preventDefault();
    };

    window.addEventListener("contextmenu", handleGlobalContextMenu);
    return () => window.removeEventListener("contextmenu", handleGlobalContextMenu);
  }, []);

  return (
    <>
      <AppLayout
        activeItem={activeItem}
        onNavigate={setActiveItem}
        backendHealth={backendHealth}
        onToggleAssistant={() => setIsAssistantOpen((prev) => !prev)}
      >
        {activeItem === "dashboard" ? (
          <DashboardManager onNavigate={setActiveItem} />
        ) : activeItem === "files" ? (
          <FilesManager
            onOpenAssistant={handleOpenAssistant}
            initialNavigationTarget={pendingFileNavigation}
            onClearInitialNavigation={() => setPendingFileNavigation(null)}
          />
        ) : activeItem === "storage" ? (
          <StorageAnalyzer
            onNavigateToFiles={(folderId, relativePath) => {
              setPendingFileNavigation({ folderId, relativePath });
              setActiveItem("files");
            }}
            onNavigateToReviewChanges={() => {
              setActiveItem("review-changes");
            }}
          />
        ) : activeItem === "organization" ? (
          <OrganizationManager
            onNavigateToReviewChanges={() => setActiveItem("review-changes")}
          />
        ) : activeItem === "smart-rename" ? (
          <SmartRenameManager
            onNavigateToReviewChanges={() => setActiveItem("review-changes")}
          />
        ) : activeItem === "review-changes" ? (
          <ReviewChangesManager />
        ) : activeItem === "history" ? (
          <HistoryManager />
        ) : activeItem === "monitoring" ? (
          <MonitoringManager />
        ) : activeItem === "managed-folders" ? (
          <ManagedFoldersManager />
        ) : activeItem === "settings" ? (
          <SettingsManager />
        ) : (
          <DashboardManager onNavigate={setActiveItem} />
        )}
      </AppLayout>

      <ContextualAssistantPanel
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
        onNavigateToReviewChanges={() => setActiveItem("review-changes")}
        initialFolderId={assistantContext?.folderId}
        initialTargetType={assistantContext?.targetType}
        initialRelativePath={assistantContext?.relativePath}
        initialEntityId={assistantContext?.entityId}
        autoPrompt={assistantContext?.autoPrompt}
      />

      <CommandPalette
        onNavigate={setActiveItem}
        onNavigateToFile={(folderId, relativePath) => {
          setPendingFileNavigation({ folderId, relativePath });
          setActiveItem("files");
        }}
        onToggleAssistant={() => setIsAssistantOpen((prev) => !prev)}
      />
    </>
  );
}

export default App;
