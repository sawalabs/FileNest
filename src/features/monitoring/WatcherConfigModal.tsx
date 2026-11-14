import React, { useState } from "react";
import { X, Settings, Save, Plus, Trash2, Loader2, Info } from "lucide-react";
import type { WatcherItem, MonitoringConfigUpdatePayload } from "@/types";

interface WatcherConfigModalProps {
  watcher: WatcherItem;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
  updateConfig: (
    folderId: string,
    payload: MonitoringConfigUpdatePayload
  ) => Promise<void>;
}

export const WatcherConfigModal: React.FC<WatcherConfigModalProps> = ({
  watcher,
  isOpen,
  onClose,
  onSaved,
  updateConfig,
}) => {
  const [debounceMs, setDebounceMs] = useState(watcher.debounce_ms || 1000);
  const [recursive, setRecursive] = useState(watcher.recursive !== false);
  const [patterns, setPatterns] = useState<string[]>(watcher.ignore_patterns || []);
  const [newPattern, setNewPattern] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleAddPattern = () => {
    const trimmed = newPattern.trim();
    if (!trimmed) return;
    if (!patterns.includes(trimmed)) {
      setPatterns([...patterns, trimmed]);
    }
    setNewPattern("");
  };

  const handleRemovePattern = (idx: number) => {
    setPatterns(patterns.filter((_, i) => i !== idx));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);
    try {
      await updateConfig(watcher.folder_id, {
        debounce_ms: debounceMs,
        recursive,
        ignore_patterns: patterns,
      });
      onSaved();
      onClose();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to update configuration");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-card border border-border w-full max-w-lg rounded-xl shadow-xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-center justify-between bg-muted/30">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-md bg-muted border border-border">
              <Settings size={16} className="text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-sm">Watcher Settings</h3>
              <p className="text-xs text-muted-foreground">{watcher.folder_name}</p>
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
        <div className="p-5 space-y-4 overflow-y-auto max-h-[70vh]">
          {error && (
            <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-700 dark:text-rose-400 text-xs">
              {error}
            </div>
          )}

          {/* Debounce Window */}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center justify-between">
              <span>Debounce Window (ms)</span>
              <span className="font-mono text-primary font-bold">{debounceMs} ms</span>
            </label>
            <input
              type="range"
              min="200"
              max="5000"
              step="100"
              value={debounceMs}
              onChange={(e) => setDebounceMs(Number(e.target.value))}
              className="w-full accent-primary cursor-pointer"
            />
            <p className="text-[11px] text-muted-foreground">
              Collapses burst write events into a single notification. Recommended: 1000ms.
            </p>
          </div>

          {/* Recursive Toggle */}
          <div className="flex items-center justify-between p-3 rounded-lg border border-border bg-muted/20">
            <div>
              <span className="text-xs font-medium block">Watch Subdirectories</span>
              <span className="text-[11px] text-muted-foreground">
                Recursively monitor subfolders inside this managed folder
              </span>
            </div>
            <input
              type="checkbox"
              checked={recursive}
              onChange={(e) => setRecursive(e.target.checked)}
              className="w-4 h-4 rounded border-border text-primary focus:ring-primary cursor-pointer"
            />
          </div>

          {/* Custom Ignore Patterns */}
          <div className="space-y-2">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Custom Ignore Patterns
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={newPattern}
                onChange={(e) => setNewPattern(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleAddPattern();
                  }
                }}
                placeholder="e.g. *.log, build/*, temp*"
                className="flex-1 px-3 py-1.5 rounded-md border border-border bg-background text-xs font-mono focus:outline-none focus:ring-1 focus:ring-primary"
              />
              <button
                type="button"
                onClick={handleAddPattern}
                className="px-3 py-1.5 rounded-md bg-secondary text-secondary-foreground text-xs font-medium hover:bg-secondary/80 border border-border transition-colors flex items-center gap-1"
              >
                <Plus size={14} />
                <span>Add</span>
              </button>
            </div>

            {/* Pattern Tags */}
            <div className="flex flex-wrap gap-1.5 pt-1 max-h-36 overflow-y-auto">
              {patterns.length === 0 ? (
                <span className="text-xs text-muted-foreground italic">
                  No custom patterns defined (standard temp files are ignored automatically)
                </span>
              ) : (
                patterns.map((p, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted border border-border text-xs font-mono"
                  >
                    <span>{p}</span>
                    <button
                      type="button"
                      onClick={() => handleRemovePattern(idx)}
                      className="text-muted-foreground hover:text-rose-500"
                    >
                      <Trash2 size={12} />
                    </button>
                  </span>
                ))
              )}
            </div>
            <div className="text-[11px] text-muted-foreground flex items-center gap-1">
              <Info size={12} />
              <span>Matching files are ignored and never written to the activity log.</span>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-border bg-muted/30 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="px-3 py-1.5 rounded-md border border-border text-xs font-medium hover:bg-muted transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50"
          >
            {isSaving ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            <span>Save Settings</span>
          </button>
        </div>
      </div>
    </div>
  );
};

