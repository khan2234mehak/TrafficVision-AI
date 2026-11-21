import axios, { AxiosError } from "axios";

export const API_BASE: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") || "";
const TOKEN_KEY = "tv-token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string | null) => (t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY));

export const api = axios.create({ baseURL: API_BASE, timeout: 60000 });

api.interceptors.request.use((cfg) => {
  const t = getToken();
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});
api.interceptors.response.use(
  (r) => r,
  (e: AxiosError) => {
    if (e.response?.status === 401 && !String(e.config?.url).includes("/auth/login")) {
      window.dispatchEvent(new Event("tv-unauthorized"));
    }
    return Promise.reject(e);
  },
);

/** Turns any backend/network error into a short, useful message. */
export function errMsg(e: unknown, fallback = "Something went wrong. Please try again."): string {
  const err = e as AxiosError<{ detail?: unknown }>;
  if (err?.response) {
    const d = err.response.data?.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) {
      return d.map((x: { loc?: unknown[]; msg?: string }) => `${(x.loc ?? []).slice(1).join(".") || "field"}: ${x.msg ?? "invalid"}`).join("; ");
    }
    if (err.response.status === 413) return "The file is too large.";
    return `${fallback} (HTTP ${err.response.status})`;
  }
  if (err?.code === "ECONNABORTED") return "The request timed out.";
  if (err?.request) return "Cannot reach the backend. Is it running on port 8000?";
  return e instanceof Error ? e.message : fallback;
}

/** <img>/<video> cannot send headers, so media URLs carry the token in the query string. */
export function mediaUrl(path: string, params: Record<string, string | number | boolean> = {}): string {
  const q = new URLSearchParams({ ...Object.fromEntries(Object.entries(params).map(([k, v]) => [k, String(v)])), token: getToken() ?? "" });
  return `${API_BASE}${path}${path.includes("?") ? "&" : "?"}${q.toString()}`;
}

export function wsUrl(path: string, params: Record<string, string | number> = {}): string {
  const base = API_BASE || window.location.origin;
  const u = new URL(path, base);
  u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
  Object.entries({ ...params, token: getToken() ?? "" }).forEach(([k, v]) => u.searchParams.set(k, String(v)));
  return u.toString();
}

export async function download(path: string, params: Record<string, string | number | undefined>, filename: string) {
  const r = await api.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(r.data as Blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export const tzOffset = () => -new Date().getTimezoneOffset();
