import React from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import { HardDrive, PieChart as PieChartIcon } from "lucide-react";
import type { DashboardCategoryItemData } from "@/types";
import { formatBytes } from "@/lib/utils";

interface StorageUsageDonutProps {
  categories: DashboardCategoryItemData[];
  totalBytes: number;
  onSelectCategory: (category: string) => void;
}

const CATEGORY_COLORS: Record<string, string> = {
  Dokumen: "#3b82f6", // blue-500
  Gambar: "#10b981",  // emerald-500
  Video: "#f59e0b",   // amber-500
  Audio: "#8b5cf6",   // violet-500
  Arsip: "#ec4899",   // pink-500
  Kode: "#06b6d4",    // cyan-500
  Lainnya: "#64748b", // slate-500
};

const DEFAULT_COLOR = "#94a3b8";

export const StorageUsageDonut: React.FC<StorageUsageDonutProps> = ({
  categories,
  totalBytes,
  onSelectCategory,
}) => {
  const activeCategories = categories.filter((c) => c.total_size_bytes > 0);
  const chartData = activeCategories.map((c) => ({
    name: c.category,
    value: c.total_size_bytes,
    percentage: c.percentage,
    color: CATEGORY_COLORS[c.category] || DEFAULT_COLOR,
  }));

  const isEmpty = chartData.length === 0 || totalBytes === 0;

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between h-full">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <PieChartIcon size={16} className="text-primary" />
            Penggunaan Penyimpanan
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Distribusi ruang berdasarkan kategori file
          </p>
        </div>
        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-muted text-muted-foreground">
          {formatBytes(totalBytes)} Total
        </span>
      </div>

      {isEmpty ? (
        <div className="py-12 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
            <HardDrive size={22} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Belum ada data penyimpanan</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Daftarkan folder atau jalankan analisis untuk melihat distribusi kategori file.
          </p>
        </div>
      ) : (
        <div className="mt-4 flex flex-col md:flex-row items-center gap-6">
          {/* Donut Chart */}
          <div className="relative w-44 h-44 flex-shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const data = payload[0].payload;
                      return (
                        <div className="px-3 py-2 bg-popover text-popover-foreground border border-border rounded-lg shadow-md text-xs">
                          <p className="font-semibold">{data.name}</p>
                          <p className="text-muted-foreground mt-0.5">
                            {formatBytes(data.value)} ({data.percentage}%)
                          </p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={70}
                  paddingAngle={3}
                  dataKey="value"
                  stroke="none"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            {/* Center label */}
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none text-center">
              <span className="text-xs text-muted-foreground font-medium">Total</span>
              <span className="text-sm font-bold text-foreground">
                {formatBytes(totalBytes)}
              </span>
            </div>
          </div>

          {/* Legend and Category List */}
          <div className="flex-1 w-full space-y-2">
            {categories.map((cat) => {
              const color = CATEGORY_COLORS[cat.category] || DEFAULT_COLOR;
              return (
                <div
                  key={cat.category}
                  role="button"
                  tabIndex={0}
                  onClick={() => onSelectCategory(cat.category)}
                  onKeyDown={(e) => e.key === "Enter" && onSelectCategory(cat.category)}
                  className="flex items-center justify-between text-xs p-1.5 rounded-md hover:bg-muted/60 transition-colors cursor-pointer group"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                      style={{ backgroundColor: color }}
                    />
                    <span className="font-medium text-foreground group-hover:text-primary transition-colors">
                      {cat.category}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-muted-foreground">
                    <span>{formatBytes(cat.total_size_bytes)}</span>
                    <span className="font-semibold w-10 text-right text-foreground/80">
                      {cat.percentage}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
