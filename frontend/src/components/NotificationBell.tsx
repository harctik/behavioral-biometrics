"use client";

import { useState, useEffect } from "react";
import { Bell, X, ShieldCheck, AlertTriangle, ArrowRightLeft, LogIn, Info } from "lucide-react";

interface Notification {
  id: string;
  type: "security" | "transaction" | "login" | "info";
  title: string;
  message: string;
  time: string;
  read: boolean;
}

const ICON_MAP: Record<string, any> = {
  security: ShieldCheck,
  transaction: ArrowRightLeft,
  login: LogIn,
  info: Info,
};

const COLOR_MAP: Record<string, string> = {
  security: "text-amber-400 bg-amber-500/10 border-amber-500/20",
  transaction: "text-blue-400 bg-blue-500/10 border-blue-500/20",
  login: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  info: "text-slate-400 bg-slate-500/10 border-slate-500/20",
};

import { getCsrfToken } from "@/lib/auth-utils";

// Demo notifications fallback if backend fetch fails
const DEMO_NOTIFICATIONS: Notification[] = [
  { id: "n1", type: "security", title: "Behavioral Profile Active", message: "Your behavioral fingerprint is being continuously verified.", time: "Just now", read: false },
  { id: "n2", type: "login", title: "New Login Detected", message: "Session started from your current device.", time: "2 min ago", read: false },
  { id: "n3", type: "info", title: "Enrollment Progress", message: "Keep using the app normally to build your security profile.", time: "5 min ago", read: true },
];

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    const fetchNotifs = async () => {
      try {
        const res = await fetch("/api/v1/notifications");
        if (res.ok) {
          const data = await res.json();
          setNotifications(data.notifications || []);
        } else {
          setNotifications(DEMO_NOTIFICATIONS);
        }
      } catch {
        setNotifications(DEMO_NOTIFICATIONS);
      }
    };
    fetchNotifs();
  }, []);

  const unreadCount = notifications.filter(n => !n.read).length;

  const markAllRead = async () => {
    setNotifications(prev => prev.map(n => ({ ...n, read: true })));
    try {
      await fetch("/api/v1/notifications/read-all", {
        method: "POST",
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
    } catch {}
  };

  const dismiss = async (id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    try {
      await fetch(`/api/v1/notifications/${id}`, {
        method: "DELETE",
        headers: { "X-CSRF-TOKEN": getCsrfToken() }
      });
    } catch {}
  };

  return (
    <div className="relative">
      {/* Bell trigger */}
      <button
        onClick={() => setOpen(!open)}
        className="relative w-9 h-9 rounded-full flex items-center justify-center hover:bg-surface-2 transition-colors border border-transparent hover:border-border"
      >
        <Bell className="w-4 h-4 text-muted" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center text-[9px] font-bold text-white shadow-[0_0_6px_rgba(239,68,68,0.5)]">
            {unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown panel */}
      {open && (
        <>
          {/* Backdrop */}
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />

          {/* Panel */}
          <div className="absolute right-0 top-12 w-80 max-h-[420px] bg-surface border border-border rounded-2xl shadow-2xl z-50 overflow-hidden flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
              <span className="text-sm font-semibold text-fg">Notifications</span>
              <div className="flex items-center gap-2">
                {unreadCount > 0 && (
                  <button onClick={markAllRead} className="text-[10px] text-accent-primary hover:underline">
                    Mark all read
                  </button>
                )}
                <button onClick={() => setOpen(false)} className="w-6 h-6 flex items-center justify-center rounded-md hover:bg-surface-2 text-muted">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <Bell className="w-8 h-8 text-muted mb-2" />
                  <span className="text-xs text-muted">No notifications</span>
                </div>
              ) : (
                notifications.map(n => {
                  const Icon = ICON_MAP[n.type] || Info;
                  return (
                    <div
                      key={n.id}
                      className={`group flex items-start gap-3 px-4 py-3 border-b border-border last:border-0 transition-colors ${!n.read ? 'bg-accent-primary/5' : 'hover:bg-surface-2/30'}`}
                    >
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center border shrink-0 mt-0.5 ${COLOR_MAP[n.type]}`}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-fg truncate">{n.title}</span>
                          {!n.read && <span className="w-1.5 h-1.5 rounded-full bg-accent-primary shrink-0" />}
                        </div>
                        <p className="text-[10px] text-muted mt-0.5 leading-relaxed">{n.message}</p>
                        <span className="text-[9px] text-muted font-mono mt-1 block">{n.time}</span>
                      </div>
                      <button
                        onClick={() => dismiss(n.id)}
                        className="w-5 h-5 flex items-center justify-center rounded hover:bg-surface-2 text-muted shrink-0 opacity-0 group-hover:opacity-100 hover:opacity-100 transition-opacity"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  );
                })
              )}
            </div>

            {/* Footer */}
            <div className="px-4 py-2.5 border-t border-border shrink-0 bg-black/20">
              <span className="text-[9px] text-muted font-mono flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Behavioral telemetry monitored in real-time
              </span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
