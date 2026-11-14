import React, { useState, useEffect } from "react";
import {
  X,
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Copy,
  Check,
  Loader2,
  AlertCircle,
  ScanText,
  FileText,
  Eye,
} from "lucide-react";
import { FileIcon } from "./FileIcon";
import { ApiService } from "@/services/api";
import type { FileItemMetadata, OCRExtractResponse } from "@/types";
import { cn } from "@/lib/utils";

interface FilePreviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  item: FileItemMetadata | null;
  managedFolderRoot: string;
  managedFolderId?: string;
  initialTab?: "preview" | "ocr";
}

const TEXT_CODE_EXTENSIONS = new Set([
  "txt", "md", "markdown", "rst", "log", "csv", "tsv",
  "json", "yaml", "yml", "xml", "html", "css",
  "js", "jsx", "ts", "tsx", "py", "rs", "sql", "sh", "bat", "cmd",
  "toml", "ini", "env", "conf", "cfg",
]);

export const FilePreviewModal: React.FC<FilePreviewModalProps> = ({
  isOpen,
  onClose,
  item,
  managedFolderRoot,
  managedFolderId,
  initialTab = "preview",
}) => {
  const [zoom, setZoom] = useState(100);
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [textContent, setTextContent] = useState<string | null>(null);
  const [textMeta, setTextMeta] = useState<{ lines: number; truncated: boolean; bytes: number } | null>(null);
  const [loading, setLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // PaddleOCR State
  const [activeTab, setActiveTab] = useState<"preview" | "ocr">(initialTab);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrResult, setOcrResult] = useState<OCRExtractResponse | null>(null);
  const [ocrError, setOcrError] = useState<string | null>(null);
  const [copiedOcr, setCopiedOcr] = useState(false);

  const ext = item?.extension?.toLowerCase() || "";
  const isImage = item?.category === "image" || ["jpg", "jpeg", "png", "webp", "gif", "bmp", "svg", "ico"].includes(ext);
  const isTextOrCode = !isImage && (item?.category === "code" || TEXT_CODE_EXTENSIONS.has(ext));
  const isOCREligible = ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"].includes(ext) || isImage;

  useEffect(() => {
    let activeUrl: string | null = null;

    if (!isOpen || !item || !managedFolderId) {
      setBlobUrl(null);
      setTextContent(null);
      setTextMeta(null);
      setPreviewError(null);
      setZoom(100);
      setActiveTab(initialTab);
      setOcrResult(null);
      setOcrError(null);
      return;
    }

    setLoading(true);
    setPreviewError(null);
    setZoom(100);
    setActiveTab(initialTab);
    setOcrResult(null);
    setOcrError(null);

    if (isImage) {
      ApiService.getFilePreviewBlob(managedFolderId, item.relative_path, false)
        .then((url) => {
          activeUrl = url;
          setBlobUrl(url);
          setLoading(false);
        })
        .catch((err) => {
          setPreviewError(err.message || "Gagal memuat pratinjau gambar.");
          setLoading(false);
        });
    } else if (isTextOrCode) {
      ApiService.getFileTextPreview(managedFolderId, item.relative_path, 65536)
        .then((res) => {
          setTextContent(res.content);
          setTextMeta({
            lines: res.lines_count,
            truncated: res.truncated,
            bytes: res.preview_bytes,
          });
          setLoading(false);
        })
        .catch((err) => {
          setPreviewError(err.message || "Gagal membaca berkas teks.");
          setLoading(false);
        });
    } else {
      setLoading(false);
    }

    return () => {
      if (activeUrl) {
        URL.revokeObjectURL(activeUrl);
      }
    };
  }, [isOpen, item, managedFolderId, isImage, isTextOrCode]);

  if (!isOpen || !item) return null;

  const fullPath = `${managedFolderRoot}\\${item.relative_path.replace(/\//g, "\\")}`;

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  const handleCopyText = () => {
    if (textContent) {
      navigator.clipboard.writeText(textContent);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleRunOCR = async () => {
    if (!managedFolderId || !item) return;
    setActiveTab("ocr");
    if (ocrResult) return;
    setOcrLoading(true);
    setOcrError(null);
    try {
      const res = await ApiService.extractOCR({
        folder_id: managedFolderId,
        relative_path: item.relative_path,
        max_pages: 10,
      });
      setOcrResult(res);
    } catch (err: unknown) {
      setOcrError(err instanceof Error ? err.message : "Gagal mengekstrak teks OCR");
    } finally {
      setOcrLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && item && managedFolderId && initialTab === "ocr" && isOCREligible && !ocrResult && !ocrLoading) {
      handleRunOCR();
    }
  }, [isOpen, item, managedFolderId, initialTab, isOCREligible]);

  const handleCopyOcr = () => {
    if (ocrResult?.full_text) {
      navigator.clipboard.writeText(ocrResult.full_text);
      setCopiedOcr(true);
      setTimeout(() => setCopiedOcr(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="w-full max-w-4xl rounded-xl border border-border bg-card shadow-2xl overflow-hidden flex flex-col max-h-[88vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-3.5 bg-muted/30">
          <div className="flex items-center gap-2.5">
            <FileIcon
              itemType={item.item_type}
              category={item.category}
              extension={item.extension}
              size={22}
            />
            <div>
              <h3 className="text-sm font-semibold text-foreground truncate max-w-md">{item.name}</h3>
              <p className="text-[11px] text-muted-foreground">
                {item.category.toUpperCase()} • {formatSize(item.size_bytes)}
                {item.mime_type && ` • ${item.mime_type}`}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {isOCREligible && (
              <div className="flex items-center rounded-md border border-border p-0.5 bg-muted/40 mr-1.5">
                <button
                  type="button"
                  onClick={() => setActiveTab("preview")}
                  className={cn(
                    "flex items-center gap-1 px-2 py-0.5 text-xs rounded font-medium transition-colors",
                    activeTab === "preview"
                      ? "bg-card text-foreground shadow-xs"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Eye size={12} />
                  <span>Pratinjau</span>
                </button>
                <button
                  type="button"
                  onClick={handleRunOCR}
                  disabled={ocrLoading}
                  className={cn(
                    "flex items-center gap-1 px-2 py-0.5 text-xs rounded font-medium transition-colors",
                    activeTab === "ocr"
                      ? "bg-card text-foreground shadow-xs font-semibold"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {ocrLoading ? (
                    <Loader2 size={12} className="animate-spin text-primary" />
                  ) : (
                    <ScanText size={12} />
                  )}
                  <span>PaddleOCR</span>
                </button>
              </div>
            )}

            {activeTab === "preview" && isImage && blobUrl && (
              <>
                <button
                  onClick={() => setZoom((z) => Math.max(25, z - 25))}
                  className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors"
                  title="Zoom Out"
                >
                  <ZoomOut size={16} />
                </button>
                <button
                  onClick={() => setZoom(100)}
                  className="flex items-center gap-1 text-xs font-mono px-2 py-0.5 rounded text-muted-foreground hover:bg-muted transition-colors"
                  title="Reset Zoom"
                >
                  <RotateCcw size={12} />
                  <span>{zoom}%</span>
                </button>
                <button
                  onClick={() => setZoom((z) => Math.min(300, z + 25))}
                  className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors"
                  title="Zoom In"
                >
                  <ZoomIn size={16} />
                </button>
              </>
            )}

            {activeTab === "preview" && isTextOrCode && textContent && (
              <button
                onClick={handleCopyText}
                className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-border bg-card hover:bg-muted text-foreground transition-colors"
                title="Salin Isi Teks"
              >
                {copied ? <Check size={14} className="text-emerald-500" /> : <Copy size={14} />}
                <span>{copied ? "Disalin" : "Salin"}</span>
              </button>
            )}

            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-muted-foreground hover:bg-muted transition-colors ml-2"
              title="Close"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Modal Content */}
        <div className="flex-1 overflow-auto p-5 flex items-center justify-center bg-background/50 min-h-[360px]">
          {activeTab === "ocr" ? (
            <div className="w-full h-full flex flex-col rounded-lg border border-border bg-card overflow-hidden shadow-xs">
              <div className="flex items-center justify-between border-b border-border px-4 py-2.5 bg-muted/40">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 rounded-md bg-secondary text-secondary-foreground border border-border">
                    <ScanText size={16} />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                      PaddleOCR PP-OCRv4
                      {ocrResult && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-secondary text-secondary-foreground font-mono font-medium border border-border">
                          {(ocrResult.confidence * 100).toFixed(1)}% akurasi
                        </span>
                      )}
                    </h4>
                    {ocrResult && (
                      <p className="text-[10px] text-muted-foreground">
                        {ocrResult.word_count} kata • {ocrResult.pages.length} halaman • {ocrResult.duration_ms} ms
                      </p>
                    )}
                  </div>
                </div>

                {ocrResult && ocrResult.full_text && (
                  <button
                    onClick={handleCopyOcr}
                    className="flex items-center gap-1 px-2.5 py-1 text-xs rounded-md border border-border bg-card hover:bg-muted text-foreground transition-colors"
                  >
                    {copiedOcr ? <Check size={13} className="text-emerald-500" /> : <Copy size={13} />}
                    <span>{copiedOcr ? "Disalin" : "Salin Teks"}</span>
                  </button>
                )}
              </div>

              <div className="flex-1 overflow-auto p-4 select-text max-h-[500px]">
                {ocrLoading ? (
                  <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-2">
                    <Loader2 size={28} className="animate-spin text-primary" />
                    <p className="text-xs">Mengekstrak teks dengan engine on-device PaddleOCR PP-OCRv4...</p>
                  </div>
                ) : ocrError ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center gap-2">
                    <AlertCircle size={32} className="text-rose-500" />
                    <h5 className="text-xs font-semibold text-foreground">Gagal Mengekstrak Teks</h5>
                    <p className="text-[11px] text-muted-foreground max-w-sm">{ocrError}</p>
                    <button
                      onClick={handleRunOCR}
                      className="mt-2 px-3 py-1 text-xs rounded-md bg-secondary hover:bg-secondary/80 font-medium"
                    >
                      Coba Lagi
                    </button>
                  </div>
                ) : ocrResult ? (
                  ocrResult.full_text ? (
                    <div className="space-y-4">
                      {ocrResult.pages.map((page) => (
                        <div key={page.page_number} className="space-y-2">
                          {ocrResult.pages.length > 1 && (
                            <div className="text-[11px] font-semibold text-muted-foreground pb-1 border-b border-border/50">
                              Halaman {page.page_number} (Akurasi: {(page.confidence * 100).toFixed(1)}%)
                            </div>
                          )}
                          <pre className="font-mono text-xs leading-relaxed text-foreground whitespace-pre-wrap break-words bg-muted/20 p-3 rounded-md border border-border/50">
                            {page.text}
                          </pre>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-14 text-center text-muted-foreground gap-1.5">
                      <FileText size={32} className="text-muted-foreground/60" />
                      <p className="text-xs font-medium">Tidak ada teks terdeteksi</p>
                      <p className="text-[11px]">Gambar atau dokumen ini tidak mengandung teks yang dapat dibaca.</p>
                    </div>
                  )
                ) : null}
              </div>
            </div>
          ) : loading ? (
            <div className="flex flex-col items-center justify-center gap-2 p-12 text-muted-foreground">
              <Loader2 size={32} className="animate-spin text-primary" />
              <p className="text-xs">Memuat pratinjau berkas terenkapsulasi...</p>
            </div>
          ) : previewError ? (
            <div className="flex flex-col items-center justify-center gap-2 p-8 max-w-md text-center">
              <AlertCircle size={36} className="text-amber-500 mb-1" />
              <h4 className="text-sm font-semibold text-foreground">Tidak Dapat Menampilkan Pratinjau</h4>
              <p className="text-xs text-muted-foreground">{previewError}</p>
            </div>
          ) : isImage && blobUrl ? (
            <div className="flex items-center justify-center p-4 overflow-auto w-full h-full">
              <img
                src={blobUrl}
                alt={item.name}
                style={{
                  transform: `scale(${zoom / 100})`,
                  transformOrigin: "center center",
                }}
                className="max-h-[500px] max-w-full object-contain rounded-lg border border-border shadow-sm select-none transition-transform duration-100"
              />
            </div>
          ) : isTextOrCode && textContent !== null ? (
            <div className="w-full h-full flex flex-col rounded-lg border border-border bg-muted/20 overflow-hidden">
              <div className="flex items-center justify-between border-b border-border/80 px-4 py-2 bg-muted/40 text-[11px] text-muted-foreground">
                <span>
                  {textMeta?.lines || 0} baris • Ditampilkan {formatSize(textMeta?.bytes || 0)}
                </span>
                {textMeta?.truncated && (
                  <span className="text-amber-500 font-medium">
                    (Terpotong pada batas 64 KB)
                  </span>
                )}
              </div>
              <div className="flex-1 overflow-auto p-4 font-mono text-xs leading-relaxed text-foreground select-text max-h-[500px]">
                <pre className="whitespace-pre break-words">{textContent}</pre>
              </div>
            </div>
          ) : (
            /* Metadata fallback view for binary, unsupported or other categories */
            <div className="w-full max-w-lg rounded-lg border border-border p-6 bg-card space-y-4 shadow-sm">
              <div className="flex items-center gap-3">
                <div className="p-3 rounded-lg bg-primary/10 text-primary">
                  <FileIcon
                    itemType={item.item_type}
                    category={item.category}
                    extension={item.extension}
                    size={36}
                  />
                </div>
                <div>
                  <h4 className="font-semibold text-base truncate max-w-sm">{item.name}</h4>
                  <p className="text-xs text-muted-foreground">
                    {item.mime_type || `${item.category.toUpperCase()} File`}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3 pt-4 border-t border-border/60 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[11px]">Size</span>
                  <span className="font-medium text-foreground">{formatSize(item.size_bytes)}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Category</span>
                  <span className="font-medium text-foreground capitalize">{item.category}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Modified</span>
                  <span className="font-medium text-foreground">{item.modified_at || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[11px]">Confinement</span>
                  <span className="font-medium text-emerald-600">Verified & In-Scope</span>
                </div>
              </div>

              <div className="pt-2 text-xs">
                <span className="text-muted-foreground block text-[11px]">Full Path</span>
                <span className="font-mono text-[11px] text-foreground/80 break-all bg-muted/40 p-2 rounded block mt-1 border border-border/50">
                  {fullPath}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="flex items-center justify-between border-t border-border px-5 py-3 bg-muted/20 text-xs text-muted-foreground">
          <span>Terenkapsulasi secara aman di dalam batas Managed Folder</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-md border border-border bg-card hover:bg-muted font-medium text-foreground transition-colors"
          >
            Tutup
          </button>
        </div>
      </div>
    </div>
  );
};
