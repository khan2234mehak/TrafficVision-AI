export const CLASS_LABEL: Record<string, string> = { car: "Cars", motorcycle: "Bikes", bus: "Buses", truck: "Trucks", bicycle: "Bicycles" };
export const CLASS_COLOR: Record<string, string> = { car: "#3B82FF", motorcycle: "#22D3EE", bus: "#34D399", truck: "#FBBF24", bicycle: "#A78BFA" };
export const CATEGORY_LABEL: Record<string, string> = {
  wrong_way: "Wrong-way driving", restricted_zone: "Restricted zone", overspeed: "Overspeeding", red_light: "Red light",
};
export const CATEGORY_COLOR: Record<string, string> = { wrong_way: "#F87171", restricted_zone: "#FBBF24", overspeed: "#FB923C", red_light: "#A78BFA" };
export const LEVEL_COLOR: Record<string, string> = { Low: "#34D399", Moderate: "#FBBF24", High: "#FB923C", Critical: "#F87171", "No data": "#64748B" };

export const fmtNum = (n: number | null | undefined) => (n == null ? "-" : new Intl.NumberFormat().format(Math.round(n)));
export const fmtBytes = (b: number) => (b > 1e9 ? `${(b / 1e9).toFixed(2)} GB` : b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);
export const fmtDuration = (s: number | null | undefined) => {
  if (s == null) return "-";
  const m = Math.floor(s / 60);
  return m ? `${m}m ${Math.round(s % 60)}s` : `${s.toFixed(1)}s`;
};
export const fmtDateTime = (iso: string) => new Date(iso).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
export const fmtTime = (iso: string, daily = false) =>
  daily ? new Date(iso).toLocaleDateString([], { month: "short", day: "numeric" }) : new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
export const timeAgo = (iso: string) => {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
};
export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");
export const levelIndex = (l: string | null | undefined) => ["Low", "Moderate", "High", "Critical"].indexOf(l ?? "");
