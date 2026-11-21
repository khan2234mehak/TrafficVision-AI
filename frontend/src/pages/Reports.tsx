import { FileDown, FileSpreadsheet, FileText } from "lucide-react";
import { useMemo, useState } from "react";
import { ClassBarChart, DensityLine, DistributionDonut, TrafficAreaChart } from "../components/charts";
import { Button, Card, CardHeader, DemoBadge, Field, Input, PageHeader, Segmented, Select, Skeleton, StatCard } from "../components/ui";
import { useToast } from "../context/AppContext";
import { useFetch } from "../hooks";
import { api, download, errMsg, tzOffset } from "../services/api";
import type { Camera, DensityPoint, DistPoint, HourPoint, TrafficPoint } from "../types";
import { fmtNum } from "../utils/format";

interface Summary { total_vehicles: number; series: TrafficPoint[]; distribution: DistPoint[]; density: DensityPoint[]; peaks: HourPoint[]; violations: number; interval: string; has_demo: boolean }
const iso = (d: Date) => d.toISOString().slice(0, 10);
type Period = "daily" | "weekly" | "monthly";
const DAYS: Record<Period, number> = { daily: 1, weekly: 7, monthly: 30 };

export default function Reports() {
  const toast = useToast();
  const today = useMemo(() => new Date(), []);
  const [period, setPeriod] = useState<Period>("weekly");
  const [from, setFrom] = useState(iso(new Date(today.getTime() - 7 * 864e5)));
  const [to, setTo] = useState(iso(today));
  const [cam, setCam] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const start = `${from}T00:00:00`, end = `${to}T23:59:59`;
  const invalid = from > to;
  const sum = useFetch(async () => invalid ? null : (await api.get<Summary>("/api/reports/summary", { params: { start, end, camera_id: cam || undefined, tz: tzOffset() } })).data, [from, to, cam]);

  const preset = (p: Period) => { setPeriod(p); setTo(iso(today)); setFrom(iso(new Date(today.getTime() - DAYS[p] * 864e5))); };
  const run = async (key: string, path: string, params: Record<string, string | number | undefined>, name: string) => {
    setBusy(key);
    try { await download(path, params, name); toast.push("success", `${name} downloaded`); } catch (e) { toast.push("error", errMsg(e, "Could not generate the report.")); } finally { setBusy(null); }
  };
  const s = sum.data;
  return (
    <>
      <PageHeader title="Reports" subtitle="Pick a period, review the numbers, then export CSV data or a PDF summary." />
      <Card className="mb-4">
        <div className="flex flex-wrap items-end gap-4">
          <Segmented label="Report period" value={period} onChange={preset} options={[{ value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }, { value: "monthly", label: "Monthly" }]} />
          <Field label="From"><Input type="date" value={from} max={to} onChange={(e) => setFrom(e.target.value)} /></Field>
          <Field label="To" error={invalid ? "The end date must be after the start date." : null}><Input type="date" value={to} min={from} max={iso(today)} onChange={(e) => setTo(e.target.value)} /></Field>
          <Field label="Camera"><Select value={cam} onChange={(e) => setCam(e.target.value)}><option value="">All cameras</option>{(cams.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
        </div>
        <div className="mt-5 flex flex-wrap gap-2 border-t border-line/60 pt-4">
          <Button variant="primary" disabled={invalid} loading={busy === "pdf"} onClick={() => run("pdf", "/api/reports/pdf", { period, camera_id: cam || undefined, end: `${to}T23:59:59`, tz: tzOffset() }, `trafficvision_${period}_report.pdf`)}><FileText className="h-4 w-4" />PDF report ({period})</Button>
          <Button disabled={invalid} loading={busy === "t"} onClick={() => run("t", "/api/reports/csv", { type: "traffic", start, end, camera_id: cam || undefined }, "trafficvision_traffic.csv")}><FileSpreadsheet className="h-4 w-4" />Traffic CSV</Button>
          <Button disabled={invalid} loading={busy === "v"} onClick={() => run("v", "/api/reports/csv", { type: "violations", start, end, camera_id: cam || undefined }, "trafficvision_violations.csv")}><FileDown className="h-4 w-4" />Violations CSV</Button>
        </div>
      </Card>
      {sum.loading ? <Skeleton className="h-64" /> : s && (<>
        <div className="grid gap-4 sm:grid-cols-3">
          <StatCard label="Vehicles counted" value={fmtNum(s.total_vehicles)} icon={<FileText className="h-5 w-5" />} />
          <StatCard label="Violations" value={fmtNum(s.violations)} icon={<FileText className="h-5 w-5" />} accent="rgb(var(--danger))" />
          <StatCard label="Peak hours" value={<span className="text-2xl">{s.peaks.map((p) => p.label).join(", ") || "-"}</span>} icon={<FileText className="h-5 w-5" />} accent="rgb(var(--orange))" />
        </div>
        {s.has_demo && <p className="mt-3 flex items-center gap-2 text-xs text-muted"><DemoBadge /> This period includes simulated demo data. Exports label it as "DEMO (simulated)".</p>}
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          <Card className="xl:col-span-2"><CardHeader title="Traffic volume" />{<TrafficAreaChart data={s.series} daily={s.interval === "1d"} />}</Card>
          <Card><CardHeader title="Vehicle categories" /><DistributionDonut data={s.distribution} /></Card>
          <Card className="xl:col-span-2"><CardHeader title="Congestion" /><DensityLine data={s.density} thresholds={[0.25, 0.5, 0.75]} daily={s.interval === "1d"} /></Card>
          <Card><CardHeader title="Mix by interval" /><ClassBarChart data={s.series.slice(-14)} daily={s.interval === "1d"} /></Card>
        </div>
      </>)}
    </>
  );
}
