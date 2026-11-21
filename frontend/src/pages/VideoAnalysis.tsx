import { Download, FileVideo, Pause, Play, Square, Trash2, UploadCloud } from "lucide-react";
import { DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { HeatmapCanvas } from "../components/Heatmap";
import { Badge, Button, Card, CardHeader, ConfirmDialog, EmptyState, ErrorState, LevelBadge, PageHeader, ProgressBar, Select, Skeleton, Tooltip } from "../components/ui";
import { useAuth, useToast } from "../context/AppContext";
import { useChannel, useFetch } from "../hooks";
import { api, errMsg, mediaUrl } from "../services/api";
import type { Camera, LiveStats, Page, Video, VideoResult } from "../types";
import { CATEGORY_LABEL, CLASS_COLOR, CLASS_LABEL, fmtBytes, fmtDuration, fmtNum } from "../utils/format";

const OK_EXT = [".mp4", ".avi", ".mov"];
const STATUS_COLOR: Record<string, string> = { uploaded: "#64748B", queued: "#38BDF8", processing: "#3B82FF", paused: "#FBBF24", completed: "#34D399", failed: "#F87171", stopped: "#FB923C" };

export default function VideoAnalysis() {
  const { can } = useAuth();
  const toast = useToast();
  const list = useFetch(async () => (await api.get<Page<Video>>("/api/videos", { params: { page_size: 30 } })).data, []);
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const [selId, setSelId] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const [uploading, setUploading] = useState<number | null>(null);
  const [camId, setCamId] = useState("");
  const [stride, setStride] = useState("1");
  const [live, setLive] = useState<{ progress: number; stats: LiveStats | null; fpsProc?: number } | null>(null);
  const [previewKey, setPreviewKey] = useState(0);
  const [result, setResult] = useState<VideoResult | null>(null);
  const [toDelete, setToDelete] = useState<Video | null>(null);
  const [busy, setBusy] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const videos = list.data?.items ?? [];
  const sel = videos.find((v) => v.id === selId) ?? null;
  const running = sel && ["queued", "processing", "paused"].includes(sel.status);

  useEffect(() => { if (selId == null && videos.length) setSelId(videos[0].id); }, [videos, selId]);
  useEffect(() => {
    setResult(null); setLive(null);
    if (sel?.status === "completed" || sel?.status === "stopped") api.get(`/api/videos/${sel.id}/result`).then((r) => setResult(r.data.result)).catch(() => undefined);
  }, [selId, sel?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  useChannel("/ws/traffic", (m) => {
    if (m.video_id !== selId && m.type !== "video_status") return;
    if (m.type === "video_progress" && m.video_id === selId) { setLive({ progress: m.progress, stats: m.stats, fpsProc: m.fps_processing }); setPreviewKey((k) => k + 1); }
    if (m.type === "video_status") {
      list.reload(true);
      if (m.status === "failed" && m.video_id === selId) toast.push("error", m.error ?? "Processing failed");
      if (m.status === "completed" && m.video_id === selId) toast.push("success", "Analysis complete");
    }
  });
  const poll = useCallback(() => { if (running) list.reload(true); }, [running]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const id = window.setInterval(poll, 4000); return () => window.clearInterval(id); }, [poll]);

  const upload = async (file: File) => {
    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (!OK_EXT.includes(ext)) { toast.push("error", "Unsupported file type. Upload an MP4, AVI or MOV video."); return; }
    if (file.size > 500 * 1024 * 1024) { toast.push("error", "That file is over the 500 MB limit."); return; }
    const fd = new FormData(); fd.append("file", file);
    setUploading(0);
    try {
      const r = await api.post<Video>("/api/videos/upload", fd, { timeout: 0, onUploadProgress: (e) => setUploading(e.total ? Math.round((100 * e.loaded) / e.total) : 50) });
      toast.push("success", `${file.name} uploaded`);
      await list.reload(true); setSelId(r.data.id);
    } catch (e) { toast.push("error", errMsg(e)); } finally { setUploading(null); }
  };
  const onDrop = (e: DragEvent) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files?.[0]; if (f && can("operator")) void upload(f); };

  const act = async (path: string, ok?: string) => {
    setBusy(true);
    try { await api.post(path); if (ok) toast.push("info", ok); await list.reload(true); } catch (e) { toast.push("error", errMsg(e)); } finally { setBusy(false); }
  };
  const process = async () => {
    if (!sel) return;
    setBusy(true); setResult(null); setLive({ progress: 0, stats: null });
    try {
      await api.post("/api/videos/process", { video_id: sel.id, camera_id: camId ? Number(camId) : null, frame_stride: Number(stride) });
      toast.push("info", "Processing started"); await list.reload(true);
    } catch (e) { toast.push("error", errMsg(e)); setLive(null); } finally { setBusy(false); }
  };
  const remove = async () => {
    if (!toDelete) return;
    try { await api.delete(`/api/videos/${toDelete.id}`); toast.push("success", "Video deleted"); if (selId === toDelete.id) setSelId(null); setToDelete(null); await list.reload(true); }
    catch (e) { toast.push("error", errMsg(e)); }
  };

  const progress = running ? Math.max(live?.progress ?? 0, sel!.progress) : sel?.progress ?? 0;

  return (
    <>
      <PageHeader title="Video analysis" subtitle="Upload an MP4, AVI or MOV file. Every frame goes through YOLO detection and ByteTrack tracking, and you get an annotated video back." />
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <Card>
            <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
              className={`rounded-2xl border-2 border-dashed p-6 text-center transition ${drag ? "border-cyan bg-cyan/10" : "border-line"}`}>
              <UploadCloud className="mx-auto h-9 w-9 text-brand" />
              <p className="mt-2 font-display font-semibold">Drop a traffic video here</p>
              <p className="mt-1 text-xs text-muted">MP4, AVI or MOV, up to 500 MB</p>
              <input ref={input} type="file" accept=".mp4,.avi,.mov,video/mp4,video/quicktime,video/x-msvideo" className="hidden" aria-label="Choose a video file" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
              <Button className="mt-4" variant="primary" disabled={!can("operator") || uploading != null} onClick={() => input.current?.click()}>Choose file</Button>
              {!can("operator") && <p className="mt-2 text-xs text-warn">Your role is read-only. Ask an admin for operator access to upload.</p>}
              {uploading != null && <div className="mt-4"><ProgressBar value={uploading} /><p className="num mt-1 text-xs text-muted">Uploading {uploading}%</p></div>}
            </div>
          </Card>
          <Card className="p-0">
            <div className="border-b border-line/60 px-5 py-3 text-sm font-semibold">Your videos</div>
            {list.loading ? <div className="space-y-2 p-4">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-14" />)}</div> : list.error ? <ErrorState message={list.error} onRetry={() => list.reload()} /> : videos.length === 0 ? (
              <EmptyState icon={<FileVideo className="h-6 w-6" />} title="No videos yet" hint="Upload your first clip to see detection results." />
            ) : <ul className="max-h-[420px] overflow-auto">{videos.map((v) => (
              <li key={v.id}><button onClick={() => setSelId(v.id)} className={`flex w-full items-center gap-3 border-b border-line/40 px-5 py-3 text-left transition last:border-0 hover:bg-raised ${v.id === selId ? "bg-brand/10" : ""}`}>
                <FileVideo className="h-5 w-5 shrink-0 text-muted" /><div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{v.original_name}</p><p className="num text-xs text-muted">{fmtBytes(v.size_bytes)} - {fmtDuration(v.duration_s)}</p></div>
                <Badge color={STATUS_COLOR[v.status]}>{v.status}</Badge></button></li>))}</ul>}
          </Card>
        </div>

        <div className="space-y-4">
          {!sel ? <Card><EmptyState icon={<FileVideo className="h-6 w-6" />} title="Select or upload a video" hint="Results, the annotated output and heatmaps appear here." /></Card> : (<>
            <Card>
              <CardHeader title={sel.original_name} subtitle={`${sel.width}x${sel.height} - ${sel.fps?.toFixed(0)} fps - ${fmtDuration(sel.duration_s)} - ${sel.total_frames ?? "?"} frames`}
                action={can("operator") && <Button size="sm" variant="danger" onClick={() => setToDelete(sel)}><Trash2 className="h-4 w-4" />Delete</Button>} />
              <div className="grid gap-4 lg:grid-cols-2">
                <div><p className="mb-2 text-xs text-muted">Original</p><video key={`o${sel.id}`} src={mediaUrl(`/api/videos/${sel.id}/original`)} controls preload="metadata" className="aspect-video w-full rounded-xl bg-black" /></div>
                <div>
                  <p className="mb-2 text-xs text-muted">Annotated output</p>
                  {running ? (
                    <div className="relative aspect-video overflow-hidden rounded-xl bg-black">
                      {previewKey > 0 && <img src={mediaUrl(`/api/videos/${sel.id}/preview`, { k: previewKey })} alt="Live annotated preview" className="h-full w-full object-contain" />}
                      <span className="absolute left-2 top-2"><Badge color="#3B82FF">Processing preview</Badge></span>
                    </div>
                  ) : sel.has_processed && sel.browser_playable ? <video key={`p${sel.id}${sel.status}`} src={mediaUrl(`/api/videos/${sel.id}/processed`)} controls preload="metadata" className="aspect-video w-full rounded-xl bg-black" />
                    : sel.has_processed ? <div className="grid aspect-video place-items-center rounded-xl border border-line p-4 text-center text-sm text-muted">The annotated video could not be re-encoded for the browser. Use Download to play it in VLC or Windows Media Player.</div>
                    : <div className="grid aspect-video place-items-center rounded-xl border border-dashed border-line p-4 text-center text-sm text-muted">Process the video to generate the annotated output.</div>}
                </div>
              </div>
            </Card>

            <Card>
              <CardHeader title="Processing" subtitle="Detection runs in a background worker, so the app stays responsive." action={<Badge color={STATUS_COLOR[sel.status]}>{sel.status}</Badge>} />
              {!running && can("operator") && (
                <div className="flex flex-wrap items-end gap-3">
                  <label className="text-sm">Detection setup<Select className="mt-1 min-w-[220px]" value={camId} onChange={(e) => setCamId(e.target.value)}><option value="">Default (one counting line, whole-frame density)</option>{(cams.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></label>
                  <label className="text-sm"><Tooltip text="Run detection on every Nth frame. Higher is faster on CPU but may miss quick vehicles.">Speed vs accuracy</Tooltip><Select className="mt-1" value={stride} onChange={(e) => setStride(e.target.value)}><option value="1">Every frame (most accurate)</option><option value="2">Every 2nd frame</option><option value="3">Every 3rd frame</option></Select></label>
                  <Button variant="primary" loading={busy} onClick={process}><Play className="h-4 w-4" />{sel.status === "completed" ? "Process again" : "Start analysis"}</Button>
                </div>
              )}
              {running && (<div className="space-y-3">
                <ProgressBar value={progress} /><div className="flex flex-wrap items-center justify-between gap-2 text-sm"><span className="num">{progress.toFixed(1)}%{live?.fpsProc ? ` - ${live.fpsProc} frames/s` : ""}</span>
                  <div className="flex gap-2">{sel.status === "paused" ? <Button size="sm" loading={busy} onClick={() => act(`/api/videos/${sel.id}/resume`, "Resumed")}><Play className="h-4 w-4" />Resume</Button> : <Button size="sm" loading={busy} onClick={() => act(`/api/videos/${sel.id}/pause`, "Paused")}><Pause className="h-4 w-4" />Pause</Button>}
                    <Button size="sm" variant="danger" loading={busy} onClick={() => act(`/api/videos/${sel.id}/stop`, "Stopping and saving partial results")}><Square className="h-4 w-4" />Stop</Button></div></div>
                {live?.stats && <div className="num flex flex-wrap gap-5 text-sm text-muted"><span>In frame <b className="text-ink">{live.stats.vehicles_in_frame}</b></span><span>Counted <b className="text-ink">{live.stats.total_count}</b></span><span>Density <LevelBadge level={live.stats.density.level} /></span></div>}
              </div>)}
              {sel.status === "failed" && <p className="mt-3 rounded-xl border border-danger/40 bg-danger/10 p-3 text-sm text-danger" role="alert">{sel.error}</p>}
              {sel.status === "uploaded" && !can("operator") && <p className="text-sm text-muted">Waiting for an operator to start the analysis.</p>}
            </Card>

            {result && (<>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <Card><p className="text-sm text-muted">Vehicles counted</p><p className="num mt-1 font-display text-3xl">{fmtNum(result.total_count)}</p><p className="mt-1 text-xs text-muted">{result.unique_tracked} unique tracks</p></Card>
                <Card><p className="text-sm text-muted">Peak congestion</p><div className="mt-2"><LevelBadge level={result.peak_density_level} /></div><p className="num mt-2 text-xs text-muted">{Math.round(result.peak_density_ratio * 100)}% occupancy - avg {result.avg_vehicles_per_frame} in frame</p></Card>
                <Card><p className="text-sm text-muted">Violations</p><p className="num mt-1 font-display text-3xl">{result.violations_total}</p><p className="mt-1 text-xs text-muted">{result.violation_modules.length ? result.violation_modules.map((m) => CATEGORY_LABEL[m] ?? m).join(", ") : "No violation modules configured"}</p></Card>
                <Card><p className="text-sm text-muted">Processing time</p><p className="num mt-1 font-display text-3xl">{fmtDuration(result.processing_seconds)}</p><p className="mt-1 text-xs text-muted">{result.frames_processed} frames with {result.model}</p></Card>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                <Card><CardHeader title="Vehicles by type" action={sel.has_processed && <a href={mediaUrl(`/api/videos/${sel.id}/processed`, { download: true })}><Button size="sm" variant="primary"><Download className="h-4 w-4" />Download annotated video</Button></a>} />
                  <ul className="space-y-3">{Object.keys(CLASS_COLOR).map((k) => { const v = result.by_class[k] ?? 0; const max = Math.max(1, ...Object.values(result.by_class)); return (
                    <li key={k}><div className="mb-1 flex justify-between text-sm"><span>{CLASS_LABEL[k]}</span><span className="num font-medium">{v}</span></div><ProgressBar value={(100 * v) / max} color={CLASS_COLOR[k]} /></li>); })}</ul>
                  {result.by_line.length > 0 && <div className="mt-5 border-t border-line/60 pt-3 text-sm">{result.by_line.map((l) => <p key={l.id} className="num flex justify-between"><span>{l.name}</span><span>{l.total} <span className="text-xs text-muted">(in {l.in} / out {l.out})</span></span></p>)}</div>}
                </Card>
                <Card><CardHeader title="Heatmap and movement paths" subtitle="Where vehicles spent time (heat) and how they moved (lines)" /><HeatmapCanvas grid={result.heatmap} trajectories={result.trajectories} background={mediaUrl(`/api/videos/${sel.id}/frame`)} /></Card>
              </div>
            </>)}
          </>)}
        </div>
      </div>
      <ConfirmDialog open={!!toDelete} danger title="Delete this video?" message={`"${toDelete?.original_name}", its annotated output and the violations found in it will be permanently removed.`} confirmLabel="Delete" onConfirm={remove} onCancel={() => setToDelete(null)} />
    </>
  );
}
