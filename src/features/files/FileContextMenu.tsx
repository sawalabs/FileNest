import React, { useEffect, useRef, useState, useLayoutEffect } from "react";
import {
  Eye,
  FolderOpen,
  Pencil,
  Trash2,
  Copy,
  FolderInput,
  Sparkles,
  ClipboardCopy,
  Info,
} from "lucide-react";
import type { FileItemMetadata } from "@/types";

export interface FileContextMenuProps {
  x: number;
  y: number;
  item: FileItemMetadata;
  selectedCount?: number;
  onClose: () => void;
  onOpen: (item: FileItemMetadata) => void;
  onRename: (item: FileItemMetadata) => void;
  onOCRRename?: (item: FileItemMetadata) => void;
  onDelete: (item: FileItemMetadata) => void;
  onCopy: (item: FileItemMetadata) => void;
  onMove: (item: FileItemMetadata) => void;
  onOCR?: (item: FileItemMetadata) => void;
  onCopyPath: (item: FileItemMetadata) => void;
  onAskAI?: (item: FileItemMetadata) => void;
  onShowDetails?: (item: FileItemMetadata) => void;
}

export const FileContextMenu: React.FC<FileContextMenuProps> = ({
  x,
  y,
  item,
  selectedCount = 1,
  onClose,
  onOpen,
  onRename,
  onOCRRename,
  onDelete,
  onCopy,
  onMove,
  onOCR,
  onCopyPath,
  onAskAI,
  onShowDetails,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const [coords, setCoords] = useState<{ top: number; left: number }>({ top: y, left: x });

  // Viewport boundary adjustment
  useLayoutEffect(() => {
    if (!menuRef.current) return;
    const rect = menuRef.current.getBoundingClientRect();
    const padding = 8;
    let nextLeft = x;
    let nextTop = y;

    if (x + rect.width > window.innerWidth - padding) {
      nextLeft = Math.max(padding, window.innerWidth - rect.width - padding);
    }
    if (y + rect.height > window.innerHeight - padding) {
      nextTop = Math.max(padding, window.innerHeight - rect.height - padding);
    }

    setCoords({ top: nextTop, left: nextLeft });
  }, [x, y]);

  // Click outside and keydown listeners to dismiss
  useEffect(() => {
    const handleMouseDown = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    const handleScroll = () => {
      onClose();
    };

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("keydown", handleKeyDown);
    window.addEventListener("scroll", handleScroll, true);
    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("scroll", handleScroll, true);
    };
  }, [onClose]);

  const isDirectory = item.item_type === "directory";
  const ext = item.extension?.toLowerCase() || "";
  const isImageOrPdf =
    item.category === "image" ||
    ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "pdf"].includes(ext);

  return (
    <div
      ref={menuRef}
      style={{
        top: `${coords.top}px`,
        left: `${coords.left}px`,
      }}
      className="fixed z-50 min-w-[220px] bg-white dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-800 rounded-lg shadow-2xl py-1 text-xs select-none animate-in fade-in-50 zoom-in-95 duration-100"
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => {
        e.preventDefault();
        e.stopPropagation();
      }}
    >
      {/* Header with item name */}
      <div className="px-3 py-1.5 border-b border-zinc-100 dark:border-zinc-800 text-zinc-500 dark:text-zinc-400 font-medium truncate max-w-[230px]">
        {item.name}
      </div>

      <div className="py-1">
        {/* Open / Preview */}
        <button
          onClick={() => {
            onClose();
            onOpen(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
        >
          {isDirectory ? (
            <FolderOpen size={14} className="text-primary" />
          ) : (
            <Eye size={14} className="text-primary" />
          )}
          <span>{isDirectory ? "Buka Folder" : "Buka / Pratinjau"}</span>
        </button>

        {/* OCR / Extract text for image or PDF */}
        {!isDirectory && isImageOrPdf && onOCR && (
          <button
            onClick={() => {
              onClose();
              onOCR(item);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
          >
            <Sparkles size={14} className="text-amber-500" />
            <span>Ekstrak Teks (OCR)</span>
          </button>
        )}
      </div>

      <div className="h-px bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800 my-0.5" />

      <div className="py-1">
        {/* Rename Manual */}
        <button
          onClick={() => {
            onClose();
            onRename(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
        >
          <Pencil size={14} className="text-muted-foreground" />
          <span>Ubah Nama</span>
        </button>

        {/* Smart Rename with OCR + AI */}
        {!isDirectory && onOCRRename && (
          <button
            onClick={() => {
              onClose();
              onOCRRename(item);
            }}
            className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
          >
            <div className="flex items-center gap-2.5">
              <Sparkles size={14} className="text-amber-500" />
              <span>Rename Otomatis (OCR + AI)</span>
            </div>
            <span className="text-[10px] font-semibold px-1 py-0.2 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
              AI
            </span>
          </button>
        )}

        {/* Copy to */}
        <button
          onClick={() => {
            onClose();
            onCopy(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
        >
          <Copy size={14} className="text-muted-foreground" />
          <span>
            {selectedCount > 1 ? `Salin (${selectedCount} item)` : "Salin ke..."}
          </span>
        </button>

        {/* Move to */}
        <button
          onClick={() => {
            onClose();
            onMove(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
        >
          <FolderInput size={14} className="text-muted-foreground" />
          <span>
            {selectedCount > 1 ? `Pindahkan (${selectedCount} item)` : "Pindahkan ke..."}
          </span>
        </button>

        {/* Copy Path */}
        <button
          onClick={() => {
            onClose();
            onCopyPath(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
        >
          <ClipboardCopy size={14} className="text-muted-foreground" />
          <span>Salin Path Lengkap</span>
        </button>
      </div>

      <div className="h-px bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800 my-0.5" />

      <div className="py-1">
        {/* Ask AI */}
        {onAskAI && (
          <button
            onClick={() => {
              onClose();
              onAskAI(item);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
          >
            <Sparkles size={14} className="text-indigo-500" />
            <span>Tanya AI tentang berkas ini</span>
          </button>
        )}

        {/* Show Details */}
        {onShowDetails && (
          <button
            onClick={() => {
              onClose();
              onShowDetails(item);
            }}
            className="w-full flex items-center gap-2.5 px-3 py-1.5 hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-700 dark:text-zinc-200 hover:text-zinc-900 dark:hover:text-zinc-50 text-left transition-colors"
          >
            <Info size={14} className="text-muted-foreground" />
            <span>Detail & Properti</span>
          </button>
        )}
      </div>

      <div className="h-px bg-zinc-100 dark:border-zinc-800 dark:bg-zinc-800 my-0.5" />

      <div className="py-1">
        {/* Delete */}
        <button
          onClick={() => {
            onClose();
            onDelete(item);
          }}
          className="w-full flex items-center gap-2.5 px-3 py-1.5 text-destructive hover:bg-destructive/10 hover:text-destructive text-left transition-colors"
        >
          <Trash2 size={14} />
          <span>
            {selectedCount > 1
              ? `Hapus ke Recycle Bin (${selectedCount})`
              : "Hapus ke Recycle Bin"}
          </span>
        </button>
      </div>
    </div>
  );
};
