import React from "react";
import { AppSidebar } from "./AppSidebar";
import type { NavItem, BackendHealth } from "@/types";
import { cn } from "@/lib/utils";

interface AppLayoutProps {
  activeItem: NavItem;
  onNavigate: (item: NavItem) => void;
  backendHealth: BackendHealth;
  onToggleAssistant?: () => void;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  activeItem,
  onNavigate,
  backendHealth,
  onToggleAssistant,
  children,
}) => {
  const isWorkspace = activeItem === "files";
  const isReviewChanges = activeItem === "review-changes";
  const isSmartRename = activeItem === "smart-rename";
  const isOrganization = activeItem === "organization";
  const isHistory = activeItem === "history";
  const isFullBleed = isWorkspace || isReviewChanges || isSmartRename || isOrganization || isHistory;

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <AppSidebar
        activeItem={activeItem}
        onNavigate={onNavigate}
        backendHealth={backendHealth}
        onToggleAssistant={onToggleAssistant}
      />
      <main
        className={cn(
          "flex-1 transition-all",
          isFullBleed
            ? "p-0 overflow-hidden flex flex-col h-full"
            : "p-6 md:p-8 overflow-y-auto"
        )}
      >
        <div
          className={cn(
            isFullBleed
              ? "h-full w-full flex flex-col min-h-0"
              : "w-full max-w-[1536px] mx-auto"
          )}
        >
          {children}
        </div>
      </main>
    </div>
  );
};
