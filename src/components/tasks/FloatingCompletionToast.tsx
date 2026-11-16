import React, { useEffect } from "react";
import { CheckCircle2, CircleX, X, ArrowRight } from "lucide-react";
import { useBackgroundTasks } from "@/contexts/BackgroundTasksContext";
import type { FloatingTaskNotification } from "@/types";

interface ToastItemProps {
  notification: FloatingTaskNotification;
  onDismiss: (id: string) => void;
  onNavigate: (jobId: string) => void;
}

const ToastItem: React.FC<ToastItemProps> = ({ notification, onDismiss, onNavigate }) => {
  useEffect(() => {
    // Auto-dismiss after 9 seconds
    const timer = setTimeout(() => {
      onDismiss(notification.id);
    }, 9000);
    return () => clearTimeout(timer);
  }, [notification.id, onDismiss]);

  const isSuccess = notification.status === "completed";

  return (
    <div
      role="alert"
      className="max-w-md w-[92vw] sm:w-[380px] bg-card/98 backdrop-blur-xl border border-border shadow-2xl rounded-xl p-3.5 flex items-start gap-3 transition-all duration-300 animate-in fade-in slide-in-from-right-3 hover:border-primary/40 select-none"
    >
      <div className="mt-0.5 shrink-0">
        {isSuccess ? (
          <CheckCircle2 size={18} className="text-emerald-500" />
        ) : (
          <CircleX size={18} className="text-destructive" />
        )}
      </div>

      <div className="flex-1 min-w-0">
        <h3 className="text-xs font-semibold text-foreground truncate">
          {notification.title}
        </h3>
        <p className="text-[11px] text-muted-foreground mt-0.5 line-clamp-2 leading-relaxed">
          {notification.summary}
        </p>

        {isSuccess && (
          <button
            type="button"
            onClick={() => {
              onNavigate(notification.job_id);
              onDismiss(notification.id);
            }}
            className="mt-2 inline-flex items-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition-colors"
          >
            <span>Buka Hasil</span>
            <ArrowRight size={13} />
          </button>
        )}
      </div>

      <button
        type="button"
        onClick={() => onDismiss(notification.id)}
        className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors shrink-0"
        title="Tutup notifikasi"
      >
        <X size={14} />
      </button>
    </div>
  );
};

export const FloatingCompletionToast: React.FC = () => {
  const { notifications, dismissNotification, navigateToJobResult } = useBackgroundTasks();

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className="fixed bottom-20 right-6 z-50 flex flex-col gap-2.5 pointer-events-auto">
      {notifications.slice(0, 3).map((notif) => (
        <ToastItem
          key={notif.id}
          notification={notif}
          onDismiss={dismissNotification}
          onNavigate={navigateToJobResult}
        />
      ))}
    </div>
  );
};
