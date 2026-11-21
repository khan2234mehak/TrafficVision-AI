import { AlertTriangle, Info, RefreshCw, Save } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { GeometryEditor } from "../components/GeometryEditor";
import { Badge, Button, Card, CardHeader, ConfirmDialog, ErrorState, Field, Input, PageHeader, ProgressBar, Segmented, Select, Skeleton, Toggle } from "../components/ui";
import { useAuth, useTheme, useToast } from "../context/AppContext";
import { useFetch } from "../hooks";
import { api, errMsg, mediaUrl } from "../services/api";
import type { ActivityLog, AppSettings, Camera, CameraConfig, Page, SystemHealth, User, Video } from "../types";
import { CLASS_LABEL, fmtDateTime } from "../utils/format";

type Tab = "detection" | "setup" | "notifications" | "appearance" | "admin" | "system";

export default function SettingsPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = (params.get("tab") as Tab) || "detection";
  const setTab = (t: Tab) => setParams((p) => { p.set("tab", t); return p; });
  const tabs: { value: Tab; label: string }[] = [
    { value: "detection", label: "Detection model" }, { value: "setup", label: "Cameras and zones" }, { value: "notifications", label: "Notifications" },
    { value: "appearance", label: "Appearance and data" }, ...(can("admin") ? [{ value: "admin" as Tab, label: "Users and activity" }] : []), { value: "system", label: "System health" },
  ];
  return (
    <>
      <PageHeader title="Settings" subtitle={can("admin") ? "Tune the detection model, configure cameras, alerts and appearance." : "You have read-only access. Ask an admin to change settings."} />
      <div className="mb-5 overflow-x-auto"><Segmented label="Settings section" value={tab} onChange={setTab} options={tabs} /></div>
      {tab === "detection" && <ModelSettings />}
      {tab === "setup" && <DetectionSetup initialCamera={params.get("camera")} />}
      {tab === "notifications" && <ModelSettings section="notifications" />}
      {tab === "appearance" && <Appearance />}
      {tab === "admin" && can("admin") && <AdminPanel />}
      {tab === "system" && <SystemHealthCard />}
    </>
  );
}

/* ------------------------------------------------------------ model + alerts */
function ModelSettings({ section = "model" }: { section?: "model" | "notifications" }) {
  const { can } = useAuth();
  const toast = useToast();
  const remote = useFetch(async () => (await api.get<AppSettings>("/api/settings")).data, []);
  const [s, setS] = useState<AppSettings | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { if (remote.data) setS(remote.data); }, [remote.data]);
  if (remote.error) return <Card><ErrorState message={remote.error} onRetry={() => remote.reload()} /></Card>;
  if (!s) return <Skeleton className="h-72" />;
  const ro = !can("admin");
  const save = async () => {
    setSaving(true);
    try { const r = await api.put<AppSettings>("/api/settings", s); setS(r.data); toast.push("success", "Settings saved"); } catch (e) { toast.push("error", errMsg(e)); } finally { setSaving(false); }
  };
  const th = s.density_thresholds;
  return (
    <Card className="max-w-3xl space-y-6">
      {section === "model" ? (<>
        <CardHeader title="Detection model" subtitle="Applies to the next video or live session you start." />
        <Field label={`Confidence threshold: ${Math.round(s.confidence * 100)}%`} hint="Higher means fewer false detections but more missed vehicles. 35% is a good start for traffic video.">
          <input type="range" min={5} max={95} step={5} disabled={ro} value={Math.round(s.confidence * 100)} onChange={(e) => setS({ ...s, confidence: +e.target.value / 100 })} className="w-full accent-[rgb(var(--brand))]" aria-label="Confidence threshold" /></Field>
        <Field label={`Overlap (NMS IoU): ${s.iou}`} hint="Lower values merge overlapping boxes more aggressively."><input type="range" min={0.1} max={0.9} step={0.05} disabled={ro} value={s.iou} onChange={(e) => setS({ ...s, iou: +e.target.value })} className="w-full accent-[rgb(var(--brand))]" aria-label="IoU threshold" /></Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Inference size" hint="Smaller is faster on CPU, larger sees small vehicles better."><Select disabled={ro} value={s.imgsz} onChange={(e) => setS({ ...s, imgsz: +e.target.value as AppSettings["imgsz"] })}>{[320, 480, 640, 960].map((n) => <option key={n} value={n}>{n} px</option>)}</Select></Field>
          <Field label="Live frame skipping" hint="Analyse every Nth frame of live sources."><Select disabled={ro} value={s.live_frame_stride} onChange={(e) => setS({ ...s, live_frame_stride: +e.target.value })}>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>Every {n === 1 ? "frame" : `${n} frames`}</option>)}</Select></Field>
        </div>
        <fieldset><legend className="mb-2 text-sm font-medium">Detection categories</legend>
          <div className="flex flex-wrap gap-2">{Object.entries(CLASS_LABEL).map(([k, label]) => { const on = s.classes.includes(k); return (
            <button key={k} disabled={ro} aria-pressed={on} onClick={() => setS({ ...s, classes: on ? s.classes.filter((c) => c !== k) : [...s.classes, k] })} className={`rounded-xl border px-3 py-1.5 text-sm transition ${on ? "border-brand bg-brand/15" : "border-line text-muted"} disabled:opacity-60`}>{k === "motorcycle" ? "Bikes (motorcycles)" : label}</button>); })}</div>
          {s.classes.length === 0 && <p className="mt-2 text-xs text-danger">Select at least one category.</p>}</fieldset>
        <fieldset><legend className="mb-2 text-sm font-medium">Congestion thresholds (occupancy)</legend>
          <div className="grid grid-cols-3 gap-3">{["Moderate from", "High from", "Critical from"].map((l, i) => (<Field key={l} label={l}><Input type="number" step={0.05} min={0.05} max={2} disabled={ro} value={th[i]} onChange={(e) => { const n = [...th] as AppSettings["density_thresholds"]; n[i] = +e.target.value; setS({ ...s, density_thresholds: n }); }} /></Field>))}</div>
          <p className="mt-2 text-xs text-muted">Occupancy = vehicles inside the density zone / its capacity. Below the first value is Low.</p></fieldset>
      </>) : (<>
        <CardHeader title="Notifications" subtitle="Alerts appear in the bell menu and as pop-ups while you are signed in." />
        <Toggle label="Congestion alerts" hint="Alert when congestion stays above your chosen level for a few seconds." checked={s.notifications.congestion_alerts} onChange={(v) => !ro && setS({ ...s, notifications: { ...s.notifications, congestion_alerts: v } })} />
        <Field label="Alert from level"><Select disabled={ro} value={s.notifications.min_congestion_level} onChange={(e) => setS({ ...s, notifications: { ...s.notifications, min_congestion_level: e.target.value as never } })}><option>Moderate</option><option>High</option><option>Critical</option></Select></Field>
        <Toggle label="Violation alerts" hint="Alert whenever a confirmed violation with evidence is recorded." checked={s.notifications.violation_alerts} onChange={(v) => !ro && setS({ ...s, notifications: { ...s.notifications, violation_alerts: v } })} />
      </>)}
      {!ro && <div className="flex justify-end"><Button variant="primary" loading={saving} disabled={s.classes.length === 0} onClick={save}><Save className="h-4 w-4" />Save settings</Button></div>}
    </Card>
  );
}

/* ----------------------------------------------------- cameras, lines, zones */
function DetectionSetup({ initialCamera }: { initialCamera: string | null }) {
  const { can } = useAuth();
  const toast = useToast();
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const vids = useFetch(async () => (await api.get<Page<Video>>("/api/videos", { params: { page_size: 50 } })).data, []);
  const [camId, setCamId] = useState<string>(initialCamera ?? "");
  const [cfg, setCfg] = useState<CameraConfig | null>(null);
  const [bg, setBg] = useState("auto");
  const [saving, setSaving] = useState(false);
  const cam = (cams.data ?? []).find((c) => String(c.id) === camId) ?? null;
  useEffect(() => { if (!camId && cams.data?.length) setCamId(String(cams.data[0].id)); }, [cams.data, camId]);
  useEffect(() => { setCfg(cam ? structuredClone(cam.config) : null); }, [cam?.id, cams.data]); // eslint-disable-line react-hooks/exhaustive-deps
  const ro = !can("admin");
  const bgUrl = bg === "none" ? null : bg === "auto" ? (cam && cam.source_type !== "none" ? mediaUrl(`/api/cameras/${cam.id}/snapshot`) : null) : mediaUrl(`/api/videos/${bg}/frame`);

  const save = async () => {
    if (!cam || !cfg) return;
    if (cfg.calibration.enabled && !cfg.calibration.meters_per_pixel) { toast.push("error", "Set the speed scale before enabling overspeed detection."); return; }
    if (cfg.signal.enabled && !cfg.signal.stop_line) { toast.push("error", "Draw a stop line before enabling red-light detection."); return; }
    setSaving(true);
    try {
      await api.put(`/api/cameras/${cam.id}`, { name: cam.name, location: cam.location, latitude: cam.latitude, longitude: cam.longitude, source_type: cam.source_type, source: cam.source, config: cfg });
      toast.push("success", "Detection setup saved"); await cams.reload(true);
    } catch (e) { toast.push("error", errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex flex-wrap items-end gap-4">
          <Field label="Camera"><Select value={camId} onChange={(e) => setCamId(e.target.value)} className="min-w-[240px]">{(cams.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Drawing background" hint="A frame to trace lines and zones on."><Select value={bg} onChange={(e) => setBg(e.target.value)} className="min-w-[240px]"><option value="auto">Camera snapshot (if available)</option>{(vids.data?.items ?? []).map((v) => <option key={v.id} value={v.id}>First frame of {v.original_name}</option>)}<option value="none">Blank canvas</option></Select></Field>
        </div>
      </Card>
      {!cam || !cfg ? <Skeleton className="h-96" /> : (<>
        <Card><CardHeader title="Counting lines and zones" subtitle="Click on the frame to draw. Shapes use relative coordinates, so they still fit if the resolution changes." />
          <GeometryEditor config={cfg} onChange={ro ? () => undefined : setCfg} background={bgUrl} /></Card>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="space-y-4"><CardHeader title="Red-light detection" subtitle="Off unless you configure a signal and a stop line." />
            <Toggle label="Enable red-light detection" checked={cfg.signal.enabled} onChange={(v) => !ro && setCfg({ ...cfg, signal: { ...cfg.signal, enabled: v } })} />
            <div className="flex gap-2 rounded-xl bg-raised/60 p-3 text-xs text-muted"><Info className="h-4 w-4 shrink-0 text-cyan" /><p>The signal state is <b>configured here</b>, not read from the video. Use a fixed cycle that matches the real signal, or set it manually. A vehicle is only flagged if it crosses the stop line while the configured state is red.</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Signal source"><Select disabled={ro} value={cfg.signal.mode} onChange={(e) => setCfg({ ...cfg, signal: { ...cfg.signal, mode: e.target.value as "manual" | "cycle" } })}><option value="manual">Manual state</option><option value="cycle">Fixed cycle</option></Select></Field>
              {cfg.signal.mode === "manual" ? <Field label="State"><Select disabled={ro} value={cfg.signal.manual_state} onChange={(e) => setCfg({ ...cfg, signal: { ...cfg.signal, manual_state: e.target.value as "red" | "green" } })}><option value="red">Red</option><option value="green">Green</option></Select></Field>
                : <><Field label="Red seconds"><Input type="number" min={1} disabled={ro} value={cfg.signal.red_seconds} onChange={(e) => setCfg({ ...cfg, signal: { ...cfg.signal, red_seconds: +e.target.value || 1 } })} /></Field><Field label="Green seconds"><Input type="number" min={1} disabled={ro} value={cfg.signal.green_seconds} onChange={(e) => setCfg({ ...cfg, signal: { ...cfg.signal, green_seconds: +e.target.value || 1 } })} /></Field></>}
              <Field label="Violating direction"><Select disabled={ro} value={cfg.signal.violation_direction} onChange={(e) => setCfg({ ...cfg, signal: { ...cfg.signal, violation_direction: e.target.value as "in" | "out" } })}><option value="in">Crossing 'in' (top to bottom for a left-to-right line)</option><option value="out">Crossing 'out'</option></Select></Field>
            </div>
            <div className="flex items-center gap-2 text-sm">Stop line: {cfg.signal.stop_line ? <Badge color="#34D399">drawn</Badge> : <Badge color="#FBBF24">not drawn - use the Stop line tool</Badge>}{cfg.signal.stop_line && !ro && <Button size="sm" variant="ghost" onClick={() => setCfg({ ...cfg, signal: { ...cfg.signal, stop_line: null } })}>Remove</Button>}</div>
          </Card>
          <Card className="space-y-4"><CardHeader title="Speed calibration" subtitle="Overspeed detection needs a real-world scale." />
            <Toggle label="Enable overspeed detection" checked={cfg.calibration.enabled} onChange={(v) => !ro && setCfg({ ...cfg, calibration: { ...cfg.calibration, enabled: v } })} />
            <div className="flex gap-2 rounded-xl bg-warn/10 p-3 text-xs"><AlertTriangle className="h-4 w-4 shrink-0 text-warn" /><p>Speed from one camera is only an <b>estimate</b>. It assumes a flat road and one metres-per-pixel value, but perspective makes that scale vary across the frame (far vehicles look slower). Calibrate with a known length near the lane you care about and treat results as indicative, not legal evidence.</p></div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Metres per pixel" hint="Use the Speed scale tool, or enter a value."><Input type="number" step="any" min={0} disabled={ro} value={cfg.calibration.meters_per_pixel ?? ""} onChange={(e) => setCfg({ ...cfg, calibration: { ...cfg.calibration, meters_per_pixel: e.target.value ? +e.target.value : null } })} /></Field>
              <Field label="Speed limit (km/h)"><Input type="number" min={5} max={250} disabled={ro} value={cfg.calibration.speed_limit_kmh} onChange={(e) => setCfg({ ...cfg, calibration: { ...cfg.calibration, speed_limit_kmh: +e.target.value || 60 } })} /></Field>
            </div>
          </Card>
        </div>
        {!ro && <div className="flex justify-end"><Button variant="primary" loading={saving} onClick={save}><Save className="h-4 w-4" />Save detection setup</Button></div>}
        <p className="text-xs text-muted">Wrong-way detection uses a "Wrong-way lane" zone with its allowed direction. Restricted-zone detection uses "Restricted" zones. Each check only runs when configured.</p>
      </>)}
    </div>
  );
}

/* -------------------------------------------------------------- appearance */
function Appearance() {
  const { theme, toggle } = useTheme();
  const { can } = useAuth();
  const toast = useToast();
  const remote = useFetch(async () => (await api.get<AppSettings>("/api/settings")).data, []);
  const [busy, setBusy] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const setDemo = async (v: boolean) => {
    if (!remote.data) return;
    try { await api.put("/api/settings", { ...remote.data, demo_mode: v }); await remote.reload(true); toast.push("success", v ? "Demo data is now included" : "Demo data hidden - showing real results only"); } catch (e) { toast.push("error", errMsg(e)); }
  };
  const refresh = async () => { setBusy(true); try { await api.post("/api/demo/refresh"); toast.push("success", "Demo data regenerated"); } catch (e) { toast.push("error", errMsg(e)); } finally { setBusy(false); setConfirm(false); } };
  return (
    <Card className="max-w-3xl space-y-6">
      <CardHeader title="Appearance" />
      <div className="flex items-center justify-between"><div><p className="text-sm font-medium">Theme</p><p className="text-xs text-muted">Stored in this browser.</p></div><Segmented label="Theme" value={theme} onChange={() => toggle()} options={[{ value: "dark", label: "Dark" }, { value: "light", label: "Light" }]} /></div>
      <div className="border-t border-line/60 pt-6"><CardHeader title="Demo data" subtitle="Simulated traffic, violations and alerts so the dashboard is usable without a camera. Always labelled DEMO." />
        {remote.data && <Toggle label="Include demo data in dashboards and reports" hint="Turn off to see only results produced by the AI pipeline from your videos and cameras." checked={remote.data.demo_mode} onChange={(v) => can("admin") ? void setDemo(v) : toast.push("error", "Only admins can change this.")} />}
        {can("admin") && <Button className="mt-4" loading={busy} onClick={() => setConfirm(true)}><RefreshCw className="h-4 w-4" />Regenerate demo data</Button>}
      </div>
      <ConfirmDialog open={confirm} title="Regenerate demo data?" message="Simulated analytics, violations and alerts are replaced with a fresh set ending now. Real results are not touched." confirmLabel="Regenerate" onConfirm={refresh} onCancel={() => setConfirm(false)} />
    </Card>
  );
}

/* ------------------------------------------------------------ admin panel */
function AdminPanel() {
  const toast = useToast();
  const { user } = useAuth();
  const users = useFetch(async () => (await api.get<User[]>("/api/users")).data, []);
  const logs = useFetch(async () => (await api.get<ActivityLog[]>("/api/logs/activity", { params: { limit: 60 } })).data, []);
  const setRole = async (u: User, role: string) => { try { await api.put(`/api/users/${u.id}/role`, { role }); toast.push("success", `${u.email} is now ${role}`); await users.reload(true); await logs.reload(true); } catch (e) { toast.push("error", errMsg(e)); } };
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card><CardHeader title="Users and roles" subtitle="Viewers read, operators run analysis, admins configure." />
        {users.loading ? <Skeleton className="h-40" /> : users.error ? <ErrorState message={users.error} onRetry={() => users.reload()} /> : <ul className="divide-y divide-line/40">{users.data?.map((u) => (
          <li key={u.id} className="flex items-center justify-between gap-3 py-3"><div className="min-w-0"><p className="truncate text-sm font-medium">{u.username}</p><p className="truncate text-xs text-muted">{u.email}</p></div>
            <Select aria-label={`Role for ${u.email}`} className="!w-auto" value={u.role} disabled={u.id === user?.id} onChange={(e) => void setRole(u, e.target.value)}><option value="viewer">Viewer</option><option value="operator">Operator</option><option value="admin">Admin</option></Select></li>))}</ul>}
      </Card>
      <Card><CardHeader title="Admin activity log" subtitle="Who did what, most recent first." />
        {logs.loading ? <Skeleton className="h-40" /> : <ul className="max-h-[420px] divide-y divide-line/40 overflow-auto">{logs.data?.map((l) => (<li key={l.id} className="py-2.5 text-sm"><p><b className="font-medium">{l.action.replace(/_/g, " ")}</b> <span className="text-muted">{l.detail}</span></p><p className="text-xs text-muted">{l.user_email} - {fmtDateTime(l.created_at)}{l.ip ? ` - ${l.ip}` : ""}</p></li>))}</ul>}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------ system health */
function SystemHealthCard() {
  const h = useFetch(async () => (await api.get<SystemHealth>("/api/system/health")).data, []);
  useEffect(() => { const id = setInterval(() => h.reload(true), 10000); return () => clearInterval(id); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  if (h.error) return <Card><ErrorState message={h.error} onRetry={() => h.reload()} /></Card>;
  if (!h.data) return <Skeleton className="h-64" />;
  const d = h.data;
  const row = (k: string, v: React.ReactNode) => <div className="flex items-center justify-between gap-4 border-b border-line/40 py-2.5 text-sm last:border-0"><span className="text-muted">{k}</span><span className="text-right">{v}</span></div>;
  return (
    <div className="grid max-w-5xl gap-4 lg:grid-cols-2">
      <Card><CardHeader title="Services" />
        {row("API and database", <Badge color={d.database.ok ? "#34D399" : "#F87171"}>{d.database.ok ? `OK (${d.database.engine})` : "Unavailable"}</Badge>)}
        {row("YOLO weights", <Badge color={d.model.available ? "#34D399" : "#F87171"}>{d.model.available ? d.model.weights : "Missing"}</Badge>)}
        {row("Inference device", <span className="num">{d.model.device}</span>)}
        {row("Live cameras / video jobs", <span className="num">{d.active_cameras} / {d.active_video_jobs}</span>)}
        {row("WebSocket clients", <span className="num">{d.websocket_clients}</span>)}
        {row("Uptime", <span className="num">{Math.floor(d.uptime_s / 3600)}h {Math.floor((d.uptime_s % 3600) / 60)}m</span>)}
        {!d.model.available && <p className="mt-3 rounded-lg bg-danger/10 p-3 text-xs text-danger">Weights not found at {d.model.path}. Run scripts\setup.ps1 (Windows) or python scripts/download_weights.py, then restart the backend.</p>}
      </Card>
      <Card><CardHeader title="Resources" />
        <div className="space-y-4">{[["CPU", d.cpu_percent], ["Memory", d.memory_percent], ["Disk", d.disk.percent]].map(([k, v]) => <div key={k as string}><div className="mb-1 flex justify-between text-sm"><span>{k}</span><span className="num">{v}%</span></div><ProgressBar value={v as number} color={(v as number) > 85 ? "rgb(var(--danger))" : "rgb(var(--brand))"} /></div>)}</div>
        <p className="mt-4 text-xs text-muted">{d.disk.free_gb} GB free of {d.disk.total_gb} GB - Python {d.python} - {d.environment}</p>
      </Card>
    </div>
  );
}
