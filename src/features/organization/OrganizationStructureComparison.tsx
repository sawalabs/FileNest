import React from "react";
import {
  Folder,
  FolderPlus,
  Layers,
} from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { StructureTreeNode } from "@/types";

interface OrganizationStructureComparisonProps {
  currentStructure: StructureTreeNode[];
  proposedStructure: StructureTreeNode[];
}

export const OrganizationStructureComparison: React.FC<OrganizationStructureComparisonProps> = ({
  currentStructure,
  proposedStructure,
}) => {
  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-4">
      <div className="flex items-center justify-between pb-3 border-b border-border/60">
        <div className="flex items-center gap-2">
          <Layers size={18} className="text-primary" />
          <h3 className="font-semibold text-sm text-foreground">Structure Comparison</h3>
        </div>
        <span className="text-xs text-muted-foreground">
          Previewing organizational layout before approval
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Left: Current Structure */}
        <div className="rounded-lg border border-border/70 bg-muted/20 p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-border/40">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1.5">
              <Folder size={14} className="text-muted-foreground" />
              <span>Current Structure</span>
            </span>
            <span className="text-[11px] text-muted-foreground">
              {currentStructure.length} directories
            </span>
          </div>

          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {currentStructure.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4 text-center">
                Empty or unindexed folder.
              </p>
            ) : (
              currentStructure.map((node) => (
                <div
                  key={node.relative_path || "root"}
                  className="flex items-center justify-between p-2 rounded-md bg-card/60 border border-border/40 text-xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Folder size={15} className="text-amber-500 fill-amber-500/20 shrink-0" />
                    <span className="font-medium text-foreground truncate" title={node.relative_path || "Root"}>
                      {node.name}
                    </span>
                    <span className="text-[11px] text-muted-foreground">
                      ({formatNumber(node.files_count)} files)
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                    {formatBytes(node.size_bytes)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Right: Proposed Structure */}
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
          <div className="flex items-center justify-between pb-2 border-b border-primary/20">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary flex items-center gap-1.5">
              <FolderPlus size={14} className="text-primary" />
              <span>Proposed Layout</span>
            </span>
            <span className="text-[11px] text-primary/80 font-medium">
              {proposedStructure.length} organized groups
            </span>
          </div>

          <div className="space-y-1.5 max-h-72 overflow-y-auto pr-1">
            {proposedStructure.length === 0 ? (
              <p className="text-xs text-muted-foreground italic py-4 text-center">
                No proposed structure generated.
              </p>
            ) : (
              proposedStructure.map((node) => (
                <div
                  key={node.relative_path || "root"}
                  className={`flex items-center justify-between p-2 rounded-md border text-xs transition-colors ${
                    node.is_new
                      ? "bg-primary/10 border-primary/40 text-foreground"
                      : "bg-card/80 border-border/50 text-foreground"
                  }`}
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <Folder
                      size={15}
                      className={
                        node.is_new
                          ? "text-primary fill-primary/20 shrink-0"
                          : "text-amber-500 fill-amber-500/20 shrink-0"
                      }
                    />
                    <span className="font-semibold text-foreground truncate" title={node.relative_path || "Root"}>
                      {node.name}
                    </span>
                    {node.is_new && (
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-primary text-primary-foreground">
                        NEW
                      </span>
                    )}
                    <span className="text-[11px] text-muted-foreground">
                      ({formatNumber(node.files_count)} files)
                    </span>
                  </div>
                  <span className="text-[11px] font-mono text-muted-foreground shrink-0">
                    {formatBytes(node.size_bytes)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
