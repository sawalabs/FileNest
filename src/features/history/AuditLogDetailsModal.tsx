import React from "react";
import { X, Sparkles, User, Cpu, Calendar, Tag, Database } from "lucide-react";
import type { AuditLogItem } from "@/types";

interface AuditLogDetailsModalProps {
  log: AuditLogItem;
  isOpen: boolean;
  onClose: () => void;
}

export const AuditLogDetailsModal: React.FC<AuditLogDetailsModalProps> = ({
  log,
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const getActorBadge = (actor: string) => {
    switch (actor) {
      case "ai":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-secondary text-secondary-foreground border border-border">
            <Sparkles size={12} className="text-muted-foreground" />
            AI Agent
          </span>
        );
      case "user":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <User size={12} />
            User
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-muted text-muted-foreground border border-border">
            <Cpu size={12} />
            System
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-card border border-border w-full max-w-xl rounded-xl shadow-xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-muted border border-border">
              <Database size={16} className="text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">Audit Record Details</h3>
              <p className="text-xs text-muted-foreground">ID: {log.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4 overflow-y-auto max-h-[70vh]">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 text-xs p-3.5 rounded-lg border border-border bg-muted/20">
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Tag size={12} /> Action Event
              </span>
              <span className="font-mono font-medium">{log.action}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <User size={12} /> Actor
              </span>
              {getActorBadge(log.actor_type)}
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Calendar size={12} /> Timestamp (UTC)
              </span>
              <span className="font-mono font-medium">{log.created_at}</span>
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Database size={12} /> Target Entity
              </span>
              <span className="font-mono">
                {log.entity_type} {log.entity_id ? `(${log.entity_id.slice(0, 8)}...)` : ""}
              </span>
            </div>
          </div>

          {/* Details JSON */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Event Payload & Snapshot
            </label>
            <pre className="p-3.5 rounded-lg border border-border bg-muted/30 text-xs font-mono overflow-x-auto text-foreground max-h-60">
              {log.details ? JSON.stringify(log.details, null, 2) : "// No additional details recorded"}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border bg-muted/30 flex justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-md text-xs font-medium border border-border bg-background hover:bg-muted transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

