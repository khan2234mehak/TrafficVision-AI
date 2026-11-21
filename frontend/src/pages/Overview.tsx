import { Activity, Camera, Gauge, ShieldAlert, Truck, Cpu } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { ClassBarChart, DensityLine, DistributionDonut, HourlyBars, TrafficAreaChart } from "../components/charts";
import { Card, CardHeader, DemoBadge, DensityMeter, ErrorState, PageHeader, Segmented, Skeleton, StatCard } from "../components/ui";
import { useChannel, useFetch, useInterval } from "../hooks";
import { api, tzOffset } from "../services/api";
import type { AppSettings, DashboardStats, DensityPoint, DistPoint, HourPoint, LiveStats, SystemHealth, TrafficPoint } from "../types";
import { fmtNum, timeAgo } from "../utils/format";

type Range = "24h" | "7d" | "30d";

export default function Overview() {
  const [range, setRange] = useState<Range>("24h");
  const [live, setLive] = useState<{ name: string; stats: LiveStats; at: number } | null>(null);
  const tz = tzOffset();
  const stats = useFetch(async () => (await api.get<DashboardStats>("/api/dashboard/stats", { params: { range } })).data, [range]);
  const trend = useFetch(async () => (await api.get<TrafficPoint[]>("/api/dashboard/traffic-trends", { params: { range, tz } })).data, [range]);
  const dist = useFetch(async () => (await api.get<DistPoint[]>("/api/dashboard/vehicle-distribution", { params: { range } })).data, [range]);
  const vdist = useFetch(async () => (await api.get<DistPoint[]>("/api/dashboard/violation-distribution", { params: { range } })).data, [range]);
  const hourly = useFetch(async () => (await api.get<HourPoint[]>("/api/dashboard/hourly-flow", { params: { range: range === "24h" ? "24h" : range, tz } })).data, [range]);
  const dens = useFetch(async () => (await api.get<{ series: DensityPoint[]; thresholds: number[] }>("/api/analytics/density", { params: { range, tz } })).data, [range]);
  const health = useFetch(async () => (await api.get<SystemHealth>("/api/system/health")).data, []);
  const settings = useFetch(async () => (await api.get<AppSettings>("/api/settings")).data, []);

  const reloadAll = () => { stats.reload(true); trend.reload(true); dist.reload(true); vdist.reload(true); hourly.reload(true); dens.reload(true); };
  useInterval(reloadAll, 30000);
  useChannel("/ws/traffic", (m) => {
    if (m.type === "live_stats") setLive({ name: m.camera_name, stats: m.stats, at: Date.now() });
    if (m.type === "video_status" && m.status === "completed") reloadAll();
  });

  const s = stats.data;
  const daily = range !== "24h";
  const liveFresh = live && Date.now() - live.at < 15000;

  return (
    <>
      <PageHeader title="Traffic overview" subtitle="Network-wide counts, congestion and violations at a glance."
        actions={<Segmented label="Time range" value={range} onChange={setRange} options={[{ value: "24h", label: "24 hours" }, { value: "7d", label: "7 days" }, { value: "30d", label: "30 days" }]} />} />

      {s && (s.demo_rows || s.real_rows) && (
        <div className="mb-5 flex flex-wrap items-center gap-2 rounded-xl border border-line/70 bg-raised/50 px-4 py-2.5 text-sm text-muted">
          {s.demo_rows && <DemoBadge />}
          <span>{s.demo_rows && s.real_rows ? "These charts mix simulated demo data with real AI results from your uploads and cameras." : s.demo_rows ? "Everything below is simulated demo data. Upload a video or start a camera to see real AI results." : "Showing results produced by the AI pipeline."}</span>
          {s.demo_rows && <Link to="/settings" className="text-cyan hover:underline">Change in Settings</Link>}
        </div>
      )}

      {liveFresh && live && (
        <Card className="mb-5 border-ok/40">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3"><span className="relative flex h-2.5 w-2.5"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-ok opacity-60" /><span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-ok" /></span>
              <p className="text-sm font-medium">Live from {live.name}</p></div>
            <div className="num flex flex-wrap gap-5 text-sm"><span>{live.stats.vehicles_in_frame} in frame</span><span>{live.stats.total_count} counted</span><span>{live.stats.vehicles_per_minute}/min</span><DensityMeter level={live.stats.density.level} ratio={live.stats.density.ratio} /></div>
          </div>
        </Card>
      )}

      {stats.error ? <Card><ErrorState message={stats.error} onRetry={() => stats.reload()} /></Card> : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {stats.loading || !s ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[118px]" />) : (<>
            <StatCard label="Vehicles detected" value={fmtNum(s.total_vehicles)} hint={`Counted in the last ${range === "24h" ? "24 hours" : range === "7d" ? "7 days" : "30 days"}`} icon={<Truck className="h-5 w-5" />} />
            <StatCard label="Active cameras" value={<>{s.active_cameras}<span className="text-lg text-muted"> / {s.total_cameras}</span></>} hint={s.active_cameras ? "Analysing live right now" : "None streaming - start one in Live Monitoring"} icon={<Camera className="h-5 w-5" />} accent="rgb(var(--cyan))" />
            <StatCard label="Current traffic density" value={<span className="text-2xl">{s.density.level}</span>} hint={s.last_update ? `Latest reading ${timeAgo(s.last_update)}` : "No readings yet"} icon={<Gauge className="h-5 w-5" />} accent="rgb(var(--orange))">
              <div className="mt-3"><DensityMeter level={s.density.level} compact /></div>
            </StatCard>
            <StatCard label="Violations" value={fmtNum(s.total_violations)} hint={<Link to="/violations" className="text-cyan hover:underline">Review evidence</Link>} icon={<ShieldAlert className="h-5 w-5" />} accent="rgb(var(--danger))" />
            <StatCard label="Vehicles per minute" value={s.vehicles_per_minute} hint="Across cameras, latest 15 minutes" icon={<Activity className="h-5 w-5" />} accent="rgb(var(--ok))" />
            <StatCard label="System status" value={<span className="text-2xl">{health.data ? (health.data.status === "ok" ? "Healthy" : "Degraded") : "..."}</span>} icon={<Cpu className="h-5 w-5" />} accent="rgb(var(--ok))"
              hint={health.data ? (health.data.model.available ? `YOLO ready on ${health.data.model.device}` : "YOLO weights missing - run the setup script") : "Checking..."} />
          </>)}
        </div>
      )}

      <div className="mt-6 grid gap-4 xl:grid-cols-3">
        <Card className="xl:col-span-2"><CardHeader title="Vehicle count over time" subtitle="Vehicles counted per interval" />{trend.loading ? <Skeleton className="h-[260px]" /> : <TrafficAreaChart data={trend.data ?? []} daily={daily} />}</Card>
        <Card><CardHeader title="Vehicle categories" subtitle="Share of all counted vehicles" />{dist.loading ? <Skeleton className="h-[240px]" /> : <DistributionDonut data={dist.data ?? []} />}</Card>
        <Card className="xl:col-span-2"><CardHeader title="Traffic density trend" subtitle="Average and peak occupancy, with congestion thresholds" />{dens.loading ? <Skeleton className="h-[260px]" /> : <DensityLine data={dens.data?.series ?? []} thresholds={dens.data?.thresholds ?? settings.data?.density_thresholds ?? [0.25, 0.5, 0.75]} daily={daily} />}</Card>
        <Card><CardHeader title="Violation categories" subtitle="Recorded in this period" />{vdist.loading ? <Skeleton className="h-[240px]" /> : <DistributionDonut data={vdist.data ?? []} kind="violation" />}</Card>
        <Card className="xl:col-span-2"><CardHeader title="Hourly traffic flow" subtitle="Average vehicles by hour of day (your local time)" />{hourly.loading ? <Skeleton className="h-[260px]" /> : <HourlyBars data={hourly.data ?? []} />}</Card>
        <Card><CardHeader title="Mix by interval" subtitle="Stacked by vehicle type" />{trend.loading ? <Skeleton className="h-[260px]" /> : <ClassBarChart data={(trend.data ?? []).slice(-14)} daily={daily} />}</Card>
      </div>
    </>
  );
}
