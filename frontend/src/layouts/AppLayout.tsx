import { AnimatePresence, motion } from "framer-motion";
import { BarChart3, Bell, Camera, FileText, FileVideo, LayoutDashboard, LogOut, Map, Menu, Moon, Radio, Settings, ShieldAlert, Sun, Wifi, WifiOff, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { NotificationsPanel, useAlerts } from "../components/NotificationsPanel";
import { Button, ConfirmDialog } from "../components/ui";
import { useAuth, useTheme } from "../context/AppContext";
import { useChannel } from "../hooks";
import { cx } from "../utils/format";

export const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard },
  { to: "/live", label: "Live Monitoring", icon: Radio },
  { to: "/video", label: "Video Analysis", icon: FileVideo },
  { to: "/cameras", label: "Camera Management", icon: Camera },
  { to: "/analytics", label: "Traffic Analytics", icon: BarChart3 },
  { to: "/violations", label: "Violation Detection", icon: ShieldAlert },
  { to: "/map", label: "Traffic Map", icon: Map },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

function Logo() {
  return (
    <div className="flex items-center gap-3 px-2">
      <div className="grid h-10 w-10 place-items-center rounded-xl bg-raised"><div className="flex flex-col gap-[3px]"><i className="h-1.5 w-1.5 rounded-full bg-danger" /><i className="h-1.5 w-1.5 rounded-full bg-warn" /><i className="h-1.5 w-1.5 rounded-full bg-cyan" /></div></div>
      <div className="leading-tight"><p className="font-display text-[17px] font-semibold">TrafficVision</p><p className="text-xs text-muted">Command center</p></div>
    </div>
  );
}

export default function AppLayout() {
  const { user, logout } = useAuth();
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [bell, setBell] = useState(false);
  const [confirmOut, setConfirmOut] = useState(false);
  const loc = useLocation();
  const { unread } = useAlerts();
  const connected = useChannel("/ws/traffic", () => {});

  const nav = (
    <nav className="mt-8 flex flex-col gap-1" aria-label="Main">
      {NAV.map(({ to, label, icon: Icon }) => (
        <NavLink key={to} to={to} end={to === "/"} onClick={() => setOpen(false)}
          className={({ isActive }) => cx("relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition", isActive ? "bg-brand/15 text-ink" : "text-muted hover:bg-raised hover:text-ink")}>
          {({ isActive }) => (<>
            {isActive && <motion.span layoutId="nav-lane" className="absolute -left-4 top-2 h-[calc(100%-16px)] w-1 rounded-full bg-cyan" />}
            <Icon className={cx("h-[18px] w-[18px]", isActive && "text-cyan")} aria-hidden />{label}
          </>)}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-full lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-line/60 bg-surface/60 p-5 backdrop-blur-xl lg:flex"><Logo />{nav}
        <div className="mt-auto rounded-xl border border-line/60 bg-raised/60 p-3 text-xs text-muted">
          <p className="font-medium text-ink">{user?.username}</p><p className="truncate">{user?.email}</p><p className="mt-1 capitalize">Role: {user?.role}</p>
        </div>
      </aside>
      <AnimatePresence>
        {open && (
          <motion.div className="fixed inset-0 z-[1100] lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <div className="absolute inset-0 bg-black/60" onClick={() => setOpen(false)} />
            <motion.aside initial={{ x: -280 }} animate={{ x: 0 }} exit={{ x: -280 }} transition={{ type: "tween", duration: 0.2 }} className="absolute inset-y-0 left-0 w-[270px] overflow-auto border-r border-line bg-surface p-5">
              <button aria-label="Close menu" className="absolute right-3 top-3 rounded-lg p-1 text-muted hover:bg-raised" onClick={() => setOpen(false)}><X className="h-5 w-5" /></button>
              <Logo />{nav}
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="min-w-0">
        <header className="sticky top-0 z-[1000] flex items-center justify-between gap-3 border-b border-line/50 bg-bg/70 px-4 py-3 backdrop-blur-xl sm:px-8">
          <div className="flex items-center gap-3">
            <button className="rounded-xl p-2 text-muted hover:bg-raised lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
            <span className={cx("flex items-center gap-2 rounded-full border px-3 py-1 text-xs", connected ? "border-ok/40 text-ok" : "border-warn/40 text-warn")} title="Real-time connection to the backend">
              {connected ? <Wifi className="h-3.5 w-3.5" /> : <WifiOff className="h-3.5 w-3.5" />}<span className="hidden sm:inline">{connected ? "Live updates connected" : "Reconnecting..."}</span>
            </span>
          </div>
          <div className="relative flex items-center gap-1">
            <Button variant="ghost" aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`} onClick={toggle}>{theme === "dark" ? <Sun className="h-[18px] w-[18px]" /> : <Moon className="h-[18px] w-[18px]" />}</Button>
            <Button variant="ghost" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} onClick={() => setBell((b) => !b)} className="relative">
              <Bell className="h-[18px] w-[18px]" />{unread > 0 && <span className="num absolute right-1 top-0.5 grid h-4 min-w-4 place-items-center rounded-full bg-danger px-1 text-[10px] font-bold text-white">{unread > 9 ? "9+" : unread}</span>}
            </Button>
            <Button variant="ghost" aria-label="Sign out" onClick={() => setConfirmOut(true)}><LogOut className="h-[18px] w-[18px]" /></Button>
            {bell && <NotificationsPanel onClose={() => { setBell(false); window.dispatchEvent(new Event("tv-notifications")); }} />}
          </div>
        </header>
        <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-8 sm:py-8">
          <AnimatePresence mode="wait"><motion.div key={loc.pathname} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.18 }}><Outlet /></motion.div></AnimatePresence>
        </main>
      </div>
      <ConfirmDialog open={confirmOut} title="Sign out?" message="You will need to sign in again to access the dashboard." confirmLabel="Sign out" onConfirm={logout} onCancel={() => setConfirmOut(false)} />
    </div>
  );
}
