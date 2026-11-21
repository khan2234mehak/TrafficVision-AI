import { AlertOctagon, BellRing, CheckCheck, Info, ShieldAlert } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { useToast } from "../context/AppContext";
import { useChannel } from "../hooks";
import { api } from "../services/api";
import type { AppNotification } from "../types";
import { timeAgo } from "../utils/format";
import { Button, DemoBadge, EmptyState } from "./ui";

export function NotificationsPanel({ onClose }: { onClose: () => void }) {
  const [items, setItems] = useState<AppNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try { const r = await api.get<{ items: AppNotification[] }>("/api/notifications"); setItems(r.data.items); } finally { setLoading(false); }
  }, []);
  useEffect(() => { void load(); }, [load]);
  const markAll = async () => { await api.post("/api/notifications/read-all"); setItems((s) => s.map((n) => ({ ...n, is_read: true }))); window.dispatchEvent(new Event("tv-notifications")); };
  const icon = (n: AppNotification) => n.kind === "violation" ? <ShieldAlert className="h-4 w-4 text-danger" /> : n.kind === "congestion" ? <AlertOctagon className="h-4 w-4 text-orange" /> : <Info className="h-4 w-4 text-brand" />;
  return (
    <div className="glass absolute right-0 top-12 z-[1200] w-[min(92vw,400px)] overflow-hidden shadow-panel" role="dialog" aria-label="Notifications">
      <div className="flex items-center justify-between border-b border-line/60 px-4 py-3">
        <h3 className="text-sm font-semibold">Notifications</h3>
        <div className="flex gap-1"><Button size="sm" variant="ghost" onClick={markAll}><CheckCheck className="h-4 w-4" />Mark all read</Button><Button size="sm" variant="ghost" onClick={onClose}>Close</Button></div>
      </div>
      <div className="max-h-[60vh] overflow-auto">
        {loading ? <p className="p-6 text-center text-sm text-muted">Loading...</p> : items.length === 0 ? (
          <EmptyState icon={<BellRing className="h-6 w-6" />} title="You're all caught up" hint="Congestion and violation alerts will show up here." />
        ) : items.map((n) => (
          <div key={n.id} className={`flex gap-3 border-b border-line/40 px-4 py-3 last:border-0 ${n.is_read ? "opacity-70" : ""}`}>
            <div className="mt-0.5">{icon(n)}</div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium">{n.title}</p>
              <p className="text-xs text-muted">{n.message}</p>
              <p className="mt-1 flex items-center gap-2 text-[11px] text-muted">{timeAgo(n.created_at)}{n.is_demo && <DemoBadge text="Demo" />}</p>
            </div>
            {!n.is_read && <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-brand" aria-label="Unread" />}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Subscribes to /ws/alerts and returns the unread count. */
export function useAlerts() {
  const toast = useToast();
  const [unread, setUnread] = useState(0);
  const refresh = useCallback(async () => {
    try { const r = await api.get<{ unread: number }>("/api/notifications"); setUnread(r.data.unread); } catch { /* offline */ }
  }, []);
  useEffect(() => {
    void refresh();
    window.addEventListener("tv-notifications", refresh);
    return () => window.removeEventListener("tv-notifications", refresh);
  }, [refresh]);
  useChannel("/ws/alerts", (m) => {
    if (m.type === "violation" || m.type === "congestion") { toast.push("error", `${m.title} - ${m.message}`); void refresh(); }
  });
  return { unread, refresh };
}
