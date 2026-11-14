import React from "react";
import {
  X,
  FilePlus,
  FilePenLine,
  Trash2,
  FolderInput,
  FileText,
  Calendar,
  Folder,
  Tag,
  ArrowRight,
} from "lucide-react";
import type { MonitoringEventItem } from "@/types";

interface EventDetailsModalProps {
  event: MonitoringEventItem;
  isOpen: boolean;
  onClose: () => void;
}

export const EventDetailsModal: React.FC<EventDetailsModalProps> = ({
  event,
  isOpen,
  onClose,
}) => {
  if (!isOpen) return null;

  const getEventBadge = (type: string) => {
    switch (type) {
      case "created":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <FilePlus size={13} />
            Created
          </span>
        );
      case "modified":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FilePenLine size={13} />
            Modified
          </span>
        );
      case "deleted":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <Trash2 size={13} />
            Deleted
          </span>
        );
      case "moved":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FolderInput size={13} />
            Moved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded text-xs font-semibold bg-muted text-muted-foreground border border-border">
            {type}
          </span>
        );
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-card border border-border w-full max-w-lg rounded-xl shadow-xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-muted border border-border">
              <FileText size={16} className="text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">Monitoring Event Details</h3>
              <p className="text-xs text-muted-foreground">ID: {event.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
          >
            <X size={18} />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 space-y-4 text-xs overflow-y-auto max-h-[70vh]">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 gap-3 p-3.5 rounded-lg border border-border bg-muted/20">
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Tag size={12} /> Event Type
              </span>
              {getEventBadge(event.event_type)}
            </div>
            <div>
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Calendar size={12} /> Occurred At (UTC)
              </span>
              <span className="font-mono font-medium">{event.occurred_at}</span>
            </div>
            <div className="col-span-2">
              <span className="text-muted-foreground block text-[11px] mb-1 flex items-center gap-1">
                <Folder size={12} /> Managed Folder
              </span>
              <span className="font-medium text-foreground">{event.managed_folder_name}</span>
            </div>
          </div>

          {/* Path Details */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Relative Path Snapshot
            </label>
            <div className="p-3 rounded-lg border border-border bg-muted/30 font-mono text-xs break-all">
              {event.relative_path}
            </div>

            {event.destination_relative_path && (
              <div className="space-y-1 pt-1">
                <span className="text-[11px] text-muted-foreground flex items-center gap-1 font-medium">
                  <ArrowRight size={12} /> Destination Path
                </span>
                <div className="p-3 rounded-lg border border-border bg-muted/30 font-mono text-xs break-all">
                  {event.destination_relative_path}
                </div>
              </div>
            )}
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

