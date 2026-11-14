import React, { useState, useEffect, useMemo, useRef, useCallback } from "react";
import {
  Folder,
  FolderOpen,
  FolderTree,
  FolderPlus,
  RefreshCw,
  Search,
  List,
  Grid,
  Info,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  ChevronRight,
  ChevronDown,
  Trash2,
  Copy,
  FolderInput,
  Pencil,
  CheckSquare,
  Square,
  AlertCircle,
  HardDrive,
  X,
  ZoomIn,
  ZoomOut,
  Sparkles,
} from "lucide-react";
import { FileIcon } from "./FileIcon";
import { FileContextMenu } from "./FileContextMenu";
import { CreateFolderModal } from "./CreateFolderModal";
import { RenameModal } from "./RenameModal";
import { DeleteConfirmModal } from "./DeleteConfirmModal";
import { MoveCopyModal } from "./MoveCopyModal";
import { FilePreviewModal } from "./FilePreviewModal";
import { FileDetailsPanel } from "./FileDetailsPanel";
import { UnregisterFolderModal } from "./UnregisterFolderModal";
import { ApiService } from "@/services/api";
import { usePreferences } from "@/contexts/PreferencesContext";
import type {
  DirectoryListingResponse,
  FileItemMetadata,
  ManagedFolder,
} from "@/types";

interface SubfolderNode {
  name: string;
  relative_path: string;
}

interface FilesManagerProps {
  onOpenAssistant?: (context: {
    folderId?: string | null;
    targetType?: "general" | "file" | "folder" | "plan" | "analysis";
    relativePath?: string | null;
    entityId?: string | null;
    autoPrompt?: string | null;
  }) => void;
  initialNavigationTarget?: {
    folderId: string;
    relativePath: string;
  } | null;
  onClearInitialNavigation?: () => void;
}

export const FilesManager: React.FC<FilesManagerProps> = ({
  onOpenAssistant,
  initialNavigationTarget,
  onClearInitialNavigation,
}) => {
  // Folder & navigation state
  const [folders, setFolders] = useState<ManagedFolder[]>([]);
  const [selectedFolderId, setSelectedFolderId] = useState<string>(
    () => initialNavigationTarget?.folderId || ""
  );
  const [currentPath, setCurrentPath] = useState<string>("");
  const [history, setHistory] = useState<string[]>([""]);
  const [historyIndex, setHistoryIndex] = useState<number>(0);
  const pendingLocatePathRef = useRef<string | null>(null);

  // Left navigation tree subfolders cache & expand state
  const [expandedTreeKeys, setExpandedTreeKeys] = useState<Set<string>>(new Set());
  const [treeSubfolderCache, setTreeSubfolderCache] = useState<Record<string, SubfolderNode[]>>({});
  const [loadingTreeKeys, setLoadingTreeKeys] = useState<Set<string>>(new Set());

  // Listing data & loading
  const [listing, setListing] = useState<DirectoryListingResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successToast, setSuccessToast] = useState<string | null>(null);

  // Preferences from Global Context
  const {
    defaultFileView,
    defaultTableDensity,
    showHiddenFiles,
    showFileExtensions,
  } = usePreferences();

  // View & UI controls
  const [viewMode, setViewMode] = useState<"list" | "grid">(defaultFileView);
  const [gridZoom, setGridZoom] = useState<number>(130); // 90px to 190px
  const [showDetails, setShowDetails] = useState<boolean>(true);
  const [showHidden, setShowHidden] = useState<boolean>(showHiddenFiles);
  const [sortBy, setSortBy] = useState<"name" | "size" | "modified">("name");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");

  // Keep viewMode and showHidden in sync with global preferences when they change
  useEffect(() => {
    setViewMode(defaultFileView);
  }, [defaultFileView]);

  useEffect(() => {
    setShowHidden(showHiddenFiles);
  }, [showHiddenFiles]);

  // Filtering & search
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sizeFilter, setSizeFilter] = useState<string>("all");
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  // Selection
  const [selectedPaths, setSelectedPaths] = useState<Set<string>>(new Set());
  const [activeItem, setActiveItem] = useState<FileItemMetadata | null>(null);

  // Modals state
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [renameTarget, setRenameTarget] = useState<FileItemMetadata | null>(null);
  const [deleteTargets, setDeleteTargets] = useState<FileItemMetadata[]>([]);
  const [moveCopyConfig, setMoveCopyConfig] = useState<{
    isOpen: boolean;
    mode: "move" | "copy";
    items: FileItemMetadata[];
  }>({ isOpen: false, mode: "move", items: [] });
  const [previewItem, setPreviewItem] = useState<FileItemMetadata | null>(null);
  const [previewInitialTab, setPreviewInitialTab] = useState<"preview" | "ocr">("preview");
  const [folderToUnregister, setFolderToUnregister] = useState<ManagedFolder | null>(null);

  // Context Menu state
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    item: FileItemMetadata;
  } | null>(null);

  const handleItemContextMenu = (item: FileItemMetadata, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    // If item is not in selectedPaths, select only this item (Windows Explorer behavior)
    if (!selectedPaths.has(item.relative_path)) {
      setSelectedPaths(new Set([item.relative_path]));
    }
    setActiveItem(item);

    setContextMenu({
      x: e.clientX,
      y: e.clientY,
      item,
    });
  };

  const handleOpenItem = (item: FileItemMetadata) => {
    if (item.item_type === "directory") {
      navigateTo(item.relative_path);
    } else {
      setPreviewInitialTab("preview");
      setPreviewItem(item);
    }
  };

  const handleOCRItem = (item: FileItemMetadata) => {
    setPreviewInitialTab("ocr");
    setPreviewItem(item);
  };

  const handleRenameItem = (item: FileItemMetadata) => {
    setRenameTarget(item);
  };

  const handleDeleteItem = (item: FileItemMetadata) => {
    if (selectedPaths.has(item.relative_path) && selectedPaths.size > 1) {
      const targets = filteredItems.filter((i) => selectedPaths.has(i.relative_path));
      setDeleteTargets(targets);
    } else {
      setDeleteTargets([item]);
    }
  };

  const handleCopyItem = (item: FileItemMetadata) => {
    if (selectedPaths.has(item.relative_path) && selectedPaths.size > 1) {
      const targets = filteredItems.filter((i) => selectedPaths.has(i.relative_path));
      setMoveCopyConfig({ isOpen: true, mode: "copy", items: targets });
    } else {
      setMoveCopyConfig({ isOpen: true, mode: "copy", items: [item] });
    }
  };

  const handleMoveItem = (item: FileItemMetadata) => {
    if (selectedPaths.has(item.relative_path) && selectedPaths.size > 1) {
      const targets = filteredItems.filter((i) => selectedPaths.has(i.relative_path));
      setMoveCopyConfig({ isOpen: true, mode: "move", items: targets });
    } else {
      setMoveCopyConfig({ isOpen: true, mode: "move", items: [item] });
    }
  };

  const handleCopyPath = async (item: FileItemMetadata) => {
    try {
      const fullPath = currentManagedFolder?.root_path
        ? (item.relative_path ? `${currentManagedFolder.root_path}\\${item.relative_path.replace(/\//g, '\\')}` : currentManagedFolder.root_path)
        : item.name;
      await navigator.clipboard.writeText(fullPath);
      showToast("Path file berhasil disalin ke clipboard!");
    } catch {
      showToast("Gagal menyalin path ke clipboard.");
    }
  };

  const handleAskAI = (item: FileItemMetadata) => {
    if (onOpenAssistant) {
      onOpenAssistant({
        folderId: selectedFolderId,
        targetType: item.item_type === "directory" ? "folder" : "file",
        relativePath: item.relative_path,
        autoPrompt: `Tolong jelaskan isi dan rekomendasi pengelolaan untuk berkas "${item.name}".`,
      });
    }
  };

  const handleShowDetails = (item: FileItemMetadata) => {
    setActiveItem(item);
    setShowDetails(true);
  };

  // Load registered Managed Folders on mount & listen to changes
  useEffect(() => {
    loadFolders();

    const handleFoldersChanged = () => {
      loadFolders();
    };
    const handleSelectFolder = (e: Event) => {
      const customEvent = e as CustomEvent<{ folderId: string }>;
      if (customEvent.detail?.folderId) {
        setSelectedFolderId(customEvent.detail.folderId);
        setCurrentPath("");
      }
    };

    window.addEventListener("folders-changed", handleFoldersChanged);
    window.addEventListener("select-managed-folder", handleSelectFolder);
    return () => {
      window.removeEventListener("folders-changed", handleFoldersChanged);
      window.removeEventListener("select-managed-folder", handleSelectFolder);
    };
  }, []);

  // Apply incoming deep-link navigation from Storage Analyzer or Global Command Palette
  useEffect(() => {
    if (!initialNavigationTarget?.folderId) return;
    const cleanRel = (initialNavigationTarget.relativePath || "")
      .replace(/\\/g, "/")
      .replace(/^\/+|\/+$/g, "");
    const lastSlash = cleanRel.lastIndexOf("/");
    const parentDir = lastSlash >= 0 ? cleanRel.slice(0, lastSlash) : "";

    setSelectedFolderId(initialNavigationTarget.folderId);
    setExpandedTreeKeys((prev) =>
      new Set(prev).add(`${initialNavigationTarget.folderId}:`)
    );

    if (
      selectedFolderId === initialNavigationTarget.folderId &&
      currentPath === parentDir &&
      listing
    ) {
      if (cleanRel) {
        const matched = listing.entries.find((e) => e.relative_path === cleanRel);
        if (matched) {
          setSelectedPaths(new Set([matched.relative_path]));
          setActiveItem(matched);
        }
      }
    } else {
      pendingLocatePathRef.current = cleanRel || null;
      setCurrentPath(parentDir);
      setHistory([parentDir]);
      setHistoryIndex(0);
    }

    onClearInitialNavigation?.();
  }, [initialNavigationTarget]);

  const handleUnregisterFolder = async (folder: ManagedFolder, permanent: boolean = true) => {
    try {
      await ApiService.unregisterFolder(folder.id, permanent);
      showToast(`Folder '${folder.name}' berhasil dihapus dari daftar FileNest.`);
      window.dispatchEvent(new Event("folders-changed"));
      const remainingFolders = folders.filter((f) => f.id !== folder.id);
      setFolders(remainingFolders);
      if (selectedFolderId === folder.id) {
        if (remainingFolders.length > 0) {
          setSelectedFolderId(remainingFolders[0].id);
          setCurrentPath("");
          setHistory([""]);
          setHistoryIndex(0);
        } else {
          setSelectedFolderId("");
          setCurrentPath("");
          setListing(null);
        }
      }
    } catch (err: unknown) {
      showToast(err instanceof Error ? err.message : "Gagal menghapus folder");
    }
  };

  const loadFolders = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const folderList = await ApiService.listFolders(true);
      setFolders(folderList);
      if (folderList.length > 0 && !selectedFolderId) {
        setSelectedFolderId(folderList[0].id);
        // Auto-expand root of first folder
        setExpandedTreeKeys((prev) => new Set(prev).add(`${folderList[0].id}:`));
        loadSubfolders(folderList[0].id, "");
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load managed folders");
    } finally {
      setIsLoading(false);
    }
  };

  // Browse directory whenever folder, currentPath, or listing options change
  useEffect(() => {
    if (selectedFolderId) {
      browseCurrentDirectory();
    }
  }, [selectedFolderId, currentPath, showHidden, sortBy, sortOrder]);

  const browseCurrentDirectory = async () => {
    if (!selectedFolderId) return;
    try {
      setIsLoading(true);
      setError(null);
      const res = await ApiService.browseDirectory(
        selectedFolderId,
        currentPath,
        showHidden,
        sortBy,
        sortOrder
      );
      setListing(res);
      const locatePath = pendingLocatePathRef.current;
      if (locatePath) {
        pendingLocatePathRef.current = null;
        const matched = res.entries.find((i) => i.relative_path === locatePath);
        if (matched) {
          setSelectedPaths(new Set([matched.relative_path]));
          setActiveItem(matched);
        } else {
          setSelectedPaths(new Set());
          setActiveItem(null);
        }
      } else {
        setSelectedPaths(new Set());
        if (activeItem) {
          const found = res.entries.find((i) => i.relative_path === activeItem.relative_path);
          setActiveItem(found || null);
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to browse directory");
    } finally {
      setIsLoading(false);
    }
  };

  // Subfolder tree loading
  const loadSubfolders = async (folderId: string, relPath: string) => {
    const key = `${folderId}:${relPath}`;
    if (loadingTreeKeys.has(key)) return;

    setLoadingTreeKeys((prev) => new Set(prev).add(key));
    try {
      const res = await ApiService.browseDirectory(folderId, relPath, false, "name", "asc");
      const subdirs: SubfolderNode[] = res.entries
        .filter((e) => e.item_type === "directory")
        .map((e) => ({
          name: e.name,
          relative_path: e.relative_path,
        }));
      setTreeSubfolderCache((prev) => ({ ...prev, [key]: subdirs }));
    } catch {
      // Ignore directory read failure in navigation tree
    } finally {
      setLoadingTreeKeys((prev) => {
        const next = new Set(prev);
        next.delete(key);
        return next;
      });
    }
  };

  const toggleTreeNodeExpand = (folderId: string, relPath: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const key = `${folderId}:${relPath}`;
    const nextExpanded = new Set(expandedTreeKeys);
    if (nextExpanded.has(key)) {
      nextExpanded.delete(key);
    } else {
      nextExpanded.add(key);
      if (!treeSubfolderCache[key]) {
        loadSubfolders(folderId, relPath);
      }
    }
    setExpandedTreeKeys(nextExpanded);
  };

  const showToast = (message: string) => {
    setSuccessToast(message);
    setTimeout(() => setSuccessToast(null), 3000);
  };

  // Navigation handlers
  const navigateTo = (newPath: string) => {
    const clean = newPath.replace(/^\/+|\/+$/g, "");
    if (clean === currentPath) return;

    const newHistory = history.slice(0, historyIndex + 1);
    newHistory.push(clean);
    setHistory(newHistory);
    setHistoryIndex(newHistory.length - 1);
    setCurrentPath(clean);
  };

  const navigateBack = () => {
    if (historyIndex > 0) {
      const newIdx = historyIndex - 1;
      setHistoryIndex(newIdx);
      setCurrentPath(history[newIdx]);
    }
  };

  const navigateForward = () => {
    if (historyIndex < history.length - 1) {
      const newIdx = historyIndex + 1;
      setHistoryIndex(newIdx);
      setCurrentPath(history[newIdx]);
    }
  };

  const navigateUp = () => {
    if (!currentPath) return;
    const parts = currentPath.split("/");
    parts.pop();
    navigateTo(parts.join("/"));
  };

  // Selected folder object
  const currentManagedFolder = useMemo(
    () => folders.find((f) => f.id === selectedFolderId) || null,
    [folders, selectedFolderId]
  );

  // Filtered items
  const filteredItems = useMemo(() => {
    if (!listing) return [];
    return listing.entries.filter((item) => {
      // 1. Search Query
      if (searchQuery.trim() && !item.name.toLowerCase().includes(searchQuery.toLowerCase())) {
        return false;
      }
      // 2. Category Filter
      if (categoryFilter !== "all" && item.item_type !== "directory") {
        if (item.category !== categoryFilter) return false;
      }
      // 3. Size Filter
      if (sizeFilter !== "all" && item.item_type !== "directory") {
        const bytes = item.size_bytes;
        if (sizeFilter === "<1mb" && bytes >= 1024 * 1024) return false;
        if (sizeFilter === "1-10mb" && (bytes < 1024 * 1024 || bytes >= 10 * 1024 * 1024)) return false;
        if (sizeFilter === "10-100mb" && (bytes < 10 * 1024 * 1024 || bytes >= 100 * 1024 * 1024)) return false;
        if (sizeFilter === "100mb-1gb" && (bytes < 100 * 1024 * 1024 || bytes >= 1024 * 1024 * 1024)) return false;
        if (sizeFilter === ">1gb" && bytes < 1024 * 1024 * 1024) return false;
      }
      return true;
    });
  }, [listing, searchQuery, categoryFilter, sizeFilter]);

  // Selection helpers
  const toggleSelect = (path: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const next = new Set(selectedPaths);
    if (next.has(path)) {
      next.delete(path);
    } else {
      next.add(path);
    }
    setSelectedPaths(next);
  };

  const selectAll = useCallback(() => {
    if (selectedPaths.size === filteredItems.length) {
      setSelectedPaths(new Set());
    } else {
      setSelectedPaths(new Set(filteredItems.map((i) => i.relative_path)));
    }
  }, [selectedPaths.size, filteredItems]);

  const selectedItemsList = useMemo(() => {
    if (!listing) return [];
    return listing.entries.filter((i) => selectedPaths.has(i.relative_path));
  }, [listing, selectedPaths]);

  const selectedTotalSize = useMemo(() => {
    return selectedItemsList.reduce((acc, curr) => acc + curr.size_bytes, 0);
  }, [selectedItemsList]);

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
  };

  // Breadcrumbs
  const breadcrumbSegments = useMemo(() => {
    if (!currentPath) return [];
    return currentPath.split("/");
  }, [currentPath]);

  // Native folder picker
  const handleAddManagedFolder = async () => {
    try {
      const { open } = await import("@tauri-apps/plugin-dialog");
      const selected = await open({
        directory: true,
        multiple: false,
        title: "Select Directory to Register as Managed Folder",
      });
      if (selected && typeof selected === "string") {
        const autoName = selected.split(/[\\/]/).filter(Boolean).pop() || "Managed Folder";
        const created = await ApiService.registerFolder({
          name: autoName,
          root_path: selected,
          monitoring_enabled: false,
          scan_on_startup: false,
          exclude_patterns: [],
        });
        showToast(`Folder '${created.name}' registered successfully.`);
        await loadFolders();
        setSelectedFolderId(created.id);
        navigateTo("");
        window.dispatchEvent(new Event("folders-changed"));
      }
    } catch {
      showToast("Gunakan menu Managed Folders di Settings untuk mendaftarkan folder.");
    }
  };

  // Mutation actions via Transaction Manager
  const handleCreateFolder = async (folderName: string) => {
    await ApiService.quickCreateFolder(selectedFolderId, currentPath, folderName);
    showToast(`Folder '${folderName}' created successfully.`);
    // Invalidate tree cache for current directory
    setTreeSubfolderCache((prev) => {
      const next = { ...prev };
      delete next[`${selectedFolderId}:${currentPath}`];
      return next;
    });
    browseCurrentDirectory();
  };

  const handleRename = async (sourcePath: string, newName: string) => {
    await ApiService.quickRename(selectedFolderId, sourcePath, newName);
    showToast(`Renamed to '${newName}'.`);
    setTreeSubfolderCache((prev) => {
      const next = { ...prev };
      delete next[`${selectedFolderId}:${currentPath}`];
      return next;
    });
    browseCurrentDirectory();
  };

  const handleDelete = async (relativePaths: string[]) => {
    await ApiService.quickDelete(selectedFolderId, relativePaths);
    showToast(`Moved ${relativePaths.length} item(s) to Recycle Bin.`);
    setTreeSubfolderCache((prev) => {
      const next = { ...prev };
      delete next[`${selectedFolderId}:${currentPath}`];
      return next;
    });
    browseCurrentDirectory();
  };

  const handleMove = async (sourcePaths: string[], destDir: string) => {
    await ApiService.quickMove(selectedFolderId, sourcePaths, destDir);
    showToast(`Moved ${sourcePaths.length} item(s) to ${destDir ? `/${destDir}` : "Root"}.`);
    setTreeSubfolderCache({});
    browseCurrentDirectory();
  };

  const handleCopy = async (sourcePaths: string[], destDir: string) => {
    await ApiService.quickCopy(selectedFolderId, sourcePaths, destDir);
    showToast(`Copied ${sourcePaths.length} item(s) to ${destDir ? `/${destDir}` : "Root"}.`);
    setTreeSubfolderCache({});
    browseCurrentDirectory();
  };

  // Keyboard Shortcuts Handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      const isInput = targetTag === "input" || targetTag === "textarea" || targetTag === "select";

      // Ctrl + K: Focus Search
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchInputRef.current?.focus();
        return;
      }

      if (isInput) return;

      // Ctrl + A: Select All
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a") {
        e.preventDefault();
        selectAll();
        return;
      }

      // F2: Rename
      if (e.key === "F2") {
        e.preventDefault();
        const target = selectedItemsList[0] || activeItem;
        if (target) {
          setRenameTarget(target);
        }
        return;
      }

      // Delete: Recycle Bin
      if (e.key === "Delete") {
        e.preventDefault();
        if (selectedItemsList.length > 0) {
          setDeleteTargets(selectedItemsList);
        } else if (activeItem) {
          setDeleteTargets([activeItem]);
        }
        return;
      }

      // Enter: Open Folder or Preview File
      if (e.key === "Enter" && activeItem) {
        e.preventDefault();
        if (activeItem.item_type === "directory") {
          navigateTo(activeItem.relative_path);
        } else {
          setPreviewItem(activeItem);
        }
        return;
      }

      // Escape: Clear selection / modal
      if (e.key === "Escape") {
        setSelectedPaths(new Set());
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeItem, selectedItemsList, selectAll]);

  // Target item for single-selection actions
  const singleActionItem = selectedItemsList.length === 1 ? selectedItemsList[0] : activeItem;

  return (
    <div className="flex h-full w-full bg-background select-none overflow-hidden">
      {/* ===================================================================== */}
      {/* 1. LEFT PANE (240px): Managed Folders & Subfolder Tree */}
      {/* ===================================================================== */}
      <aside className="w-60 border-r border-border bg-card/40 flex flex-col shrink-0 overflow-hidden">
        {/* Left Pane Header */}
        <div className="p-3.5 border-b border-border flex items-center justify-between gap-2 shrink-0 bg-card/70">
          <div className="flex items-center gap-2 min-w-0">
            <FolderTree size={16} className="text-primary shrink-0" />
            <h3 className="text-xs font-semibold text-foreground tracking-wide truncate">
              Managed Folders
            </h3>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-muted text-muted-foreground shrink-0">
              {folders.length}
            </span>
          </div>

          <button
            onClick={handleAddManagedFolder}
            title="Add Managed Folder"
            className="p-1 rounded-md text-muted-foreground hover:bg-muted hover:text-foreground transition-colors shrink-0"
          >
            <FolderPlus size={15} />
          </button>
        </div>

        {/* Folder Hierarchy Tree */}
        <div className="flex-1 overflow-y-auto p-2 space-y-0.5 text-xs">
          {folders.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-[11px]">
              <HardDrive size={28} className="mx-auto mb-2 text-muted-foreground/40" />
              <p>Belum ada folder terdaftar.</p>
              <button
                onClick={handleAddManagedFolder}
                className="mt-2 text-primary hover:underline font-medium inline-block"
              >
                + Tambah Folder
              </button>
            </div>
          ) : (
            folders.map((folder) => {
              const rootKey = `${folder.id}:`;
              const isFolderSelected = folder.id === selectedFolderId;
              const isRootActive = isFolderSelected && !currentPath;
              const isExpanded = expandedTreeKeys.has(rootKey);
              const subdirs = treeSubfolderCache[rootKey] || [];
              const isLoadingSubdirs = loadingTreeKeys.has(rootKey);

              return (
                <div key={folder.id} className="space-y-0.5">
                  {/* Root Folder Item */}
                  <div
                    onClick={() => {
                      setSelectedFolderId(folder.id);
                      navigateTo("");
                    }}
                    title={folder.root_path}
                    className={`group flex items-center gap-1.5 px-2 py-1.5 rounded-md cursor-pointer transition-colors ${
                      isRootActive
                        ? "bg-primary/10 text-primary font-medium border-l-2 border-primary"
                        : isFolderSelected
                        ? "bg-muted/60 text-foreground font-medium"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    }`}
                  >
                    <button
                      onClick={(e) => toggleTreeNodeExpand(folder.id, "", e)}
                      className="p-0.5 rounded hover:bg-muted/80 text-muted-foreground"
                    >
                      {isExpanded ? (
                        <ChevronDown size={14} />
                      ) : (
                        <ChevronRight size={14} />
                      )}
                    </button>

                    {isExpanded ? (
                      <FolderOpen size={15} className="text-amber-500 fill-amber-500/20 shrink-0" />
                    ) : (
                      <Folder size={15} className="text-amber-500 fill-amber-500/20 shrink-0" />
                    )}

                    <span className="truncate flex-1 text-left">{folder.name}</span>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setFolderToUnregister(folder);
                      }}
                      title="Hapus folder ini dari daftar FileNest"
                      className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>

                  {/* Subfolder list if expanded */}
                  {isExpanded && (
                    <div className="pl-5 space-y-0.5 border-l border-border/50 ml-3.5 my-0.5">
                      {isLoadingSubdirs ? (
                        <div className="px-2 py-1 text-[11px] text-muted-foreground/60 flex items-center gap-1.5">
                          <RefreshCw size={11} className="animate-spin" />
                          <span>Loading...</span>
                        </div>
                      ) : subdirs.length === 0 ? (
                        <div className="px-2 py-1 text-[11px] text-muted-foreground/50 italic">
                          (No subfolders)
                        </div>
                      ) : (
                        subdirs.map((sub) => {
                          const isSubActive =
                            isFolderSelected && currentPath === sub.relative_path;
                          const subKey = `${folder.id}:${sub.relative_path}`;
                          const isSubExpanded = expandedTreeKeys.has(subKey);
                          const nestedSubdirs = treeSubfolderCache[subKey] || [];

                          return (
                            <div key={sub.relative_path} className="space-y-0.5">
                              <div
                                onClick={() => {
                                  setSelectedFolderId(folder.id);
                                  navigateTo(sub.relative_path);
                                }}
                                title={sub.relative_path}
                                className={`group flex items-center gap-1 px-2 py-1 rounded cursor-pointer transition-colors text-xs ${
                                  isSubActive
                                    ? "bg-primary/10 text-primary font-medium border-l-2 border-primary"
                                    : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                                }`}
                              >
                                <button
                                  onClick={(e) =>
                                    toggleTreeNodeExpand(folder.id, sub.relative_path, e)
                                  }
                                  className="p-0.5 rounded text-muted-foreground/60 hover:text-foreground"
                                >
                                  {isSubExpanded ? (
                                    <ChevronDown size={12} />
                                  ) : (
                                    <ChevronRight size={12} />
                                  )}
                                </button>
                                <Folder size={13} className="text-amber-500/80 shrink-0" />
                                <span className="truncate flex-1 text-left">{sub.name}</span>

                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setDeleteTargets([
                                      {
                                        name: sub.name,
                                        relative_path: sub.relative_path,
                                        parent_relative_path: sub.relative_path.split("/").slice(0, -1).join("/"),
                                        item_type: "directory",
                                        category: "other",
                                        size_bytes: 0,
                                        modified_at: "",
                                        is_hidden: false,
                                        is_symlink: false,
                                        is_inaccessible: false,
                                      },
                                    ]);
                                  }}
                                  title="Pindahkan subfolder ke Recycle Bin"
                                  className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0"
                                >
                                  <Trash2 size={12} />
                                </button>
                              </div>

                              {/* Nested Subfolders if expanded */}
                              {isSubExpanded && nestedSubdirs.length > 0 && (
                                <div className="pl-4 space-y-0.5 border-l border-border/40 ml-2">
                                  {nestedSubdirs.map((nested) => {
                                    const isNestedActive =
                                      isFolderSelected && currentPath === nested.relative_path;
                                    return (
                                      <div
                                        key={nested.relative_path}
                                        onClick={() => {
                                          setSelectedFolderId(folder.id);
                                          navigateTo(nested.relative_path);
                                        }}
                                        className={`group flex items-center gap-1.5 px-2 py-1 rounded cursor-pointer transition-colors text-xs ${
                                          isNestedActive
                                            ? "bg-primary/10 text-primary font-medium border-l-2 border-primary"
                                            : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                                        }`}
                                      >
                                        <Folder size={12} className="text-amber-500/70 shrink-0" />
                                        <span className="truncate flex-1 text-left">{nested.name}</span>

                                        <button
                                          type="button"
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setDeleteTargets([
                                              {
                                                name: nested.name,
                                                relative_path: nested.relative_path,
                                                parent_relative_path: nested.relative_path.split("/").slice(0, -1).join("/"),
                                                item_type: "directory",
                                                category: "other",
                                                size_bytes: 0,
                                                modified_at: "",
                                                is_hidden: false,
                                                is_symlink: false,
                                                is_inaccessible: false,
                                              },
                                            ]);
                                          }}
                                          title="Pindahkan subfolder ke Recycle Bin"
                                          className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-all shrink-0"
                                        >
                                          <Trash2 size={12} />
                                        </button>
                                      </div>
                                    );
                                  })}
                                </div>
                              )}
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Left Pane Footer (Active Path Details) */}
        {currentManagedFolder && (
          <div className="p-2.5 border-t border-border bg-muted/20 text-[11px] text-muted-foreground shrink-0">
            <div className="truncate font-mono text-[10px]" title={currentManagedFolder.root_path}>
              {currentManagedFolder.root_path}
            </div>
          </div>
        )}
      </aside>

      {/* ===================================================================== */}
      {/* 2. CENTER PANE: Explorer Canvas + Address Bar + Toolbars */}
      {/* ===================================================================== */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden bg-background">
        {/* Top Breadcrumb & Action Toolbar */}
        <div className="px-4 py-2 border-b border-border bg-card/70 flex flex-wrap items-center justify-between gap-2 shrink-0">
          {/* Navigation arrows & Breadcrumbs */}
          <div className="flex items-center gap-1.5 flex-1 min-w-[280px]">
            <div className="flex items-center border border-border rounded-md bg-background overflow-hidden shrink-0">
              <button
                onClick={navigateBack}
                disabled={historyIndex <= 0}
                title="Back"
                className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 transition-colors"
              >
                <ArrowLeft size={14} />
              </button>
              <button
                onClick={navigateForward}
                disabled={historyIndex >= history.length - 1}
                title="Forward"
                className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 transition-colors border-l border-border"
              >
                <ArrowRight size={14} />
              </button>
              <button
                onClick={navigateUp}
                disabled={!currentPath}
                title="Up to Parent Directory"
                className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 transition-colors border-l border-border"
              >
                <ArrowUp size={14} />
              </button>
              <button
                onClick={browseCurrentDirectory}
                disabled={isLoading || !selectedFolderId}
                title="Refresh Directory"
                className="p-1.5 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30 transition-colors border-l border-border"
              >
                <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
              </button>
            </div>

            {/* Breadcrumb Path Bar */}
            <div className="flex items-center gap-1 text-xs overflow-x-auto whitespace-nowrap bg-background border border-border rounded-md px-2.5 py-1 flex-1 min-w-0">
              <button
                onClick={() => navigateTo("")}
                className={`hover:text-primary transition-colors flex items-center gap-1 font-medium ${
                  !currentPath ? "text-foreground font-semibold" : "text-muted-foreground"
                }`}
              >
                <Folder size={13} className="text-amber-500 fill-amber-500/20" />
                <span>{currentManagedFolder?.name || "Root"}</span>
              </button>

              {breadcrumbSegments.map((segment, idx) => {
                const segmentPath = breadcrumbSegments.slice(0, idx + 1).join("/");
                const isLast = idx === breadcrumbSegments.length - 1;
                return (
                  <React.Fragment key={segmentPath}>
                    <ChevronRight size={12} className="text-muted-foreground/50 shrink-0" />
                    <button
                      onClick={() => navigateTo(segmentPath)}
                      className={`hover:text-primary transition-colors truncate max-w-[130px] ${
                        isLast ? "text-foreground font-semibold" : "text-muted-foreground"
                      }`}
                      title={segment}
                    >
                      {segment}
                    </button>
                  </React.Fragment>
                );
              })}
            </div>
          </div>

          {/* Action Toolbar */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Unregister Folder from FileNest (Available at Root) */}
            {!currentPath && currentManagedFolder && (
              <button
                type="button"
                onClick={() => setFolderToUnregister(currentManagedFolder)}
                className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs rounded-md border border-border bg-background hover:bg-destructive/10 hover:text-destructive hover:border-destructive/30 text-muted-foreground transition-colors shrink-0"
                title="Hapus folder ini dari daftar FileNest (berkas fisik di disk tidak dihapus)"
              >
                <Trash2 size={13} />
                <span className="hidden sm:inline">Hapus Folder</span>
              </button>
            )}

            {/* AI Assistant */}
            <button
              type="button"
              onClick={() =>
                onOpenAssistant?.({
                  folderId: selectedFolderId,
                  targetType: singleActionItem
                    ? singleActionItem.item_type === "directory"
                      ? "folder"
                      : "file"
                    : currentPath
                    ? "folder"
                    : "general",
                  relativePath: singleActionItem
                    ? singleActionItem.relative_path
                    : currentPath || undefined,
                  autoPrompt: singleActionItem
                    ? `Analisis dan berikan rekomendasi penataan untuk '${singleActionItem.name}'`
                    : currentPath
                    ? `Analisis isi subfolder '${currentPath}'`
                    : "Tolong rapikan dan kelompokkan berkas lepas di folder ini.",
                })
              }
              disabled={!selectedFolderId}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-semibold rounded-md bg-primary/10 hover:bg-primary/20 text-primary border border-primary/25 transition-colors shadow-2xs disabled:opacity-40"
              title="Buka AI Assistant untuk analisis dan rekomendasi penataan cerdas"
            >
              <Sparkles size={13} />
              <span className="hidden sm:inline">AI Assistant</span>
            </button>

            {/* + New Folder */}
            <button
              onClick={() => setIsCreateOpen(true)}
              disabled={!selectedFolderId}
              className="inline-flex items-center gap-1 px-2.5 py-1.5 text-xs font-medium rounded-md bg-primary text-primary-foreground hover:bg-primary/90 transition-colors shadow-xs disabled:opacity-50"
              title="New Folder (Ctrl+Shift+N)"
            >
              <FolderPlus size={14} />
              <span>New Folder</span>
            </button>

            {/* Rename (F2) */}
            <button
              onClick={() => singleActionItem && setRenameTarget(singleActionItem)}
              disabled={!singleActionItem}
              className="inline-flex items-center gap-1 px-2 py-1.5 text-xs rounded-md border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-40"
              title="Rename (F2)"
            >
              <Pencil size={13} />
              <span>Rename</span>
            </button>

            {/* Move */}
            <button
              onClick={() =>
                setMoveCopyConfig({
                  isOpen: true,
                  mode: "move",
                  items: selectedItemsList.length > 0 ? selectedItemsList : activeItem ? [activeItem] : [],
                })
              }
              disabled={selectedItemsList.length === 0 && !activeItem}
              className="inline-flex items-center gap-1 px-2 py-1.5 text-xs rounded-md border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-40"
              title="Move Items"
            >
              <FolderInput size={13} />
              <span>Move</span>
            </button>

            {/* Copy */}
            <button
              onClick={() =>
                setMoveCopyConfig({
                  isOpen: true,
                  mode: "copy",
                  items: selectedItemsList.length > 0 ? selectedItemsList : activeItem ? [activeItem] : [],
                })
              }
              disabled={selectedItemsList.length === 0 && !activeItem}
              className="inline-flex items-center gap-1 px-2 py-1.5 text-xs rounded-md border border-border bg-background hover:bg-muted text-foreground transition-colors disabled:opacity-40"
              title="Copy Items"
            >
              <Copy size={13} />
              <span>Copy</span>
            </button>

            {/* Delete (Recycle Bin) */}
            <button
              onClick={() =>
                setDeleteTargets(
                  selectedItemsList.length > 0 ? selectedItemsList : activeItem ? [activeItem] : []
                )
              }
              disabled={selectedItemsList.length === 0 && !activeItem}
              className="inline-flex items-center gap-1 px-2 py-1.5 text-xs rounded-md bg-destructive/10 border border-destructive/20 text-destructive hover:bg-destructive/20 transition-colors disabled:opacity-40"
              title="Delete to Recycle Bin (Del)"
            >
              <Trash2 size={13} />
              <span>Delete</span>
            </button>

            <div className="h-4 w-[1px] bg-border mx-0.5" />

            {/* Toggle Details Panel */}
            <button
              onClick={() => setShowDetails(!showDetails)}
              className={`p-1.5 rounded-md border border-border transition-colors ${
                showDetails
                  ? "bg-primary/10 text-primary border-primary/30"
                  : "bg-background text-muted-foreground hover:bg-muted"
              }`}
              title="Toggle Details Panel"
            >
              <Info size={14} />
            </button>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="px-4 py-2 border-b border-border bg-muted/20 flex flex-wrap items-center justify-between gap-2 shrink-0">
          <div className="flex items-center gap-2 flex-1 max-w-xl">
            {/* Search Box */}
            <div className="relative flex-1">
              <Search
                size={14}
                className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground pointer-events-none"
              />
              <input
                ref={searchInputRef}
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search files... (Ctrl + K)"
                className="w-full pl-8 pr-7 py-1 rounded-md border border-input bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X size={12} />
                </button>
              )}
            </div>

            {/* Category Filter */}
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-xs rounded-md border border-border bg-background px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary text-foreground"
            >
              <option value="all">All Types</option>
              <option value="document">Documents</option>
              <option value="image">Images</option>
              <option value="video">Videos</option>
              <option value="audio">Audio</option>
              <option value="archive">Archives</option>
              <option value="code">Code</option>
              <option value="other">Other</option>
            </select>

            {/* Size Filter */}
            <select
              value={sizeFilter}
              onChange={(e) => setSizeFilter(e.target.value)}
              className="text-xs rounded-md border border-border bg-background px-2 py-1 focus:outline-none focus:ring-1 focus:ring-primary text-foreground"
            >
              <option value="all">All Sizes</option>
              <option value="<1mb">&lt; 1 MB</option>
              <option value="1-10mb">1 – 10 MB</option>
              <option value="10-100mb">10 – 100 MB</option>
              <option value="100mb-1gb">100 MB – 1 GB</option>
              <option value=">1gb">&gt; 1 GB</option>
            </select>
          </div>

          {/* Show hidden toggle */}
          <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer select-none">
            <input
              type="checkbox"
              checked={showHidden}
              onChange={(e) => setShowHidden(e.target.checked)}
              className="rounded border-border text-primary focus:ring-primary"
            />
            <span>Show Hidden</span>
          </label>
        </div>

        {/* Toast Notification */}
        {successToast && (
          <div className="mx-4 mt-2 px-3 py-1.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-xs flex items-center justify-between animate-in fade-in">
            <span>{successToast}</span>
            <button onClick={() => setSuccessToast(null)}>
              <X size={13} />
            </button>
          </div>
        )}

        {/* Error Banner */}
        {error && (
          <div className="mx-4 mt-2 px-3 py-2 rounded-md bg-destructive/10 border border-destructive/20 text-destructive text-xs flex items-center gap-2">
            <AlertCircle size={14} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Multi-Selection Banner */}
        {selectedPaths.size > 0 && (
          <div className="px-4 py-1.5 bg-primary/10 border-b border-primary/20 flex items-center justify-between gap-4 text-xs shrink-0">
            <span className="font-semibold text-primary">
              {selectedPaths.size} item{selectedPaths.size > 1 ? "s" : ""} selected ({formatSize(selectedTotalSize)})
            </span>
            <div className="flex items-center gap-2">
              <button
                onClick={() =>
                  setMoveCopyConfig({
                    isOpen: true,
                    mode: "copy",
                    items: selectedItemsList,
                  })
                }
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-background border border-border hover:bg-muted text-foreground transition-colors"
              >
                <Copy size={12} />
                <span>Copy</span>
              </button>
              <button
                onClick={() =>
                  setMoveCopyConfig({
                    isOpen: true,
                    mode: "move",
                    items: selectedItemsList,
                  })
                }
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-background border border-border hover:bg-muted text-foreground transition-colors"
              >
                <FolderInput size={12} />
                <span>Move</span>
              </button>
              <button
                onClick={() => setDeleteTargets(selectedItemsList)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-destructive/10 border border-destructive/20 text-destructive hover:bg-destructive/20 transition-colors"
              >
                <Trash2 size={12} />
                <span>Delete</span>
              </button>
              <button
                onClick={() => setSelectedPaths(new Set())}
                className="p-1 rounded text-muted-foreground hover:bg-muted ml-1"
                title="Clear Selection"
              >
                <X size={13} />
              </button>
            </div>
          </div>
        )}

        {/* Main Canvas Area */}
        <div className="flex-1 overflow-auto p-4 min-h-0">
          {folders.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <HardDrive size={44} className="text-muted-foreground/30 mb-3" />
              <h3 className="text-base font-semibold text-foreground">No Registered Folders</h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                Register a Managed Folder in Settings to begin safely exploring and organizing your files.
              </p>
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center p-8">
              <Folder size={44} className="text-muted-foreground/30 mb-3" />
              <h3 className="text-base font-semibold text-foreground">
                {searchQuery || categoryFilter !== "all" || sizeFilter !== "all"
                  ? "No files match your filters"
                  : "This folder is empty"}
              </h3>
              <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                {searchQuery || categoryFilter !== "all"
                  ? "Try adjusting your search query or reset filter options."
                  : "Create a new folder or add files within this managed directory."}
              </p>
            </div>
          ) : viewMode === "list" ? (
            /* LIST VIEW */
            <div className="rounded-lg border border-border overflow-hidden bg-card">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-border bg-muted/40 font-semibold text-muted-foreground">
                    <th className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} w-10 text-center`}>
                      <button
                        onClick={selectAll}
                        className="text-muted-foreground hover:text-foreground inline-flex items-center justify-center"
                        title="Select All (Ctrl+A)"
                      >
                        {selectedPaths.size === filteredItems.length && filteredItems.length > 0 ? (
                          <CheckSquare size={15} className="text-primary" />
                        ) : (
                          <Square size={15} />
                        )}
                      </button>
                    </th>
                    <th
                      onClick={() => {
                        if (sortBy === "name") setSortOrder(sortOrder === "asc" ? "desc" : "asc");
                        else {
                          setSortBy("name");
                          setSortOrder("asc");
                        }
                      }}
                      className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} cursor-pointer hover:text-foreground`}
                    >
                      Name {sortBy === "name" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th
                      onClick={() => {
                        if (sortBy === "size") setSortOrder(sortOrder === "asc" ? "desc" : "asc");
                        else {
                          setSortBy("size");
                          setSortOrder("asc");
                        }
                      }}
                      className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} w-28 cursor-pointer hover:text-foreground text-right`}
                    >
                      Size {sortBy === "size" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} w-32`}>Type</th>
                    <th
                      onClick={() => {
                        if (sortBy === "modified") setSortOrder(sortOrder === "asc" ? "desc" : "asc");
                        else {
                          setSortBy("modified");
                          setSortOrder("asc");
                        }
                      }}
                      className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} w-40 cursor-pointer hover:text-foreground`}
                    >
                      Modified {sortBy === "modified" && (sortOrder === "asc" ? "↑" : "↓")}
                    </th>
                    <th className={`${defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5"} w-12 text-center`}></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border/60">
                  {filteredItems.map((item) => {
                    const isSelected = selectedPaths.has(item.relative_path);
                    const isActive = activeItem?.relative_path === item.relative_path;
                    const cellPad = defaultTableDensity === "compact" ? "px-2.5 py-1.5" : "p-2.5";
                    const itemDisplayName =
                      !showFileExtensions && item.item_type === "file" && item.extension
                        ? item.name.slice(0, -(item.extension.length + 1))
                        : item.name;

                    return (
                      <tr
                        key={item.relative_path}
                        onClick={() => setActiveItem(item)}
                        onDoubleClick={() => {
                          if (item.item_type === "directory") {
                            navigateTo(item.relative_path);
                          } else {
                            setPreviewInitialTab("preview");
                            setPreviewItem(item);
                          }
                        }}
                        onContextMenu={(e) => handleItemContextMenu(item, e)}
                        className={`group cursor-pointer transition-colors ${
                          isSelected
                            ? "bg-primary/10"
                            : isActive
                            ? "bg-muted/70"
                            : "hover:bg-muted/40"
                        }`}
                      >
                        <td
                          className={`${cellPad} text-center`}
                          onClick={(e) => toggleSelect(item.relative_path, e)}
                        >
                          {isSelected ? (
                            <CheckSquare size={15} className="text-primary inline" />
                          ) : (
                            <Square
                              size={15}
                              className="text-muted-foreground/50 group-hover:text-muted-foreground inline"
                            />
                          )}
                        </td>
                        <td className={`${cellPad} font-medium text-foreground`}>
                          <div className="flex items-center gap-2 truncate max-w-md">
                            <FileIcon
                              itemType={item.item_type}
                              category={item.category}
                              extension={item.extension}
                              size={16}
                            />
                            <span className="truncate" title={item.name}>
                              {itemDisplayName}
                            </span>
                          </div>
                        </td>
                        <td className={`${cellPad} text-right text-muted-foreground font-mono text-[11px]`}>
                          {item.item_type === "directory" ? "—" : formatSize(item.size_bytes)}
                        </td>
                        <td className={`${cellPad} text-muted-foreground capitalize text-[11px]`}>
                          {item.item_type === "directory"
                            ? "Folder"
                            : item.extension
                            ? `${item.extension.toUpperCase()} File`
                            : item.category}
                        </td>
                        <td className={`${cellPad} text-muted-foreground font-mono text-[11px]`}>
                          {item.modified_at || "—"}
                        </td>
                        <td className={`${cellPad} text-center`}>
                          <div className="flex items-center justify-end gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setRenameTarget(item);
                              }}
                              title="Rename"
                              className="p-1 rounded text-muted-foreground hover:bg-muted hover:text-foreground"
                            >
                              <Pencil size={12} />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setDeleteTargets([item]);
                              }}
                              title="Delete"
                              className="p-1 rounded text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            /* GRID VIEW WITH DYNAMIC ZOOM */
            <div
              className="grid gap-3"
              style={{
                gridTemplateColumns: `repeat(auto-fill, minmax(${gridZoom}px, 1fr))`,
              }}
            >
              {filteredItems.map((item) => {
                const isSelected = selectedPaths.has(item.relative_path);
                const isActive = activeItem?.relative_path === item.relative_path;
                return (
                  <div
                    key={item.relative_path}
                    onClick={() => setActiveItem(item)}
                    onDoubleClick={() => {
                      if (item.item_type === "directory") {
                        navigateTo(item.relative_path);
                      } else {
                        setPreviewInitialTab("preview");
                        setPreviewItem(item);
                      }
                    }}
                    onContextMenu={(e) => handleItemContextMenu(item, e)}
                    className={`group relative p-3 rounded-lg border transition-all cursor-pointer flex flex-col items-center text-center select-none ${
                      isSelected
                        ? "border-primary bg-primary/10 shadow-xs"
                        : isActive
                        ? "border-primary/50 bg-muted/60 shadow-xs"
                        : "border-border/80 bg-card hover:bg-muted/40 hover:border-border"
                    }`}
                  >
                    {/* Checkbox toggle */}
                    <button
                      onClick={(e) => toggleSelect(item.relative_path, e)}
                      className="absolute top-2 left-2 text-muted-foreground hover:text-foreground"
                    >
                      {isSelected ? (
                        <CheckSquare size={15} className="text-primary" />
                      ) : (
                        <Square
                          size={15}
                          className="opacity-0 group-hover:opacity-100 text-muted-foreground/60"
                        />
                      )}
                    </button>

                    {/* Icon / Thumbnail */}
                    <div className="my-2 p-2">
                      <FileIcon
                        itemType={item.item_type}
                        category={item.category}
                        extension={item.extension}
                        size={gridZoom > 140 ? 44 : 34}
                      />
                    </div>

                    {/* Name */}
                    <p
                      className="text-xs font-medium text-foreground truncate w-full px-1"
                      title={item.name}
                    >
                      {!showFileExtensions && item.item_type === "file" && item.extension
                        ? item.name.slice(0, -(item.extension.length + 1))
                        : item.name}
                    </p>

                    {/* Subtitle */}
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {item.item_type === "directory" ? "Folder" : formatSize(item.size_bytes)}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ===================================================================== */}
        {/* 4. BOTTOM STATUS BAR */}
        {/* ===================================================================== */}
        <div className="px-4 py-1.5 border-t border-border bg-card/60 flex items-center justify-between text-xs text-muted-foreground shrink-0 select-none">
          {/* Left: Selection Counter */}
          <div className="flex items-center gap-3">
            {selectedPaths.size > 0 ? (
              <span className="font-medium text-foreground">
                {selectedPaths.size} item{selectedPaths.size > 1 ? "s" : ""} selected ({formatSize(selectedTotalSize)})
              </span>
            ) : (
              <span>{filteredItems.length} items in directory</span>
            )}
          </div>

          {/* Center: Directory Total */}
          <div className="hidden sm:block text-[11px]">
            {listing && <span>Total Size: {formatSize(listing.total_size_bytes)}</span>}
          </div>

          {/* Right: View Toggles & Zoom Slider */}
          <div className="flex items-center gap-3">
            {/* Zoom Slider for Grid */}
            {viewMode === "grid" && (
              <div className="flex items-center gap-1.5">
                <ZoomOut size={13} className="text-muted-foreground/70" />
                <input
                  type="range"
                  min="90"
                  max="190"
                  value={gridZoom}
                  onChange={(e) => setGridZoom(Number(e.target.value))}
                  className="w-20 h-1.5 bg-muted rounded-lg appearance-none cursor-pointer accent-primary"
                  title={`Grid size: ${gridZoom}px`}
                />
                <ZoomIn size={13} className="text-muted-foreground/70" />
                <span className="font-mono text-[10px] w-8 text-right">
                  {Math.round((gridZoom / 130) * 100)}%
                </span>
              </div>
            )}

            {/* View Mode Toggle */}
            <div className="flex items-center border border-border rounded-md bg-background overflow-hidden">
              <button
                onClick={() => setViewMode("list")}
                className={`p-1 transition-colors ${
                  viewMode === "list"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                title="List View"
              >
                <List size={14} />
              </button>
              <button
                onClick={() => setViewMode("grid")}
                className={`p-1 transition-colors border-l border-border ${
                  viewMode === "grid"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:bg-muted"
                }`}
                title="Grid View"
              >
                <Grid size={14} />
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* ===================================================================== */}
      {/* 3. RIGHT PANE (320px): Persistent File Details Panel */}
      {/* ===================================================================== */}
      {showDetails && (
        <FileDetailsPanel
          item={activeItem}
          onClose={() => setShowDetails(false)}
          onPreview={(item) => setPreviewItem(item)}
          onRename={(item) => setRenameTarget(item)}
          onDelete={(item) => setDeleteTargets([item])}
          managedFolderRoot={currentManagedFolder?.root_path || ""}
          managedFolderId={selectedFolderId}
          managedFolder={currentManagedFolder}
          onUnregisterFolder={() => currentManagedFolder && setFolderToUnregister(currentManagedFolder)}
          onAskAI={(item) =>
            onOpenAssistant?.({
              folderId: selectedFolderId,
              targetType: item.item_type === "directory" ? "folder" : "file",
              relativePath: item.relative_path,
              autoPrompt: `Jelaskan ${item.item_type === "directory" ? "subfolder" : "berkas"} '${item.name}' dan rekomendasikan penataan yang aman.`,
            })
          }
        />
      )}

      {/* ===================================================================== */}
      {/* Operation Modals */}
      {/* ===================================================================== */}
      <CreateFolderModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSubmit={handleCreateFolder}
        currentPath={currentPath}
      />

      <RenameModal
        isOpen={Boolean(renameTarget)}
        onClose={() => setRenameTarget(null)}
        onSubmit={handleRename}
        item={renameTarget}
      />

      <DeleteConfirmModal
        isOpen={deleteTargets.length > 0}
        onClose={() => setDeleteTargets([])}
        onConfirm={handleDelete}
        items={deleteTargets}
      />

      <MoveCopyModal
        isOpen={moveCopyConfig.isOpen}
        mode={moveCopyConfig.mode}
        onClose={() => setMoveCopyConfig({ isOpen: false, mode: "move", items: [] })}
        onSubmit={moveCopyConfig.mode === "move" ? handleMove : handleCopy}
        items={moveCopyConfig.items}
        managedFolderId={selectedFolderId}
      />

      <FilePreviewModal
        isOpen={Boolean(previewItem)}
        onClose={() => setPreviewItem(null)}
        item={previewItem}
        managedFolderRoot={currentManagedFolder?.root_path || ""}
        managedFolderId={selectedFolderId || undefined}
        initialTab={previewInitialTab}
      />

      <UnregisterFolderModal
        isOpen={Boolean(folderToUnregister)}
        onClose={() => setFolderToUnregister(null)}
        folder={folderToUnregister}
        onConfirm={handleUnregisterFolder}
      />

      {contextMenu && (
        <FileContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          item={contextMenu.item}
          selectedCount={
            selectedPaths.has(contextMenu.item.relative_path)
              ? selectedPaths.size
              : 1
          }
          onClose={() => setContextMenu(null)}
          onOpen={handleOpenItem}
          onRename={handleRenameItem}
          onDelete={handleDeleteItem}
          onCopy={handleCopyItem}
          onMove={handleMoveItem}
          onOCR={handleOCRItem}
          onCopyPath={handleCopyPath}
          onAskAI={onOpenAssistant ? handleAskAI : undefined}
          onShowDetails={handleShowDetails}
        />
      )}
    </div>
  );
};
