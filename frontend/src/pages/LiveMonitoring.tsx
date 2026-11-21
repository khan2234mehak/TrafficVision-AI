import { Camera as CamIcon, Play, Radio, Square, VideoOff } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, DensityMeter, EmptyState, ErrorState, PageHeader, Select, Skeleton } from "../components/ui";
import { useAuth, useToast } from "../context/AppContext";
import { useChannel, useFetch } from "../hooks";
import { api, errMsg, mediaUrl, wsUrl } from "../services/api";
import type { Camera, LiveStats } from "../types";
import { CATEGORY_LABEL, CLASS_COLOR, CLASS_LABEL, fmtNum } from "../utils/format";

export default function LiveMonitoring() {
  const { can } = useAuth();
  const toast = useToast();
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const [camId, setCamId] = useState<number | null>(null);
  const [active, setActive] = useState(false);
  const [stats, setStats] = useState<LiveStats | null>(null);
  const [fps, setFps] = useState(0);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [frame, setFrame] = useState<string | null>(null);
  const [streamKey, setStreamKey] = useState(0);
  const video = useRef<HTMLVideoElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const ws = useRef<WebSocket | null>(null);
  const media = useRef<MediaStream | null>(null);

  const usable = (cams.data ?? []).filter((c) => c.source_type !== "none");
  const cam = (cams.data ?? []).find((c) => c.id === camId) ?? null;

  useEffect(() => { if (camId == null && usable.length) setCamId(usable[0].id); }, [usable, camId]);

  // resume the view if this camera is already being analysed on the server
  useEffect(() => {
    if (!cam || cam.source_type === "browser") { setActive(false); return; }
    api.get(`/api/monitoring/${cam.id}/state`).then((r) => {
      setActive(r.data.active); setStats(r.data.stats); setProblem(r.data.active ? null : r.data.error);
      if (r.data.active) setStreamKey((k) => k + 1);
    }).catch(() => undefined);
  }, [cam?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useChannel("/ws/traffic", (m) => {
    if (m.type === "live_stats" && m.camera_id === camId && cam?.source_type !== "browser") { setStats(m.stats); setFps(m.fps); }
    if (m.type === "camera_status" && m.camera_id === camId) {
      if (m.status !== "online") { setActive(false); setProblem(m.error ?? null); if (m.error) toast.push("error", m.error); cams.reload(true); }
    }
  });

  const releaseBrowser = useCallback(() => {
    ws.current?.close(); ws.current = null;
    media.current?.getTracks().forEach((t) => t.stop()); media.current = null;
    if (video.current) video.current.srcObject = null;
  }, []);
  useEffect(() => releaseBrowser, [releaseBrowser]);

  const startBrowser = async (id: number) => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 960 }, height: { ideal: 540 } }, audio: false });
    } catch (e) {
      const n = (e as DOMException).name;
      throw new Error(n === "NotAllowedError" ? "Camera permission was denied. Allow camera access in your browser's site settings and try again."
        : n === "NotFoundError" ? "No camera was found on this device." : n === "NotReadableError" ? "The camera is in use by another application."
        : "Could not access the camera. Browsers only allow it on localhost or HTTPS.");
    }
    media.current = stream;
    if (video.current) { video.current.srcObject = stream; await video.current.play().catch(() => undefined); }
    await api.post("/api/monitoring/start", { camera_id: id });
    const socket = new WebSocket(wsUrl("/ws/webcam", { camera_id: id }));
    ws.current = socket;
    const send = () => {
      const v = video.current, c = canvas.current;
      if (!v || !c || socket.readyState !== 1 || !v.videoWidth) { window.setTimeout(send, 150); return; }
      const w = Math.min(640, v.videoWidth); c.width = w; c.height = Math.round((w * v.videoHeight) / v.videoWidth);
      c.getContext("2d")?.drawImage(v, 0, 0, c.width, c.height);
      c.toBlob((b) => b && socket.readyState === 1 && socket.send(b), "image/jpeg", 0.7);
    };
    socket.onopen = send;
    socket.onmessage = (e) => {
      const m = JSON.parse(e.data);
      if (m.type === "frame") { setFrame(`data:image/jpeg;base64,${m.image}`); setStats(m.stats); setFps(m.fps); window.setTimeout(send, 60); }
      else if (m.type === "error") { setProblem(m.message); toast.push("error", m.message); }
    };
    socket.onclose = () => { setActive(false); media.current?.getTracks().forEach((t) => t.stop()); };
  };

  const start = async () => {
    if (!cam) return;
    setBusy(true); setProblem(null); setStats(null); setFrame(null);
    try {
      if (cam.source_type === "browser") await startBrowser(cam.id);
      else { await api.post("/api/monitoring/start", { camera_id: cam.id }); setStreamKey((k) => k + 1); }
      setActive(true); toast.push("success", `Monitoring ${cam.name}`); cams.reload(true);
    } catch (e) {
      releaseBrowser();
      const msg = e instanceof Error && !("response" in e) ? e.message : errMsg(e);
      setProblem(msg); toast.push("error", msg);
    } finally { setBusy(false); }
  };
  const stop = async () => {
    if (!cam) return;
    setBusy(true);
    try { releaseBrowser(); await api.post("/api/monitoring/stop", { camera_id: cam.id }); setActive(false); toast.push("info", "Monitoring stopped"); cams.reload(true); }
    catch (e) { toast.push("error", errMsg(e)); } finally { setBusy(false); }
  };

  const modeLabel = cam ? { browser: "Browser webcam", webcam: "Server webcam", stream: "Network stream", file: "Recorded sample video", none: "No source" }[cam.source_type] : "";

  return (
    <>
      <PageHeader title="Live monitoring" subtitle="Real-time detection, tracking IDs and counts from a camera, stream or recorded sample video."
        actions={<>
          <Select aria-label="Select camera" className="!w-auto min-w-[220px]" value={camId ?? ""} disabled={active || busy} onChange={(e) => { setCamId(Number(e.target.value)); setStats(null); setFrame(null); setProblem(null); }}>
            {usable.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </Select>
          {can("operator") && (active
            ? <Button variant="danger" loading={busy} onClick={stop}><Square className="h-4 w-4" />Stop</Button>
            : <Button variant="primary" loading={busy} disabled={!cam} onClick={start}><Play className="h-4 w-4" />Start monitoring</Button>)}
        </>} />

      {cams.loading ? <Skeleton className="h-[460px]" /> : cams.error ? <Card><ErrorState message={cams.error} onRetry={() => cams.reload()} /></Card> : usable.length === 0 ? (
        <Card><EmptyState icon={<VideoOff className="h-6 w-6" />} title="No camera with a video source yet" hint="Add a camera with a browser webcam, server webcam, stream URL or a sample video, then come back to start monitoring."
          action={<Link to="/cameras"><Button variant="primary">Open camera management</Button></Link>} /></Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
          <Card className="p-3">
            <div className="relative aspect-video w-full overflow-hidden rounded-xl bg-black">
              {active && cam && cam.source_type !== "browser" && <img key={streamKey} src={mediaUrl(`/api/monitoring/stream/${cam.id}`)} alt="Annotated live feed" className="h-full w-full object-contain" onError={() => undefined} />}
              {active && cam?.source_type === "browser" && frame && <img src={frame} alt="Annotated webcam feed" className="h-full w-full object-contain" />}
              <video ref={video} className="hidden" muted playsInline /><canvas ref={canvas} className="hidden" />
              {!active && <div className="absolute inset-0 grid place-items-center p-6 text-center"><div><Radio className="mx-auto mb-3 h-10 w-10 text-muted" /><p className="font-display text-lg">Ready when you are</p><p className="mt-1 text-sm text-muted">{cam ? `${cam.name} - ${modeLabel}` : "Choose a camera"}</p></div></div>}
              {active && <div className="absolute left-3 top-3 flex items-center gap-2"><Badge color="#34D399"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-ok" />Live analysis</Badge>{cam?.source_type === "file" && <Badge color="#A78BFA">Recorded file</Badge>}<span className="num rounded-full bg-black/60 px-2 py-0.5 text-xs text-white">{fps} fps</span></div>}
            </div>
            {problem && <div className="mt-3 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger" role="alert">{problem}</div>}
            <p className="mt-3 px-1 text-xs text-muted">{cam?.source_type === "file" ? "This camera plays a recorded sample video once through the real AI pipeline. It is not a live CCTV feed." : "Boxes show class, tracking ID and confidence; coloured trails show each vehicle's path. Red boxes mark flagged violations."}</p>
          </Card>

          <div className="space-y-4">
            <Card>
              <CardHeader title="Traffic density" />
              <DensityMeter level={stats?.density.level ?? null} ratio={stats?.density.ratio} />
              {stats?.density.zones?.length ? <ul className="mt-3 space-y-1 text-xs text-muted">{stats.density.zones.map((z) => <li key={z.id} className="flex justify-between"><span>{z.name}</span><span className="num">{z.vehicles} vehicles - {z.level}</span></li>)}</ul> : null}
            </Card>
            <Card>
              <CardHeader title="Counts" />
              <div className="grid grid-cols-3 gap-3 text-center">
                <div><p className="num font-display text-2xl">{stats?.vehicles_in_frame ?? 0}</p><p className="text-xs text-muted">In frame</p></div>
                <div><p className="num font-display text-2xl">{fmtNum(stats?.total_count ?? 0)}</p><p className="text-xs text-muted">Counted</p></div>
                <div><p className="num font-display text-2xl">{stats?.vehicles_per_minute ?? 0}</p><p className="text-xs text-muted">Per minute</p></div>
              </div>
              <ul className="mt-4 space-y-2">
                {Object.keys(CLASS_COLOR).map((k) => (<li key={k} className="flex items-center justify-between text-sm"><span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-sm" style={{ background: CLASS_COLOR[k] }} />{CLASS_LABEL[k]}</span><span className="num font-medium">{stats?.by_class?.[k] ?? 0}</span></li>))}
              </ul>
              {stats?.by_line?.length ? <div className="mt-4 border-t border-line/60 pt-3"><p className="mb-1 text-xs text-muted">Counting lines</p>{stats.by_line.map((l) => <p key={l.id} className="num flex justify-between text-sm"><span>{l.name}</span><span>{l.total} <span className="text-xs text-muted">(in {l.in} / out {l.out})</span></span></p>)}</div> : null}
            </Card>
            <Card>
              <CardHeader title="Violation modules" subtitle="Only configured checks run" />
              {stats ? (stats.active_violation_modules.length ? <div className="flex flex-wrap gap-2">{stats.active_violation_modules.map((m) => <Badge key={m} color="#38BDF8">{CATEGORY_LABEL[m] ?? m}: {stats.violations[m] ?? 0}</Badge>)}</div> : <p className="text-sm text-muted">None enabled for this camera. Add restricted zones, a wrong-way lane, calibration or a stop line in <Link to={`/settings?camera=${cam?.id}`} className="text-cyan hover:underline">Settings</Link>.</p>) : <p className="text-sm text-muted">Start monitoring to see status.</p>}
              {stats?.signal_state && <p className="mt-3 text-sm">Configured signal: <b className={stats.signal_state === "red" ? "text-danger" : "text-ok"}>{stats.signal_state}</b></p>}
            </Card>
          </div>
        </div>
      )}
      {cam && <p className="mt-4 flex items-center gap-2 text-xs text-muted"><CamIcon className="h-3.5 w-3.5" />{cam.location || "No location set"}</p>}
    </>
  );
}
