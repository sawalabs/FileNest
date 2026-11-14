import React from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, Calendar } from "lucide-react";
import type { DashboardStorageTrendPointData } from "@/types";
import { formatBytes } from "@/lib/utils";

interface StorageHistoryChartProps {
  historyPoints: DashboardStorageTrendPointData[];
}

export const StorageHistoryChart: React.FC<StorageHistoryChartProps> = ({
  historyPoints,
}) => {
  const chartData = historyPoints.map((p) => ({
    date: p.date,
    total_size: p.total_size_bytes,
    formatted_size: formatBytes(p.total_size_bytes),
  }));

  const isEmpty = chartData.length === 0;

  return (
    <div className="p-5 rounded-xl border border-border bg-card shadow-sm flex flex-col justify-between">
      <div className="flex items-center justify-between pb-3 border-b border-border/50">
        <div>
          <h3 className="font-semibold text-sm text-foreground flex items-center gap-2">
            <TrendingUp size={16} className="text-primary" />
            Riwayat Tren Penyimpanan
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Pertumbuhan ruang terpakai 7 hari terakhir
          </p>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Calendar size={13} />
          <span>7 Hari Terakhir</span>
        </div>
      </div>

      {isEmpty ? (
        <div className="py-12 flex flex-col items-center justify-center text-center text-muted-foreground">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-2">
            <TrendingUp size={18} className="text-muted-foreground/60" />
          </div>
          <p className="text-sm font-medium text-foreground">Belum ada riwayat tren</p>
          <p className="text-xs mt-1 text-muted-foreground max-w-xs">
            Tren harian akan tercatat seiring bertambahnya pemindaian berkala.
          </p>
        </div>
      ) : (
        <div className="mt-4 h-48 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="storageTrendGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
                </linearGradient>
              </defs>
              <XAxis
                dataKey="date"
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "#888888" }}
                dy={5}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tick={{ fontSize: 10, fill: "#888888" }}
                tickFormatter={(value) => formatBytes(value)}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (active && payload && payload.length) {
                    const data = payload[0].payload;
                    return (
                      <div className="px-3 py-2 bg-popover text-popover-foreground border border-border rounded-lg shadow-md text-xs">
                        <p className="font-semibold text-foreground">{data.date}</p>
                        <p className="text-primary font-medium mt-0.5">
                          Total: {data.formatted_size}
                        </p>
                      </div>
                    );
                  }
                  return null;
                }}
              />
              <Area
                type="monotone"
                dataKey="total_size"
                stroke="#3b82f6"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#storageTrendGradient)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};
