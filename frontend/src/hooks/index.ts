import { DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { errMsg, wsUrl } from "../services/api";

/** Loads data, exposing loading / error / reload. Re-runs when `deps` change. */
export function useFetch<T>(fn: () => Promise<T>, deps: DependencyList = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try { setData(await fnRef.current()); setError(null); } catch (e) { setError(errMsg(e)); } finally { setLoading(false); }
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void reload(); }, deps);
  return { data, loading, error, reload, setData };
}

/** Reconnecting WebSocket for the backend channels (/ws/traffic, /ws/alerts). */
export function useChannel(path: "/ws/traffic" | "/ws/alerts", onMessage: (m: any) => void) {
  const cb = useRef(onMessage);
  cb.current = onMessage;
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let ws: WebSocket | null = null; let closed = false; let timer: number; let ping: number;
    const open = () => {
      ws = new WebSocket(wsUrl(path));
      ws.onopen = () => { setConnected(true); ping = window.setInterval(() => ws?.readyState === 1 && ws.send("ping"), 25000); };
      ws.onmessage = (e) => { try { cb.current(JSON.parse(e.data)); } catch { /* ignore malformed */ } };
      ws.onclose = () => { setConnected(false); window.clearInterval(ping); if (!closed) timer = window.setTimeout(open, 3000); };
    };
    open();
    return () => { closed = true; window.clearTimeout(timer); window.clearInterval(ping); ws?.close(); };
  }, [path]);
  return connected;
}

export function useInterval(fn: () => void, ms: number | null) {
  const ref = useRef(fn);
  ref.current = fn;
  useEffect(() => {
    if (ms == null) return;
    const id = window.setInterval(() => ref.current(), ms);
    return () => window.clearInterval(id);
  }, [ms]);
}
