"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, NotificationItem } from "@/lib/api";

const POLL_INTERVAL_MS = 30000;

const LEVEL_DOT: Record<NotificationItem["level"], string> = {
  info: "bg-brand-500",
  warning: "bg-amber-500",
  critical: "bg-red-500",
};

export function NotificationBell() {
  const router = useRouter();
  const [count, setCount] = useState(0);
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const poll = () => api.unreadNotificationCount().then((r) => setCount(r.count)).catch(() => {});
    poll();
    const interval = setInterval(poll, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!open) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const handleToggle = async () => {
    const next = !open;
    setOpen(next);
    if (next) {
      const data = await api.listNotifications().catch(() => []);
      setItems(data);
    }
  };

  const handleItemClick = async (item: NotificationItem) => {
    setOpen(false);
    if (!item.is_read) {
      setCount((c) => Math.max(0, c - 1));
      setItems((prev) => prev?.map((i) => (i.id === item.id ? { ...i, is_read: true } : i)) ?? null);
      api.markNotificationRead(item.id).catch(() => {});
    }
    if (item.link) router.push(item.link);
  };

  const handleMarkAllRead = async () => {
    setCount(0);
    setItems((prev) => prev?.map((i) => ({ ...i, is_read: true })) ?? null);
    await api.markAllNotificationsRead().catch(() => {});
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={handleToggle}
        className="relative rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        aria-label="Notifications"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="h-5 w-5">
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2c0 .5-.2 1-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"
          />
        </svg>
        {count > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-medium text-white">
            {count > 9 ? "9+" : count}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-80 rounded-lg border border-slate-200 bg-white shadow-lg">
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-2">
            <span className="text-sm font-medium text-slate-900">Notifications</span>
            {count > 0 && (
              <button onClick={handleMarkAllRead} className="text-xs text-brand-600 hover:underline">
                Mark all read
              </button>
            )}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {items === null ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">Loading...</p>
            ) : items.length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-slate-500">No notifications yet.</p>
            ) : (
              items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleItemClick(item)}
                  className={`flex w-full gap-2.5 border-b border-slate-50 px-4 py-3 text-left text-sm last:border-0 hover:bg-slate-50 ${
                    item.is_read ? "" : "bg-brand-50/40"
                  }`}
                >
                  <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${LEVEL_DOT[item.level]}`} />
                  <span>
                    <span className="block font-medium text-slate-900">{item.title}</span>
                    {item.body && <span className="mt-0.5 block text-xs text-slate-500">{item.body}</span>}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
