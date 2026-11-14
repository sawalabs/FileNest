import React, { useState, useMemo } from "react";
import {
  Search,
  Filter,
  ArrowUpDown,
  Copy,
  Check,
  FileCode,
  Layers,
} from "lucide-react";
import { formatBytes, formatNumber } from "@/lib/utils";
import type { FileTypeStats } from "@/types";

interface FileTypesTabProps {
  fileTypes: FileTypeStats[];
  initialCategoryFilter?: string;
  onFilterByCategory?: (category: string) => void;
}

export const FileTypesTab: React.FC<FileTypesTabProps> = ({
  fileTypes,
  initialCategoryFilter = "all",
}) => {
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryFilter, setCategoryFilter] = useState(initialCategoryFilter);
  const [sortBy, setSortBy] = useState<"size_desc" | "count_desc" | "ext_asc">("size_desc");
  const [copiedExt, setCopiedExt] = useState<string | null>(null);

  const categories = useMemo(() => {
    const set = new Set<string>();
    fileTypes.forEach((ft) => {
      if (ft.category) set.add(ft.category);
    });
    return Array.from(set).sort();
  }, [fileTypes]);

  const filteredTypes = useMemo(() => {
    return fileTypes
      .filter((ft) => {
        if (searchQuery.trim()) {
          const q = searchQuery.toLowerCase();
          if (!ft.extension.toLowerCase().includes(q)) {
            return false;
          }
        }
        if (categoryFilter !== "all" && ft.category.toLowerCase() !== categoryFilter.toLowerCase()) {
          return false;
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "size_desc") return b.total_size_bytes - a.total_size_bytes;
        if (sortBy === "count_desc") return b.files_count - a.files_count;
        if (sortBy === "ext_asc") return a.extension.localeCompare(b.extension);
        return 0;
      });
  }, [fileTypes, searchQuery, categoryFilter, sortBy]);

  const handleCopyExt = async (ext: string) => {
    try {
      await navigator.clipboard.writeText(ext);
      setCopiedExt(ext);
      setTimeout(() => setCopiedExt(null), 2000);
    } catch {
      // ignore
    }
  };

  return (
    <div className="space-y-4">
      {/* Search and Filters */}
      <div className="p-4 rounded-xl border border-border bg-card shadow-sm space-y-3">
        <div className="flex flex-col md:flex-row items-stretch md:items-center gap-3">
          <div className="relative flex-1">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search file extensions (e.g. .pdf, .png, .mp4)..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs bg-muted/40 border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-primary"
            />
          </div>

          <div className="flex items-center gap-2">
            <Filter size={14} className="text-muted-foreground shrink-0" />
            <select
              value={categoryFilter}
              onChange={(e) => setCategoryFilter(e.target.value)}
              className="text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
            >
              <option value="all">All Categories</option>
              {categories.map((cat) => (
                <option key={cat} value={cat}>
                  {cat.charAt(0).toUpperCase() + cat.slice(1)}
                </option>
              ))}
            </select>

            <div className="flex items-center gap-1.5">
              <ArrowUpDown size={14} className="text-muted-foreground shrink-0" />
              <select
                value={sortBy}
                onChange={(e) => setSortBy(e.target.value as any)}
                className="text-xs bg-muted/40 border border-border rounded-md px-2.5 py-1.5 focus:outline-none focus:ring-1 focus:ring-primary"
              >
                <option value="size_desc">Largest Size First</option>
                <option value="count_desc">Most Files First</option>
                <option value="ext_asc">Extension (A-Z)</option>
              </select>
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t border-border/40">
          <span>
            Showing <strong className="text-foreground">{filteredTypes.length}</strong> of {fileTypes.length} file types
          </span>
          {categoryFilter !== "all" && (
            <button
              onClick={() => setCategoryFilter("all")}
              className="text-primary hover:underline text-[11px]"
            >
              Reset Category Filter
            </button>
          )}
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-border bg-card shadow-sm overflow-hidden">
        {filteredTypes.length === 0 ? (
          <div className="py-12 text-center text-muted-foreground space-y-2">
            <Layers size={32} className="mx-auto text-muted-foreground/40" />
            <p className="text-xs font-semibold">No file extensions matched</p>
            <p className="text-[11px]">Try clearing search or changing the selected category.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-muted/50 border-b border-border text-muted-foreground font-semibold">
                <tr>
                  <th className="py-2.5 px-4">Extension</th>
                  <th className="py-2.5 px-4">Category</th>
                  <th className="py-2.5 px-4 text-right">Files Count</th>
                  <th className="py-2.5 px-4 text-right">Total Size</th>
                  <th className="py-2.5 px-4 text-right">Avg Size</th>
                  <th className="py-2.5 px-4 text-right">Storage Share</th>
                  <th className="py-2.5 px-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {filteredTypes.map((ft) => {
                  const avgBytes = ft.files_count > 0 ? ft.total_size_bytes / ft.files_count : 0;

                  return (
                    <tr key={ft.extension} className="hover:bg-muted/30 transition-colors">
                      <td className="py-2.5 px-4 font-mono font-semibold text-foreground flex items-center gap-2">
                        <FileCode size={15} className="text-primary shrink-0" />
                        <span>{ft.extension}</span>
                      </td>
                      <td className="py-2.5 px-4">
                        <span className="capitalize px-2 py-0.5 rounded-full text-[10px] font-medium bg-muted text-muted-foreground">
                          {ft.category}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 text-right font-medium text-foreground">
                        {formatNumber(ft.files_count)}
                      </td>
                      <td className="py-2.5 px-4 text-right font-bold text-foreground">
                        {formatBytes(ft.total_size_bytes)}
                      </td>
                      <td className="py-2.5 px-4 text-right text-muted-foreground">
                        {formatBytes(avgBytes)}
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <div className="inline-flex items-center gap-2">
                          <div className="w-16 bg-muted rounded-full h-1.5 overflow-hidden">
                            <div
                              className="bg-primary h-1.5 rounded-full"
                              style={{ width: `${Math.min(ft.percentage, 100)}%` }}
                            />
                          </div>
                          <span className="font-mono text-[11px] text-muted-foreground w-11 text-right">
                            {ft.percentage.toFixed(1)}%
                          </span>
                        </div>
                      </td>
                      <td className="py-2.5 px-4 text-right">
                        <button
                          onClick={() => handleCopyExt(ft.extension)}
                          title="Copy extension"
                          className="p-1 rounded hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                        >
                          {copiedExt === ft.extension ? (
                            <Check size={14} className="text-emerald-600" />
                          ) : (
                            <Copy size={14} />
                          )}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
