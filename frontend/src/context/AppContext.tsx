import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setToken, getToken } from "../services/api";
import type { User } from "../types";

/* ---------------------------------------------------------------- auth */
interface AuthCtx {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => void;
  can: (role: "operator" | "admin") => boolean;
}
const Auth = createContext<AuthCtx>(null as never);
export const useAuth = () => useContext(Auth);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(!!getToken());

  const logout = useCallback(() => { setToken(null); setUser(null); }, []);
  useEffect(() => {
    if (!getToken()) return;
    api.get<User>("/api/auth/me").then((r) => setUser(r.data)).catch(() => setToken(null)).finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    window.addEventListener("tv-unauthorized", logout);
    return () => window.removeEventListener("tv-unauthorized", logout);
  }, [logout]);

  const value = useMemo<AuthCtx>(() => ({
    user, loading, logout,
    login: async (email, password) => {
      const r = await api.post("/api/auth/login", { email, password });
      setToken(r.data.access_token); setUser(r.data.user);
    },
    register: async (email, username, password) => {
      const r = await api.post("/api/auth/register", { email, username, password });
      setToken(r.data.access_token); setUser(r.data.user);
    },
    can: (role) => !!user && (role === "operator" ? user.role !== "viewer" : user.role === "admin"),
  }), [user, loading, logout]);
  return <Auth.Provider value={value}>{children}</Auth.Provider>;
}

/* --------------------------------------------------------------- theme */
type Theme = "dark" | "light";
const ThemeC = createContext<{ theme: Theme; toggle: () => void }>({ theme: "dark", toggle: () => {} });
export const useTheme = () => useContext(ThemeC);

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>(() => (document.documentElement.getAttribute("data-theme") as Theme) || "dark");
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try { localStorage.setItem("tv-theme", theme); } catch { /* storage unavailable */ }
  }, [theme]);
  return <ThemeC.Provider value={{ theme, toggle: () => setTheme((t) => (t === "dark" ? "light" : "dark")) }}>{children}</ThemeC.Provider>;
}

/* --------------------------------------------------------------- toast */
interface Toast { id: number; kind: "success" | "error" | "info"; text: string }
const ToastC = createContext<{ push: (kind: Toast["kind"], text: string) => void }>({ push: () => {} });
export const useToast = () => useContext(ToastC);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((kind: Toast["kind"], text: string) => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s.slice(-3), { id, kind, text }]);
    setTimeout(() => setItems((s) => s.filter((t) => t.id !== id)), kind === "error" ? 7000 : 4000);
  }, []);
  const color = { success: "border-ok/50", error: "border-danger/60", info: "border-brand/50" } as const;
  return (
    <ToastC.Provider value={{ push }}>
      {children}
      <div className="fixed bottom-4 right-4 z-[2000] flex w-[min(92vw,380px)] flex-col gap-2" aria-live="polite" role="status">
        {items.map((t) => (
          <div key={t.id} className={`glass border-l-4 px-4 py-3 text-sm shadow-panel ${color[t.kind]}`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastC.Provider>
  );
}
