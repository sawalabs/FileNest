import React, { useEffect, useState, useCallback } from "react";
import {
  RefreshCw,
  Play,
  Square,
  Pause,
  FolderInput,
  FilePlus,
  FilePenLine,
  Trash2,
  Settings,
  Search,
  Activity,
  ShieldCheck,
  Bell,
  Clock,
  CircleAlert,
  Copy,
  FileText,
} from "lucide-react";
import { PageHeader } from "@/components/layout/PageHeader";
import { OrganizationRulesPanel } from "@/features/organization/OrganizationRulesPanel";
import { ApiService } from "@/services/api";
import { usePreferences } from "@/contexts/PreferencesContext";
import { MonitoringSummaryCards } from "./MonitoringSummaryCards";
import { ActivityCharts } from "./ActivityCharts";
import { WatcherConfigModal } from "./WatcherConfigModal";
import type {
  ActivityChartPoint,
  AuditLogItem,
  DistributionItem,
  ManagedFolder,
  MonitoringEventItem,
  MonitoringSummaryStats,
  WatcherItem,
} from "@/types";
import { cn, formatDate } from "@/lib/utils";

type MonitoringTab = "activity" | "watchers" | "change_rules" | "alerts" | "history";

export const MonitoringManager: React.FC = () => {
  const { defaultTableDensity } = usePreferences();
  const isCompact = defaultTableDensity === "compact";
  const rowPad = isCompact ? "py-1.5 px-3" : "py-2.5 px-3";

  const [activeTab, setActiveTab] = useState<MonitoringTab>("activity");
  const [isLoading, setIsLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string>(new Date().toLocaleTimeString());

  // Service overall status
  const [serviceStatus, setServiceStatus] = useState<string>("idle");
  const [activeWatchersCount, setActiveWatchersCount] = useState(0);

  // Watchers & Folders
  const [watchers, setWatchers] = useState<WatcherItem[]>([]);
  const [folders, setFolders] = useState<ManagedFolder[]>([]);

  // Stats & Charts
  const [stats, setStats] = useState<MonitoringSummaryStats>({
    monitored_folders_count: 0,
    active_watchers_count: 0,
    total_events_24h: 0,
    files_created_count: 0,
    files_modified_count: 0,
    files_deleted_count: 0,
    total_change_size_bytes: 0,
  });
  const [chartPoints, setChartPoints] = useState<ActivityChartPoint[]>([]);
  const [distribution, setDistribution] = useState<DistributionItem[]>([]);
  const [timeRange, setTimeRange] = useState<string>("last_24h");

  // Recent Events & Audit History
  const [events, setEvents] = useState<MonitoringEventItem[]>([]);
  const [totalEvents, setTotalEvents] = useState(0);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);

  // Filters
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedFolderId, setSelectedFolderId] = useState<string>("all");
  const [selectedEventType, setSelectedEventType] = useState<string>("all");
  const [cardFilter, setCardFilter] = useState<string | undefined>(undefined);

  // Modals
  const [configuringWatcher, setConfiguringWatcher] = useState<WatcherItem | null>(null);
  const [inspectingEvent, setInspectingEvent] = useState<MonitoringEventItem | null>(null);
  const [actionFeedback, setActionFeedback] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  // Load summary stats and charts
  const loadOverviewData = useCallback(async () => {
    try {
      const [statusRes, watchersRes, statsRes, chartRes, distRes, foldersRes, auditRes] =
        await Promise.all([
          ApiService.getMonitoringStatus(),
          ApiService.listWatchers(),
          ApiService.getMonitoringStats(),
          ApiService.getMonitoringActivityChart(timeRange),
          ApiService.getMonitoringDistribution(),
          ApiService.listFolders(),
          ApiService.getAuditLogs({ limit: 50 }).catch(() => ({ total: 0, items: [] })),
        ]);

      setServiceStatus(statusRes.status);
      setActiveWatchersCount(statusRes.active_watchers);
      setWatchers(watchersRes);
      setStats(statsRes);
      setChartPoints(chartRes.data_points);
      setDistribution(distRes.distribution);
      setFolders(foldersRes);
      setAuditLogs(auditRes.items || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      console.error("Failed to load monitoring overview data", err);
    }
  }, [timeRange]);

  // Load events
  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    try {
      const params: Record<string, any> = {
        limit: 100,
        time_range: timeRange,
      };

      if (selectedFolderId !== "all") params.folder_id = selectedFolderId;
      if (selectedEventType !== "all") params.event_type = selectedEventType;
      else if (cardFilter && ["created", "modified", "deleted"].includes(cardFilter)) {
        params.event_type = cardFilter;
      }

      if (searchQuery.trim()) params.search = searchQuery.trim();

      const res = await ApiService.getMonitoringEvents(params);
      setEvents(res.items);
      setTotalEvents(res.total);
      if (res.items.length > 0 && !inspectingEvent) {
        setInspectingEvent(res.items[0]);
      }
    } catch (err: unknown) {
      console.error("Failed to load monitoring events", err);
    } finally {
      setIsLoading(false);
    }
  }, [selectedFolderId, selectedEventType, cardFilter, searchQuery, timeRange]);

  useEffect(() => {
    loadOverviewData();
  }, [loadOverviewData]);

  useEffect(() => {
    loadEvents();
  }, [loadEvents]);

  // Watcher Actions
  const handleStartWatcher = async (folderId: string) => {
    try {
      await ApiService.startWatcher(folderId);
      setActionFeedback({ type: "success", text: "Watcher started and monitoring active." });
      loadOverviewData();
      loadEvents();
    } catch (err: unknown) {
      setActionFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to start watcher",
      });
    }
  };

  const handleStopWatcher = async (folderId: string) => {
    try {
      await ApiService.stopWatcher(folderId);
      setActionFeedback({ type: "success", text: "Watcher stopped." });
      loadOverviewData();
      loadEvents();
    } catch (err: unknown) {
      setActionFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to stop watcher",
      });
    }
  };

  const handlePauseWatcher = async (folderId: string) => {
    try {
      await ApiService.pauseWatcher(folderId);
      setActionFeedback({ type: "success", text: "Watcher paused." });
      loadOverviewData();
    } catch (err: unknown) {
      setActionFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to pause watcher",
      });
    }
  };

  const handleResumeWatcher = async (folderId: string) => {
    try {
      await ApiService.resumeWatcher(folderId);
      setActionFeedback({ type: "success", text: "Watcher resumed." });
      loadOverviewData();
    } catch (err: unknown) {
      setActionFeedback({
        type: "error",
        text: err instanceof Error ? err.message : "Failed to resume watcher",
      });
    }
  };

  const getEventBadge = (type: string) => {
    switch (type) {
      case "created":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <FilePlus size={11} />
            Created
          </span>
        );
      case "modified":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FilePenLine size={11} />
            Modified
          </span>
        );
      case "deleted":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <Trash2 size={11} />
            Deleted
          </span>
        );
      case "moved":
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
            <FolderInput size={11} />
            Moved
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground border border-border">
            {type}
          </span>
        );
    }
  };

  const getWatcherStatusPill = (status: string) => {
    switch (status) {
      case "watching":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Watching
          </span>
        );
      case "paused":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
            <Pause size={10} />
            Paused
          </span>
        );
      case "stopped":
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-muted text-muted-foreground border border-border">
            <Square size={10} />
            Stopped
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20">
            <CircleAlert size={10} />
            Error
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <PageHeader
        title="Monitoring"
        description="Monitor file and folder changes in your managed folders in real time or in the background."
      >
        <div className="flex items-center gap-2.5">
          {/* Status Indicator */}
          <div className="flex items-center gap-1.5 mr-2">
            {serviceStatus === "running" ? (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Monitoring Active ({activeWatchersCount})</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium bg-muted text-muted-foreground border border-border">
                <span className="w-2 h-2 rounded-full bg-muted-foreground/60" />
                <span>Monitoring Idle</span>
              </span>
            )}
          </div>

          <span className="text-xs text-muted-foreground hidden sm:inline">
            Updated: {lastUpdated}
          </span>

          <button
            type="button"
            onClick={() => {
              loadOverviewData();
              loadEvents();
            }}
            disabled={isLoading}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md border border-border bg-card text-xs font-medium hover:bg-muted transition-colors disabled:opacity-50"
          >
            <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
            <span>Refresh</span>
          </button>
        </div>
      </PageHeader>

      {/* Action Feedback Banner */}
      {actionFeedback && (
        <div
          className={cn(
            "p-3 rounded-lg border text-xs flex items-center justify-between animate-in fade-in",
            actionFeedback.type === "success"
              ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700 dark:text-emerald-400"
              : "bg-rose-500/10 border-rose-500/30 text-rose-700 dark:text-rose-400"
          )}
        >
          <span>{actionFeedback.text}</span>
          <button
            type="button"
            onClick={() => setActionFeedback(null)}
            className="text-muted-foreground hover:text-foreground"
          >
            ×
          </button>
        </div>
      )}

      {/* Summary Cards */}
      <MonitoringSummaryCards
        stats={stats}
        activeFilter={cardFilter}
        onFilterClick={(key) => {
          if (cardFilter === key) setCardFilter(undefined);
          else setCardFilter(key);
        }}
      />

      {/* Monitoring Tabs */}
      <div className="border-b border-border flex items-center gap-1 overflow-x-auto">
        {[
          { id: "activity", label: "Activity" },
          { id: "watchers", label: `Watchers (${watchers.length})` },
          { id: "change_rules", label: "Change Rules" },
          { id: "alerts", label: "Alerts" },
          { id: "history", label: "History" },
        ].map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id as MonitoringTab)}
            className={cn(
              "px-3.5 py-2 text-xs font-medium border-b-2 transition-colors whitespace-nowrap",
              activeTab === tab.id
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground hover:border-border"
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab 1: Activity */}
      {activeTab === "activity" && (
        <div className="space-y-5">
          {/* Middle Visualizations Row (3 Columns: Timeline Bar, Distribution Donut, Active Watchers) */}
          <ActivityCharts
            chartPoints={chartPoints}
            distribution={distribution}
            watchers={watchers}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
            onCategoryClick={(category) => {
              setSelectedEventType(category);
            }}
            onPauseWatcher={handlePauseWatcher}
            onResumeWatcher={handleResumeWatcher}
            onStartWatcher={handleStartWatcher}
            onManageWatchers={() => setActiveTab("watchers")}
          />

          {/* Bottom Master-Detail Split Pane (2 Columns: Events Table on left, Persistent Inspector on right) */}
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            {/* Left: Events Master Table (~67% width / col-span-8) */}
            <div className="lg:col-span-8 space-y-3">
              {/* Filter Toolbar */}
              <div className="flex flex-wrap items-center justify-between gap-2.5 p-2.5 bg-card border border-border rounded-lg text-xs">
                <div className="flex flex-wrap items-center gap-2 flex-1 min-w-[240px]">
                  {/* Search */}
                  <div className="relative flex-1 min-w-[160px]">
                    <Search
                      size={13}
                      className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
                    />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Search file, path..."
                      className="w-full pl-8 pr-3 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                    />
                  </div>

                  {/* Event Type Filter */}
                  <select
                    value={selectedEventType}
                    onChange={(e) => setSelectedEventType(e.target.value)}
                    className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="all">All Events</option>
                    <option value="created">Created</option>
                    <option value="modified">Modified</option>
                    <option value="deleted">Deleted</option>
                    <option value="moved">Moved</option>
                  </select>

                  {/* Folder Filter */}
                  <select
                    value={selectedFolderId}
                    onChange={(e) => setSelectedFolderId(e.target.value)}
                    className="px-2 py-1 rounded-md border border-border bg-background text-xs focus:outline-none focus:ring-1 focus:ring-primary"
                  >
                    <option value="all">All Folders</option>
                    {folders.map((f) => (
                      <option key={f.id} value={f.id}>
                        {f.name}
                      </option>
                    ))}
                  </select>
                </div>

                <button
                  type="button"
                  onClick={() => {
                    setSearchQuery("");
                    setSelectedFolderId("all");
                    setSelectedEventType("all");
                    setCardFilter(undefined);
                  }}
                  className="px-2.5 py-1 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
                >
                  Reset
                </button>
              </div>

              {/* Counter Banner */}
              <div className="flex items-center justify-between text-xs text-muted-foreground px-1">
                <span>
                  Showing {events.length} of {totalEvents} captured event{totalEvents === 1 ? "" : "s"}
                </span>
                {isLoading && <span className="text-[11px] animate-pulse">Loading updates...</span>}
              </div>

              {/* Events Table */}
              <div className="border border-border rounded-lg bg-card overflow-hidden shadow-xs">
                <table className="w-full text-left text-xs border-collapse">
                  <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px] font-semibold">
                    <tr>
                      <th className="py-2.5 px-3 w-10 text-center">#</th>
                      <th className="py-2.5 px-3 w-32">Time (UTC)</th>
                      <th className="py-2.5 px-3 w-24">Event</th>
                      <th className="py-2.5 px-3">File / Relative Path</th>
                      <th className="py-2.5 px-3 w-36">Managed Folder</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {events.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="py-12 text-center text-muted-foreground">
                          <Activity size={32} className="mx-auto mb-2 opacity-40" />
                          <span>No monitoring events detected yet.</span>
                        </td>
                      </tr>
                    ) : (
                      events.map((ev, idx) => {
                        const isSelected = inspectingEvent?.id === ev.id;
                        return (
                          <tr
                            key={ev.id}
                            onClick={() => setInspectingEvent(ev)}
                            className={cn(
                              "cursor-pointer transition-colors group",
                              isSelected
                                ? "bg-primary/10 border-l-2 border-primary"
                                : "hover:bg-muted/30"
                            )}
                          >
                            <td className={`${rowPad} text-center text-muted-foreground font-mono text-[11px]`}>
                              {idx + 1}
                            </td>
                            <td className={`${rowPad} font-mono text-muted-foreground text-[11px]`}>
                              {ev.occurred_at}
                            </td>
                            <td className={`${rowPad}`}>{getEventBadge(ev.event_type)}</td>
                            <td className={`${rowPad} font-mono text-foreground break-all max-w-xs`}>
                              <span title={ev.relative_path}>{ev.relative_path}</span>
                              {ev.destination_relative_path && (
                                <span className="text-muted-foreground block text-[10px]">
                                  → {ev.destination_relative_path}
                                </span>
                              )}
                            </td>
                            <td
                              className={`${rowPad} text-muted-foreground truncate max-w-[140px]`}
                              title={ev.managed_folder_name}
                            >
                              {ev.managed_folder_name}
                            </td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Right: Persistent Event Details Inspector (~33% width / col-span-4) */}
            <div className="lg:col-span-4 space-y-4">
              {inspectingEvent ? (
                <div className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3.5">
                  {/* Header */}
                  <div className="flex items-center justify-between border-b border-border pb-2.5">
                    <div className="flex items-center gap-2">
                      <FileText size={16} className="text-primary" />
                      <span className="font-semibold text-xs text-foreground uppercase tracking-wider">
                        Event Details
                      </span>
                    </div>
                    {getEventBadge(inspectingEvent.event_type)}
                  </div>

                  {/* Metadata Grid */}
                  <div className="grid grid-cols-2 gap-2.5 p-3 rounded-lg bg-muted/30 border border-border text-xs">
                    <div>
                      <span className="text-[10px] text-muted-foreground block mb-0.5">Time (UTC)</span>
                      <span className="font-mono text-[11px] font-medium">{inspectingEvent.occurred_at}</span>
                    </div>
                    <div>
                      <span className="text-[10px] text-muted-foreground block mb-0.5">Event Type</span>
                      <span className="font-medium capitalize text-[11px]">{inspectingEvent.event_type}</span>
                    </div>
                    <div className="col-span-2 border-t border-border/60 pt-2">
                      <span className="text-[10px] text-muted-foreground block mb-0.5">Managed Folder</span>
                      <span
                        className="font-medium text-foreground text-[11px] truncate block"
                        title={inspectingEvent.managed_folder_name}
                      >
                        {inspectingEvent.managed_folder_name}
                      </span>
                    </div>
                  </div>

                  {/* Relative Path */}
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>Relative Path</span>
                      <button
                        type="button"
                        onClick={() => {
                          navigator.clipboard.writeText(inspectingEvent.relative_path);
                          setActionFeedback({ type: "success", text: "Relative path copied." });
                        }}
                        className="hover:text-foreground text-[10px] flex items-center gap-1"
                      >
                        <Copy size={11} />
                        <span>Copy</span>
                      </button>
                    </div>
                    <div className="p-2 rounded bg-muted/40 border border-border font-mono text-[11px] text-foreground break-all">
                      {inspectingEvent.relative_path}
                    </div>
                  </div>

                  {/* Full Physical Path */}
                  <div className="space-y-1 text-xs">
                    <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                      <span>Physical Disk Path</span>
                    </div>
                    <div className="p-2 rounded bg-muted/40 border border-border font-mono text-[10px] text-muted-foreground break-all">
                      {(() => {
                        const f = folders.find((fol) => fol.id === inspectingEvent.managed_folder_id);
                        return f
                          ? `${f.root_path}\\${inspectingEvent.relative_path.replace(/\//g, "\\")}`
                          : inspectingEvent.relative_path;
                      })()}
                    </div>
                  </div>

                  {/* Action Buttons */}
                  <div className="pt-2 border-t border-border flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => {
                        const f = folders.find((fol) => fol.id === inspectingEvent.managed_folder_id);
                        const full = f
                          ? `${f.root_path}\\${inspectingEvent.relative_path.replace(/\//g, "\\")}`
                          : inspectingEvent.relative_path;
                        navigator.clipboard.writeText(full);
                        setActionFeedback({
                          type: "success",
                          text: `Copied path to clipboard: ${full}`,
                        });
                      }}
                      className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-xs font-medium transition-colors shadow-xs"
                    >
                      <Copy size={13} />
                      <span>Copy Full Path</span>
                    </button>
                  </div>
                </div>
              ) : (
                <div className="p-8 rounded-lg border border-border bg-card/60 text-center text-muted-foreground space-y-2">
                  <Activity size={32} className="mx-auto text-muted-foreground/40" />
                  <h4 className="text-xs font-medium text-foreground">No Event Selected</h4>
                  <p className="text-[11px] text-muted-foreground max-w-[200px] mx-auto">
                    Click any event in the table to inspect its relative path, timestamp, and disk location.
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: Watchers */}
      {activeTab === "watchers" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-sm">Managed Folder Watchers</h3>
              <p className="text-xs text-muted-foreground">
                Control active observers and configure event debounce parameters.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {watchers.map((w) => (
              <div
                key={w.folder_id}
                className="p-4 rounded-lg border border-border bg-card shadow-xs space-y-3 flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="font-semibold text-sm">{w.folder_name}</h4>
                      <p className="text-xs font-mono text-muted-foreground break-all mt-0.5">
                        {w.root_path}
                      </p>
                    </div>
                    {getWatcherStatusPill(w.status)}
                  </div>

                  <div className="grid grid-cols-2 gap-2 p-2.5 rounded-md bg-muted/20 border border-border text-xs">
                    <div>
                      <span className="text-muted-foreground block text-[10px]">
                        Debounce Window:
                      </span>
                      <span className="font-semibold">{w.debounce_ms} ms</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-[10px]">
                        Recursive Subfolders:
                      </span>
                      <span className="font-semibold">{w.recursive ? "Yes" : "No"}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-[10px]">
                        Events (Last 24h):
                      </span>
                      <span className="font-semibold text-primary">{w.events_count_24h}</span>
                    </div>
                    <div>
                      <span className="text-muted-foreground block text-[10px]">
                        Custom Ignore Patterns:
                      </span>
                      <span className="font-semibold">{w.ignore_patterns.length}</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-border">
                  <button
                    type="button"
                    onClick={() => setConfiguringWatcher(w)}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border border-border bg-background hover:bg-muted text-xs font-medium transition-colors"
                  >
                    <Settings size={13} />
                    <span>Configure</span>
                  </button>

                  <div className="flex items-center gap-2">
                    {w.status === "watching" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => handlePauseWatcher(w.folder_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-border text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 text-xs font-medium transition-colors"
                        >
                          <Pause size={13} />
                          <span>Pause</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleStopWatcher(w.folder_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-rose-600 hover:bg-rose-700 text-white text-xs font-medium transition-colors shadow-xs"
                        >
                          <Square size={13} />
                          <span>Stop</span>
                        </button>
                      </>
                    ) : w.status === "paused" ? (
                      <>
                        <button
                          type="button"
                          onClick={() => handleResumeWatcher(w.folder_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md bg-emerald-600 hover:bg-emerald-700 text-white text-xs font-medium transition-colors shadow-xs"
                        >
                          <Play size={13} />
                          <span>Resume</span>
                        </button>
                        <button
                          type="button"
                          onClick={() => handleStopWatcher(w.folder_id)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md border border-border text-rose-600 hover:bg-rose-500/10 text-xs font-medium transition-colors"
                        >
                          <Square size={13} />
                          <span>Stop</span>
                        </button>
                      </>
                    ) : (
                      <button
                        type="button"
                        onClick={() => handleStartWatcher(w.folder_id)}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:bg-primary/90 transition-colors shadow-xs"
                      >
                        <Play size={13} />
                        <span>Start Watcher</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 3: Change Rules */}
      {activeTab === "change_rules" && (
        <div className="space-y-4">
          <div className="p-5 rounded-lg border border-border bg-card space-y-3">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-primary/10 text-primary">
                <ShieldCheck size={20} />
              </div>
              <div>
                <h3 className="font-semibold text-sm">Monitoring-Triggered Change Rules</h3>
                <p className="text-xs text-muted-foreground">
                  Approved automation rules evaluated safely when Watchdog detects new or modified files inside Managed Folders.
                </p>
              </div>
            </div>
            <div className="p-3 rounded-lg border border-border bg-muted/20 text-xs text-muted-foreground">
              <span className="font-semibold text-foreground mr-2">Safety Guarantees:</span>
              Watchers never mutate files directly; approved rules create validated Change Plans routed through the Transaction Manager.
            </div>
          </div>

          <OrganizationRulesPanel
            folders={folders}
            selectedFolderId={selectedFolderId !== "all" ? selectedFolderId : undefined}
          />
        </div>
      )}

      {/* Tab 4: Alerts */}
      {activeTab === "alerts" && (() => {
        const watcherErrors = watchers.filter((w) => w.status === "error" || Boolean(w.error_message));
        const alertEvents = events.filter(
          (e) => e.event_type === "deleted" || e.status === "failed"
        );
        return (
          <div className="space-y-4">
            <div className="p-5 rounded-lg border border-border bg-card space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-2.5 rounded-lg bg-amber-500/10 text-amber-600 dark:text-amber-400">
                    <Bell size={20} />
                  </div>
                  <div>
                    <h3 className="font-semibold text-sm">Monitoring Notifications & Alerts</h3>
                    <p className="text-xs text-muted-foreground">
                      Live watcher errors, failed event evaluations, and deletion spikes across Managed Folders.
                    </p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    loadOverviewData();
                    loadEvents();
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted text-xs font-medium"
                >
                  <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
                  <span>Refresh</span>
                </button>
              </div>

              <div className="p-4 rounded-lg border border-border bg-muted/20 text-xs space-y-1.5">
                <div className="flex items-center justify-between text-foreground font-medium">
                  <span className="flex items-center gap-1.5">
                    <Clock size={13} className="text-primary" />
                    Active Observers Health ({activeWatchersCount} active)
                  </span>
                  <span
                    className={cn(
                      "font-semibold",
                      watcherErrors.length > 0
                        ? "text-rose-600 dark:text-rose-400"
                        : "text-emerald-600 dark:text-emerald-400"
                    )}
                  >
                    {watcherErrors.length > 0 ? `${watcherErrors.length} Watcher Error(s)` : "Nominal"}
                  </span>
                </div>
                <p className="text-muted-foreground">
                  {watcherErrors.length === 0
                    ? `All ${activeWatchersCount} active watcher(s) reporting healthy capture; ${alertEvents.length} deletion/failure event(s) in current filter.`
                    : "Some watchers reported errors and may require reconfiguration or restart."}
                </p>
              </div>

              {watcherErrors.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-rose-600 dark:text-rose-400">
                    Watcher Errors
                  </h4>
                  <div className="divide-y divide-border rounded-lg border border-rose-500/30 bg-rose-500/5">
                    {watcherErrors.map((w) => (
                      <div key={w.folder_id} className="p-3 text-xs flex items-center justify-between gap-3">
                        <div>
                          <p className="font-semibold text-foreground">{w.folder_name}</p>
                          <p className="text-[11px] text-rose-600 dark:text-rose-400">
                            {w.error_message || "Watcher entered error state"}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setConfiguringWatcher(w)}
                          className="px-2.5 py-1 rounded border border-border bg-background hover:bg-muted text-[11px] font-medium"
                        >
                          Configure
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-foreground">
                  High-Attention Events (Deletions & Failures)
                </h4>
                {alertEvents.length === 0 ? (
                  <p className="py-6 text-center text-xs text-muted-foreground border border-dashed border-border rounded-lg">
                    No deletion or failed processing alerts detected in the selected window.
                  </p>
                ) : (
                  <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
                    {alertEvents.slice(0, 20).map((ev) => (
                      <div key={ev.id} className="p-3 text-xs flex items-center justify-between gap-3 bg-background/40">
                        <div className="min-w-0">
                          <p className="font-mono text-[11px] text-foreground truncate">
                            [{ev.managed_folder_name}] {ev.relative_path}
                          </p>
                          <p className="text-[11px] text-muted-foreground">
                            {formatDate(ev.occurred_at)} · status: {ev.status}
                          </p>
                        </div>
                        <span className="px-2 py-0.5 rounded bg-rose-500/10 text-rose-600 dark:text-rose-400 font-medium capitalize text-[11px] shrink-0">
                          {ev.event_type}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })()}

      {/* Tab 5: History */}
      {activeTab === "history" && (
        <div className="p-5 rounded-lg border border-border bg-card space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2.5 rounded-lg bg-blue-500/10 text-blue-600 dark:text-blue-400">
                <Clock size={20} />
              </div>
              <div>
                <h3 className="font-semibold text-sm">Monitoring Audit History</h3>
                <p className="text-xs text-muted-foreground">
                  Recorded watcher lifecycle events, rule audits, and recent monitoring activity.
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => {
                loadOverviewData();
                loadEvents();
              }}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border bg-background hover:bg-muted text-xs font-medium"
            >
              <RefreshCw size={13} className={isLoading ? "animate-spin" : ""} />
              <span>Refresh</span>
            </button>
          </div>

          {auditLogs.length === 0 && events.length === 0 ? (
            <div className="py-10 text-center text-xs text-muted-foreground border border-dashed border-border rounded-lg">
              No monitoring audit entries or filesystem events recorded yet.
            </div>
          ) : (
            <div className="border border-border rounded-lg overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-muted/40 text-muted-foreground border-b border-border uppercase tracking-wider text-[10px]">
                  <tr>
                    <th className="py-2 px-3">Timestamp</th>
                    <th className="py-2 px-3">Actor / Source</th>
                    <th className="py-2 px-3">Action / Event</th>
                    <th className="py-2 px-3">Target</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {auditLogs.slice(0, 25).map((log) => (
                    <tr key={`audit-${log.id}`} className="hover:bg-muted/20">
                      <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </td>
                      <td className="py-2 px-3 capitalize font-medium text-foreground">
                        {log.actor_type} ({log.entity_type})
                      </td>
                      <td className="py-2 px-3">
                        <span className="px-2 py-0.5 rounded bg-secondary text-secondary-foreground font-medium text-[11px]">
                          {log.action}
                        </span>
                      </td>
                      <td className="py-2 px-3 font-mono text-[11px] text-muted-foreground truncate max-w-sm">
                        {log.entity_id || JSON.stringify(log.details || {})}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Watcher Config Modal */}
      {configuringWatcher && (
        <WatcherConfigModal
          watcher={configuringWatcher}
          isOpen={true}
          onClose={() => setConfiguringWatcher(null)}
          onSaved={() => {
            loadOverviewData();
          }}
          updateConfig={ApiService.updateWatcherConfig}
        />
      )}
    </div>
  );
};
