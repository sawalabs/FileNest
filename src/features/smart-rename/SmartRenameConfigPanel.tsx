import React, { useState } from "react";
import {
  FilePenLine,
  Sparkles,
  Play,
  Type,
  Hash,
  ScanText,
} from "lucide-react";
import type { ManagedFolder, SmartRenamePlanRequest } from "@/types";

interface SmartRenameConfigPanelProps {
  folders: ManagedFolder[];
  selectedFolderId: string;
  onSelectFolderId: (id: string) => void;
  onSubmit: (request: SmartRenamePlanRequest) => void;
  isLoading: boolean;
}

export const SmartRenameConfigPanel: React.FC<SmartRenameConfigPanelProps> = ({
  folders,
  selectedFolderId,
  onSelectFolderId,
  onSubmit,
  isLoading,
}) => {
  const [strategy, setStrategy] = useState<"describe_content" | "make_consistent" | "pattern" | "add_meaningful">("describe_content");
  const [useAiContent, setUseAiContent] = useState(true);
  const [runOcrBackground, setRunOcrBackground] = useState(false);
  const [subfolder, setSubfolder] = useState("");
  const [pattern, setPattern] = useState("{project}_{type}_{number}");
  const [caseTransform, setCaseTransform] = useState<"lower" | "upper" | "title" | "preserve">("lower");
  const [spaceReplacement, setSpaceReplacement] = useState<"_" | "-" | "none">("_");
  const [keepExtension, setKeepExtension] = useState(true);
  const [addSequenceOnCollision, setAddSequenceOnCollision] = useState(true);
  const [skipCompliantFiles, setSkipCompliantFiles] = useState(true);
  const [prefix, setPrefix] = useState("");
  const [suffix, setSuffix] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFolderId) return;

    onSubmit({
      managed_folder_id: selectedFolderId,
      target_subfolder: subfolder.trim(),
      strategy,
      pattern: strategy === "pattern" ? pattern : undefined,
      case_transform: caseTransform,
      space_replacement: spaceReplacement,
      keep_extension: keepExtension,
      add_sequence_on_collision: addSequenceOnCollision,
      skip_compliant_files: skipCompliantFiles,
      prefix: prefix.trim(),
      suffix: suffix.trim(),
      use_ai_content: useAiContent,
      run_ocr_background: runOcrBackground,
    });
  };

  const selectedFolder = folders.find((f) => f.id === selectedFolderId);

  return (
    <form onSubmit={handleSubmit} className="p-5 rounded-xl border border-border bg-card shadow-sm space-y-5">
      <div className="flex items-center gap-2 pb-3 border-b border-border/60">
        <FilePenLine size={18} className="text-primary" />
        <h3 className="font-semibold text-sm text-foreground">Rename Configuration</h3>
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
          placeholder="Leave blank for entire folder or e.g. Documents"
          value={subfolder}
          onChange={(e) => setSubfolder(e.target.value)}
          className="w-full text-xs bg-muted/40 border border-border rounded-md px-3 py-2 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
        />
      </div>

      {/* Naming Strategy */}
      <div className="space-y-2">
        <label className="text-xs font-semibold text-foreground">
          Naming Strategy
        </label>
        <div className="grid grid-cols-1 gap-2">
          {/* 1. Describe Content (AI & PaddleOCR) */}
          <label
            onClick={() => setStrategy("describe_content")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "describe_content"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "describe_content"}
              onChange={() => setStrategy("describe_content")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <ScanText size={14} className="text-primary" />
                <span>Describe Content (PaddleOCR & AI)</span>
                <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground font-medium border border-border">Sesuai Gambar</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Ekstrak teks di dalam gambar (struk, invoice, label, screenshot) dengan PaddleOCR dan rumuskan nama berkas baru yang sesuai dengan isi gambar.
              </p>
            </div>
          </label>

          {/* 2. Make Consistent */}
          <label
            onClick={() => setStrategy("make_consistent")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "make_consistent"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "make_consistent"}
              onChange={() => setStrategy("make_consistent")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Type size={14} className="text-blue-500" />
                <span>Make Consistent</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Standardize naming conventions: clean special characters, strip duplicate delimiters, normalize spaces.
              </p>
            </div>
          </label>

          {/* 2. Pattern Based */}
          <label
            onClick={() => setStrategy("pattern")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "pattern"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "pattern"}
              onChange={() => setStrategy("pattern")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Hash size={14} className="text-muted-foreground" />
                <span>Custom Pattern</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Apply structured templates using variables like &#123;project&#125;, &#123;type&#125;, &#123;date&#125;, &#123;number&#125;.
              </p>
            </div>
          </label>

          {/* 3. Add Meaningful */}
          <label
            onClick={() => setStrategy("add_meaningful")}
            className={`p-3 rounded-lg border cursor-pointer transition-all flex items-start gap-3 ${
              strategy === "add_meaningful"
                ? "border-primary bg-primary/5 ring-1 ring-primary/20"
                : "border-border hover:bg-muted/40"
            }`}
          >
            <input
              type="radio"
              name="strategy"
              checked={strategy === "add_meaningful"}
              onChange={() => setStrategy("add_meaningful")}
              className="mt-0.5 text-primary focus:ring-primary"
            />
            <div className="space-y-0.5">
              <div className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Sparkles size={14} className="text-amber-500" />
                <span>Clean & Descriptive</span>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Strip camera and scanner prefixes (IMG_, DSC_), noise words (copy, final, draft), and format neatly.
              </p>
            </div>
          </label>
        </div>
      </div>

      {/* Pattern Template Input (if pattern strategy selected) */}
      {strategy === "pattern" && (
        <div className="space-y-1.5 bg-muted/20 p-3 rounded-lg border border-border/60">
          <label className="text-xs font-semibold text-foreground">
            Pattern Template
          </label>
          <input
            type="text"
            value={pattern}
            onChange={(e) => setPattern(e.target.value)}
            className="w-full text-xs font-mono bg-card border border-border rounded-md px-3 py-1.5 text-foreground focus:outline-none focus:ring-1 focus:ring-primary"
          />
          <p className="text-[10px] text-muted-foreground">
            Available: <code className="text-primary">&#123;name&#125;</code>, <code className="text-primary">&#123;project&#125;</code>, <code className="text-primary">&#123;type&#125;</code>, <code className="text-primary">&#123;date&#125;</code>, <code className="text-primary">&#123;number&#125;</code>
          </p>
        </div>
      )}

      {/* Formatting Controls */}
      <div className="grid grid-cols-2 gap-3 pt-2 border-t border-border/60">
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-muted-foreground">Case Transform</label>
          <select
            value={caseTransform}
            onChange={(e) => setCaseTransform(e.target.value as any)}
            className="w-full text-xs bg-muted/40 border border-border rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="lower">lowercase (file_name)</option>
            <option value="upper">UPPERCASE (FILE_NAME)</option>
            <option value="title">Title Case (File_Name)</option>
            <option value="preserve">Preserve Original</option>
          </select>
        </div>

        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-muted-foreground">Space Replacement</label>
          <select
            value={spaceReplacement}
            onChange={(e) => setSpaceReplacement(e.target.value as any)}
            className="w-full text-xs bg-muted/40 border border-border rounded-md px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="_">Underscore (_)</option>
            <option value="-">Hyphen (-)</option>
            <option value="none">Keep Spaces</option>
          </select>
        </div>
      </div>

      {/* Prefix / Suffix */}
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-muted-foreground">Prefix (Optional)</label>
          <input
            type="text"
            placeholder="e.g. 2026_"
            value={prefix}
            onChange={(e) => setPrefix(e.target.value)}
            className="w-full text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
        <div className="space-y-1">
          <label className="text-[11px] font-semibold text-muted-foreground">Suffix (Optional)</label>
          <input
            type="text"
            placeholder="e.g. _v1"
            value={suffix}
            onChange={(e) => setSuffix(e.target.value)}
            className="w-full text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
          />
        </div>
      </div>

      {/* Checkbox Options */}
      <div className="space-y-2 pt-2 border-t border-border/60">
        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground p-2 rounded-md bg-muted/40 border border-border">
          <input
            type="checkbox"
            checked={useAiContent}
            onChange={(e) => setUseAiContent(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <div className="flex flex-col">
            <span className="font-medium text-foreground">Aktifkan pemahaman isi gambar (PaddleOCR & AI)</span>
            <span className="text-[10px] text-muted-foreground">Rencana awal dibuat instan. Anda dapat menjalankan OCR per file atau di latar belakang.</span>
          </div>
        </label>

        {useAiContent && (
          <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground p-2 rounded-md bg-primary/5 border border-primary/20">
            <input
              type="checkbox"
              checked={runOcrBackground}
              onChange={(e) => setRunOcrBackground(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary"
            />
            <div className="flex flex-col">
              <span className="font-medium text-primary">Jalankan OCR semua file langsung di background</span>
              <span className="text-[10px] text-muted-foreground">Proses berjalan otomatis di latar belakang tanpa memblokir UI</span>
            </div>
          </label>
        )}

        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
          <input
            type="checkbox"
            checked={keepExtension}
            onChange={(e) => setKeepExtension(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <span>Preserve original file extension</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
          <input
            type="checkbox"
            checked={addSequenceOnCollision}
            onChange={(e) => setAddSequenceOnCollision(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <span>Auto-resolve collisions with numbers (_01, _02)</span>
        </label>

        <label className="flex items-center gap-2 cursor-pointer text-xs text-foreground">
          <input
            type="checkbox"
            checked={skipCompliantFiles}
            onChange={(e) => setSkipCompliantFiles(e.target.checked)}
            className="rounded border-border text-primary focus:ring-primary"
          />
          <span>Skip files that already match convention</span>
        </label>
      </div>

      {/* Submit Button */}
      <button
        type="submit"
        disabled={isLoading || !selectedFolderId}
        className="w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 shadow-sm"
      >
        <Play size={14} className={isLoading ? "animate-spin" : "fill-current"} />
        <span>{isLoading ? "Generating Rename Plan..." : "Generate Rename Plan"}</span>
      </button>
    </form>
  );
};
