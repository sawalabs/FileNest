import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
} from "react";
import { ApiService } from "@/services/api";
import type {
  BackgroundJobItem,
  BackgroundJobType,
  FloatingTaskNotification,
  NavItem,
} from "@/types";

interface CompletedJobPayload {
  jobId: string;
  jobType: BackgroundJobType;
  resultPayload: any;
  managedFolderId?: string | null;
  timestamp: string;
}

interface BackgroundTasksContextType {
  activeJobs: BackgroundJobItem[];
  recentJobs: BackgroundJobItem[];
  notifications: FloatingTaskNotification[];
  isDrawerOpen: boolean;
  setIsDrawerOpen: (open: boolean) => void;
  toggleDrawer: () => void;
  cancelJob: (jobId: string) => Promise<boolean>;
  dismissJob: (jobId: string) => Promise<void>;
  dismissNotification: (id: string) => void;
  clearAllNotifications: () => void;
  refreshJobs: () => Promise<void>;
  lastCompletedPayload: CompletedJobPayload | null;
  clearCompletedPayload: () => void;
  navigateToJobResult: (jobId: string, onNavigate?: (item: NavItem) => void) => void;
}

const BackgroundTasksContext = createContext<BackgroundTasksContextType | undefined>(
  undefined
);

const LOCAL_STORAGE_ACTIVE_JOBS_KEY = "fne_active_job_ids";
const LOCAL_STORAGE_NOTIFS_KEY = "fne_task_notifications";

export const BackgroundTasksProvider: React.FC<{
  children: React.ReactNode;
  onNavigate?: (item: NavItem) => void;
}> = ({ children, onNavigate }) => {
  const [activeJobs, setActiveJobs] = useState<BackgroundJobItem[]>([]);
  const [recentJobs, setRecentJobs] = useState<BackgroundJobItem[]>([]);
  const [notifications, setNotifications] = useState<FloatingTaskNotification[]>(() => {
    try {
      const saved = localStorage.getItem(LOCAL_STORAGE_NOTIFS_KEY);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [lastCompletedPayload, setLastCompletedPayload] =
    useState<CompletedJobPayload | null>(null);

  // Keep track of previously known active job statuses to detect transitions
  const previousStatusMap = useRef<Map<string, string>>(new Map());

  // Save notifications to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(LOCAL_STORAGE_NOTIFS_KEY, JSON.stringify(notifications.slice(0, 20)));
    } catch (e) {
      console.warn("Failed to save task notifications to localStorage:", e);
    }
  }, [notifications]);

  const toggleDrawer = useCallback(() => {
    setIsDrawerOpen((prev) => !prev);
  }, []);

  const dismissNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearAllNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const clearCompletedPayload = useCallback(() => {
    setLastCompletedPayload(null);
  }, []);

  // Poll active & recent jobs
  const refreshJobs = useCallback(async () => {
    try {
      const [actives, recents] = await Promise.all([
        ApiService.getActiveJobs().catch(() => []),
        ApiService.getRecentJobs(10).catch(() => []),
      ]);

      setActiveJobs(actives);
      setRecentJobs(recents);

      // Persist active job IDs to localStorage
      try {
        const activeIds = actives.map((j) => j.id);
        localStorage.setItem(LOCAL_STORAGE_ACTIVE_JOBS_KEY, JSON.stringify(activeIds));
      } catch {
        // ignore
      }

      // Check transitions: if a job was previously in running/queued, and is now completed or failed
      actives.forEach((job) => {
        previousStatusMap.current.set(job.id, job.status);
      });

      recents.forEach((job) => {
        const prevStatus = previousStatusMap.current.get(job.id);
        if (
          prevStatus &&
          (prevStatus === "running" || prevStatus === "queued") &&
          (job.status === "completed" || job.status === "failed")
        ) {
          // Transition detected! Create a floating toast notification
          const notifId = `notif_${job.id}_${Date.now()}`;
          let targetView: "storage" | "smart_rename" | "organization" | "history" = "history";
          let summary = job.current_step || "Pekerjaan selesai";

          if (job.job_type === "storage_analysis") {
            targetView = "storage";
            summary = "Analisis kapasitas & duplikat file siap ditinjau.";
          } else if (job.job_type === "smart_rename_plan") {
            targetView = "smart_rename";
            summary = "Rekomendasi penamaan berkas cerdas telah dibuat.";
          } else if (job.job_type === "batch_ocr") {
            targetView = "smart_rename";
            summary = "Ekstraksi OCR dan penamaan teks AI telah selesai.";
          } else if (job.job_type === "organization_plan") {
            targetView = "organization";
            summary = "Rencana pemilahan berkas folder telah siap ditinjau.";
          }

          if (job.status === "failed") {
            summary = job.error_message || "Terjadi kesalahan saat memproses pekerjaan.";
          }

          const newNotif: FloatingTaskNotification = {
            id: notifId,
            job_id: job.id,
            job_type: job.job_type,
            title: job.title,
            status: job.status as "completed" | "failed",
            summary,
            timestamp: job.finished_at || new Date().toISOString(),
            result_payload: job.result_payload,
            target_view: targetView,
          };

          setNotifications((prev) => [newNotif, ...prev.filter((n) => n.job_id !== job.id)]);

          if (job.status === "completed" && job.result_payload) {
            setLastCompletedPayload({
              jobId: job.id,
              jobType: job.job_type,
              resultPayload: job.result_payload,
              managedFolderId: job.managed_folder_id,
              timestamp: new Date().toISOString(),
            });
          }
        }
        previousStatusMap.current.set(job.id, job.status);
      });
    } catch (err) {
      console.error("Failed to poll background jobs:", err);
    }
  }, []);

  // Polling loop: 1.5s when active jobs exist, 5s when idle
  useEffect(() => {
    refreshJobs();
    const intervalTime = activeJobs.length > 0 ? 1500 : 5000;
    const interval = setInterval(refreshJobs, intervalTime);
    return () => clearInterval(interval);
  }, [activeJobs.length, refreshJobs]);

  const cancelJob = useCallback(
    async (jobId: string): Promise<boolean> => {
      try {
        await ApiService.cancelJob(jobId);
        await refreshJobs();
        return true;
      } catch (err) {
        console.error(`Failed to cancel job ${jobId}:`, err);
        return false;
      }
    },
    [refreshJobs]
  );

  const dismissJob = useCallback(
    async (jobId: string): Promise<void> => {
      try {
        await ApiService.dismissJob(jobId);
        await refreshJobs();
      } catch (err) {
        console.error(`Failed to dismiss job ${jobId}:`, err);
      }
    },
    [refreshJobs]
  );

  const navigateToJobResult = useCallback(
    (jobId: string, customNavigate?: (item: NavItem) => void) => {
      const navFn = customNavigate || onNavigate;
      // Find job in active, recent, or notifications
      const targetJob =
        recentJobs.find((j) => j.id === jobId) ||
        activeJobs.find((j) => j.id === jobId);

      if (targetJob) {
        if (targetJob.result_payload) {
          setLastCompletedPayload({
            jobId: targetJob.id,
            jobType: targetJob.job_type,
            resultPayload: targetJob.result_payload,
            managedFolderId: targetJob.managed_folder_id,
            timestamp: new Date().toISOString(),
          });
        }

        if (navFn) {
          if (targetJob.job_type === "storage_analysis") {
            navFn("storage");
          } else if (
            targetJob.job_type === "smart_rename_plan" ||
            targetJob.job_type === "batch_ocr"
          ) {
            navFn("smart-rename");
          } else if (targetJob.job_type === "organization_plan") {
            navFn("organization");
          } else {
            navFn("history");
          }
        }
      } else {
        // Fallback to checking notification by job_id
        const notif = notifications.find((n) => n.job_id === jobId);
        if (notif && navFn) {
          if (notif.job_type === "storage_analysis") {
            navFn("storage");
          } else if (
            notif.job_type === "smart_rename_plan" ||
            notif.job_type === "batch_ocr"
          ) {
            navFn("smart-rename");
          } else if (notif.job_type === "organization_plan") {
            navFn("organization");
          }
        }
      }
    },
    [activeJobs, recentJobs, notifications, onNavigate]
  );

  return (
    <BackgroundTasksContext.Provider
      value={{
        activeJobs,
        recentJobs,
        notifications,
        isDrawerOpen,
        setIsDrawerOpen,
        toggleDrawer,
        cancelJob,
        dismissJob,
        dismissNotification,
        clearAllNotifications,
        refreshJobs,
        lastCompletedPayload,
        clearCompletedPayload,
        navigateToJobResult,
      }}
    >
      {children}
    </BackgroundTasksContext.Provider>
  );
};

export const useBackgroundTasks = () => {
  const context = useContext(BackgroundTasksContext);
  if (!context) {
    throw new Error(
      "useBackgroundTasks must be used within a BackgroundTasksProvider"
    );
  }
  return context;
};
