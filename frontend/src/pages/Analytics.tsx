import { Activity, Flame } from "lucide-react";
import { useState } from "react";
import { ClassBarChart, DensityLine, DistributionDonut, HourlyBars, TrafficAreaChart } from "../components/charts";
import { HeatmapCanvas } from "../components/Heatmap";
import { Card, CardHeader, DemoBadge, EmptyState, Pagination, PageHeader, Segmented, Select, Skeleton } from "../components/ui";
import { useFetch } from "../hooks";
import { api, mediaUrl, tzOffset } from "../services/api";
import type { Camera, DensityPoint, DistPoint, HourPoint, Page, TrafficPoint, Video } from "../types";
import { CLASS_LABEL, fmtDateTime, fmtNum } from "../utils/format";

type Range = "24h" | "7d" | "30d";
interface Det { id: number; camera: string | null; video_id: number | null; track_id: number; class_name: string; confidence: number; video_time_s: number; timestamp: string }

export default function Analytics() {
  const [range, setRange] = useState<Range>("7d");
  const [cam, setCam] = useState("");
  const [src, setSrc] = useState("");
  const [page, setPage] = useState(1);
  const [cls, setCls] = useState("");
  const tz = tzOffset();
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const vids = useFetch(async () => (await api.get<Page<Video>>("/api/videos", { params: { page_size: 50 } })).data, []);
  const params = { range, tz, camera_id: cam || undefined };
  const traffic = useFetch(async () => (await api.get<{ series: TrafficPoint[]; total: number; distribution: DistPoint[]; interval: string }>("/api/analytics/traffic", { params })).data, [range, cam]);
  const dens = useFetch(async () => (await api.get<{ series: DensityPoint[]; thresholds: number[] }>("/api/analytics/density", { params })).data, [range, cam]);
  const peaks = useFetch(async () => (await api.get<{ hourly: HourPoint[]; peaks: HourPoint[] }>("/api/analytics/peak-hours", { params: { range: range === "24h" ? "24h" : range, tz, camera_id: cam || undefined } })).data, [range, cam]);
  const heat = useFetch(async () => {
    if (!src) return null;
    const [kind, id] = src.split(":");
    return (await api.get<{ heatmap: number[][]; trajectories: number[][][]; label: string; source: string }>("/api/analytics/heatmap", { params: kind === "video" ? { video_id: id } : { camera_id: id } })).data;
  }, [src]);
  const dets = useFetch(async () => (await api.get<Page<Det>>("/api/analytics/detections", { params: { page, page_size: 8, class_name: cls || undefined } })).data, [page, cls]);

  const daily = traffic.data?.interval === "1d";
  const processed = (vids.data?.items ?? []).filter((v) => v.status === "completed" || v.status === "stopped");
  const liveCams = (cams.data ?? []).filter((c) => c.monitoring);
  const bgFor = (s: string) => (s.startsWith("video:") ? mediaUrl(`/api/videos/${s.split(":")[1]}/frame`) : s.startsWith("cam:") ? mediaUrl(`/api/cameras/${s.split(":")[1]}/snapshot`) : null);

  return (
    <>
      <PageHeader title="Traffic analytics" subtitle="Historical flow, congestion patterns, peak periods, heatmaps and detection history."
        actions={<><Select aria-label="Camera filter" className="!w-auto" value={cam} onChange={(e) => setCam(e.target.value)}><option value="">All cameras</option>{(cams.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
          <Segmented label="Range" value={range} onChange={setRange} options={[{ value: "24h", label: "24 h" }, { value: "7d", label: "7 days" }, { value: "30d", label: "30 days" }]} /></>} />
      <div className="grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2"><CardHeader title="Traffic flow" subtitle={`${fmtNum(traffic.data?.total)} vehicles in this period`} action={<Activity className="h-4 w-4 text-muted" />} />{traffic.loading ? <Skeleton className="h-[260px]" /> : <TrafficAreaChart data={traffic.data?.series ?? []} daily={daily} />}</Card>
        <Card><CardHeader title="Vehicle categories" />{traffic.loading ? <Skeleton className="h-[240px]" /> : <DistributionDonut data={traffic.data?.distribution ?? []} />}</Card>
        <Card className="xl:col-span-2"><CardHeader title="Flow by vehicle type" />{traffic.loading ? <Skeleton className="h-[260px]" /> : <ClassBarChart data={(traffic.data?.series ?? []).slice(-24)} daily={daily} />}</Card>
        <Card>
          <CardHeader title="Peak traffic periods" subtitle="Busiest hours of the day (local time)" />
          {peaks.data?.peaks.length ? <ol className="space-y-3">{peaks.data.peaks.map((p, i) => <li key={p.hour} className="flex items-center justify-between rounded-xl bg-raised/60 px-4 py-3"><span className="flex items-center gap-3"><span className="num grid h-7 w-7 place-items-center rounded-lg bg-danger/15 text-sm font-semibold text-danger">{i + 1}</span><span className="num font-display text-lg">{p.label}</span></span><span className="num text-sm text-muted">~{fmtNum(p.avg_vehicles)} vehicles</span></li>)}</ol> : <p className="py-8 text-center text-sm text-muted">Not enough data yet.</p>}
        </Card>
        <Card className="xl:col-span-2"><CardHeader title="Hourly profile" subtitle="Average vehicles per hour of day" />{peaks.loading ? <Skeleton className="h-[240px]" /> : <HourlyBars data={peaks.data?.hourly ?? []} height={240} />}</Card>
        <Card className="xl:col-span-3"><CardHeader title="Congestion over time" subtitle="Occupancy against the Moderate / High / Critical thresholds" />{dens.loading ? <Skeleton className="h-[260px]" /> : <DensityLine data={dens.data?.series ?? []} thresholds={dens.data?.thresholds ?? [0.25, 0.5, 0.75]} daily={daily} />}</Card>
      </div>

      <Card className="mt-4">
        <CardHeader title="Heatmap and vehicle movement" subtitle="Built from real detections of a processed video or a camera that is live right now" action={<Select aria-label="Heatmap source" className="!w-auto min-w-[240px]" value={src} onChange={(e) => setSrc(e.target.value)}><option value="">Choose a source...</option>{processed.map((v) => <option key={v.id} value={`video:${v.id}`}>Video: {v.original_name}</option>)}{liveCams.map((c) => <option key={c.id} value={`cam:${c.id}`}>Live: {c.name}</option>)}</Select>} />
        {!src ? <EmptyState icon={<Flame className="h-6 w-6" />} title="Pick a processed video" hint="Heatmaps and movement paths only come from real AI results, never from demo data. Analyse a video first, then select it here." />
          : heat.loading ? <Skeleton className="aspect-video w-full" /> : heat.error ? <p className="p-6 text-center text-sm text-danger">{heat.error}</p> : <HeatmapCanvas grid={heat.data?.heatmap} trajectories={heat.data?.trajectories} background={bgFor(src)} />}
      </Card>

      <Card className="mt-4">
        <CardHeader title="Detection history" subtitle="One row per tracked vehicle, written by the AI pipeline" action={<Select aria-label="Class filter" className="!w-auto" value={cls} onChange={(e) => { setCls(e.target.value); setPage(1); }}><option value="">All types</option>{Object.keys(CLASS_LABEL).map((k) => <option key={k} value={k}>{CLASS_LABEL[k]}</option>)}</Select>} />
        {dets.loading ? <Skeleton className="h-48" /> : !dets.data?.items.length ? <EmptyState icon={<Activity className="h-6 w-6" />} title="No detections recorded yet" hint="Process a video or start a camera. Demo data does not create detection rows." /> : (<>
          <div className="overflow-x-auto"><table className="w-full min-w-[560px] text-left text-sm"><thead className="text-xs text-muted"><tr><th className="py-2 pr-4 font-medium">Time</th><th className="pr-4 font-medium">Source</th><th className="pr-4 font-medium">Type</th><th className="pr-4 font-medium">Track</th><th className="pr-4 font-medium">Confidence</th><th className="font-medium">Video time</th></tr></thead>
            <tbody>{dets.data.items.map((d) => <tr key={d.id} className="border-t border-line/40"><td className="py-2.5 pr-4">{fmtDateTime(d.timestamp)}</td><td className="pr-4">{d.camera ?? (d.video_id ? `Video #${d.video_id}` : "-")}</td><td className="pr-4">{CLASS_LABEL[d.class_name] ?? d.class_name}</td><td className="num pr-4">#{d.track_id}</td><td className="num pr-4">{Math.round(d.confidence * 100)}%</td><td className="num">{d.video_time_s.toFixed(1)}s</td></tr>)}</tbody></table></div>
          <Pagination page={page} pageSize={8} total={dets.data.total} onPage={setPage} />
        </>)}
      </Card>
      {traffic.data && traffic.data.series.length > 0 && <p className="mt-3 flex items-center gap-2 text-xs text-muted"><DemoBadge text="Charts may include demo data" /> Switch demo data off in Settings to see only real AI results.</p>}
    </>
  );
}
