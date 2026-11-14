import React, { useEffect, useState } from "react";
import {
  FolderTree,
  Folder,
  Calendar,
  FileCode,
  Layers,
  Sparkles,
  Play,
  SlidersHorizontal,
} from "lucide-react";
import { ApiService } from "@/services/api";
import type {
  ManagedFolder,
  OrganizationPlanRequest,
  OrganizationSettings,
} from "@/types";

interface OrganizationConfigPanelProps {
  folders: ManagedFolder[];
  selectedFolderId: string;
  onSelectFolderId: (id: string) => void;
  onSubmit: (request: OrganizationPlanRequest) => void;
  isLoading: boolean;
}

export const OrganizationConfigPanel: React.FC<OrganizationConfigPanelProps> = ({
  folders,
  selectedFolderId,
  onSelectFolderId,
  onSubmit,
  isLoading,
}) => {
  const [strategy, setStrategy] = useState<"by_category" | "by_date" | "by_extension" | "by_project" | "custom">("by_category");
  const [subfolder, setSubfolder] = useState("");
  const [includeSubfolders, setIncludeSubfolders] = useState(true);
  const [moveUnorganizedOnly, setMoveUnorganizedOnly] = useState(true);
  const [customInstructions, setCustomInstructions] = useState("");
  const [orgPrefs, setOrgPrefs] = useState<OrganizationSettings | null>(null);

  useEffect(() => {
    let cancelled = false;
    ApiService.getCategorySettings<OrganizationSettings>("organization")
      .then((prefs) => {
        if (cancelled || !prefs) return;
        setOrgPrefs(prefs);
        const strategyMap: Record<
          string,
          "by_category" | "by_date" | "by_extension" | "by_project" | "custom"
        > = {
          file_type: "by_category",
          by_category: "by_category",
          project_structure: "by_project",
          by_project: "by_project",
          by_date: "by_date",
          by_extension: "by_extension",
          custom: "custom",
        };
        if (prefs.default_strategy && strategyMap[prefs.default_strategy]) {
          setStrategy(strategyMap[prefs.default_strategy]);
        }
      })
      .catch(() => {
        // Fallback silently to default UI state if backend preferences fail to load
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFolderId) return;

    onSubmit({
      managed_folder_id: selectedFolderId,
      target_subfolder: subfolder.trim(),
      strategy,
      include_subfolders: includeSubfolders,
      move_unorganized_only: moveUnorganizedOnly,
      custom_rules: strategy === "custom" ? { instructions: customInstructions } : undefined,
    });
  };

  const selectedFolder = folders.find((f) => f.id === selectedFolderId);

  return (
    <form onSubmit={handleSubmit} className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-5">
      <div className="flex items-center gap-2 pb-3 border-b border-border/60">
        <FolderTree size={18} className="text-primary" />
        <h3 className="font-semibold text-sm text-foreground">Organization Configuration</h3>
      </div>

      {/* Select Folder */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-foreground flex items-center justify-between">
          <span>Target Managed Folder</span>
          <span className="text-[11px] text-muted-foreground font-normal">Registered only</span>
        </label>
        <select
          value={selectedFolderId}
          onChange={(e) => onSelectFolderId(e.target.value)}
          className="w-full text-xs bg-muted/40 border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        >
          {folders.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name} ({f.root_path})
            </option>
          ))}
        </select>
        {selectedFolder && (
          <p className="text-[11px] text-muted-foreground font-mono truncate" title={selectedFolder.root_path}>
            Path: {selectedFolder.root_path}
          </p>
        )}
      </div>

      {/* Target Subfolder (optional) */}
      <div className="space-y-1.5">
        <label className="text-xs font-semibold text-foreground">
          Subfolder Scope (Optional)
        </label>
        <input
          type="text"
          placeholder="Leave blank for entire folder or e.g. Downloads"
          value={subfolder}
          onChange={(e) => setSubfolder(e.target.value)}
          className="w-full text-xs bg-muted/40 border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* Organization Goal / Strategy */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground">
          Organization Goal
        </label>
        <div className="grid grid-cols-1 gap-2">
          {/* 1. By File Type */}
          <label
            onClick={() => setStrategy("by_category")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "by_category"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "by_category"}
              onChange={() => setStrategy("by_category")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Folder size={14} className="text-amber-500" />
                <span>Organize by File Type</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Group files into Documents, Images, Videos, Audio, Archives, and Source_Code.
              </p>
            </div>
          </label>

          {/* 2. By Date */}
          <label
            onClick={() => setStrategy("by_date")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "by_date"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "by_date"}
              onChange={() => setStrategy("by_date")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Calendar size={14} className="text-blue-500" />
                <span>Organize by Modified Date</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Sort chronologically into Year and Month directories (e.g. 2026/2026-11).
              </p>
            </div>
          </label>

          {/* 3. By Extension */}
          <label
            onClick={() => setStrategy("by_extension")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "by_extension"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "by_extension"}
              onChange={() => setStrategy("by_extension")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <FileCode size={14} className="text-muted-foreground" />
                <span>Organize by File Extension</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Group files strictly by extension folders (e.g. PDF/, PNG/, DOCX/).
              </p>
            </div>
          </label>

          {/* 4. By Project Structure */}
          <label
            onClick={() => setStrategy("by_project")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "by_project"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "by_project"}
              onChange={() => setStrategy("by_project")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Layers size={14} className="text-indigo-500" />
                <span>Project Structure</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Group into Source, Assets, Documents, Resources, and Archive folders.
              </p>
            </div>
          </label>

          {/* 5. Custom with AI */}
          <label
            onClick={() => setStrategy("custom")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "custom"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "custom"}
              onChange={() => setStrategy("custom")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Sparkles size={14} className="text-amber-500" />
                <span>Custom Instructions</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Describe desired structure using natural rules and conditions.
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Custom Textarea if selected */}
      {strategy === "custom" && (
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-foreground">
            Custom Organization Instructions
          </label>
          <textarea
            rows={3}
            placeholder="e.g. Move files with prefix 'invoice' to Accounting/Invoices..."
            value={customInstructions}
            onChange={(e) => setCustomInstructions(e.target.value)}
            className="w-full text-xs bg-muted/40 border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      )}

      {/* Options */}
      <div className="space-y-2 pt-2 border-t border-border/60">
        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
          <input
            type="checkbox"
            checked={includeSubfolders}
            onChange={(e) => setIncludeSubfolders(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <span>Include subfolders in analysis</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
          <input
            type="checkbox"
            checked={moveUnorganizedOnly}
            onChange={(e) => setMoveUnorganizedOnly(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <span>Move unorganized files only (skip files already organized)</span>
        </label>
      </div>

      {/* Synced Global Organization Defaults Badge */}
      {orgPrefs && (
        <div className="p-2.5 rounded-lg bg-muted/40 border border-border/60 text-[11px] text-muted-foreground space-y-1">
          <div className="flex items-center gap-1.5 font-medium text-foreground">
            <SlidersHorizontal size={12} className="text-primary" />
            <span>Global Organization Defaults Active</span>
          </div>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5">
            <span>Naming: <strong className="text-foreground">{orgPrefs.default_folder_naming}</strong></span>
            <span>Archive: <strong className="text-foreground">{orgPrefs.default_archive_folder_name}</strong></span>
            <span>Conflicts: <strong className="text-foreground">{orgPrefs.conflict_resolution_strategy}</strong></span>
          </div>
        </div>
      )}

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isLoading || !selectedFolderId}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm"
      >
        <Play size={14} className={isLoading ? "animate-spin" : "fill-current"} />
        <span>{isLoading ? "Analyzing & Generating Plan..." : "Analyze & Create Plan"}</span>
      </button>
    </form>
  );
};
