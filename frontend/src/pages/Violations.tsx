import { Download, Image as ImageIcon, Search, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Badge, Button, Card, DemoBadge, EmptyState, ErrorState, Input, Modal, PageHeader, Pagination, Select, Skeleton } from "../components/ui";
import { useToast } from "../context/AppContext";
import { useFetch } from "../hooks";
import { api, download, errMsg, mediaUrl } from "../services/api";
import type { Camera, Page, Violation } from "../types";
import { CATEGORY_COLOR, CATEGORY_LABEL, CLASS_LABEL, fmtDateTime } from "../utils/format";

const SEV_COLOR = { low: "#38BDF8", medium: "#FBBF24", high: "#FB923C", critical: "#F87171" } as const;

export default function Violations() {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [category, setCategory] = useState("");
  const [severity, setSeverity] = useState("");
  const [camera, setCamera] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [open, setOpen] = useState<Violation | null>(null);
  const [exporting, setExporting] = useState(false);
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);

  useEffect(() => { const t = setTimeout(() => { setQ(search); setPage(1); }, 350); return () => clearTimeout(t); }, [search]);
  const filters = { category: category || undefined, severity: severity || undefined, camera_id: camera || undefined, search: q || undefined,
    start: from ? new Date(from).toISOString().slice(0, 19) : undefined, end: to ? new Date(`${to}T23:59:59`).toISOString().slice(0, 19) : undefined };
  const data = useFetch(async () => (await api.get<Page<Violation>>("/api/violations", { params: { ...filters, page, page_size: 12 } })).data, [page, q, category, severity, camera, from, to]);

  const exportCsv = async () => {
    setExporting(true);
    try { await download("/api/reports/csv", { type: "violations", camera_id: camera || undefined, start: filters.start, end: filters.end }, "trafficvision_violations.csv"); toast.push("success", "CSV downloaded"); }
    catch (e) { toast.push("error", errMsg(e)); } finally { setExporting(false); }
  };
  const reset = () => { setSearch(""); setCategory(""); setSeverity(""); setCamera(""); setFrom(""); setTo(""); setPage(1); };
  const rows = data.data?.items ?? [];
  const filtered = !!(q || category || severity || camera || from || to);

  return (
    <>
      <PageHeader title="Violation detection" subtitle="Every record keeps a timestamp, the tracking ID, the category and a screenshot as evidence. Violations are only raised when their zone, signal or calibration is configured."
        actions={<Button loading={exporting} onClick={exportCsv}><Download className="h-4 w-4" />Export CSV</Button>} />
      <Card className="mb-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          <div className="relative lg:col-span-2"><Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-muted" /><Input aria-label="Search violations" className="!pl-9" placeholder="Search by track ID, type or vehicle" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
          <Select aria-label="Violation type" value={category} onChange={(e) => { setCategory(e.target.value); setPage(1); }}><option value="">All types</option>{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
          <Select aria-label="Severity" value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }}><option value="">All severities</option>{["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s}</option>)}</Select>
          <Select aria-label="Camera" value={camera} onChange={(e) => { setCamera(e.target.value); setPage(1); }}><option value="">All cameras</option>{(cams.data ?? []).map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select>
          <Button variant="ghost" onClick={reset} disabled={!filtered}>Clear filters</Button>
          <label className="text-xs text-muted">From<Input type="date" className="mt-1" value={from} max={to || undefined} onChange={(e) => { setFrom(e.target.value); setPage(1); }} /></label>
          <label className="text-xs text-muted">To<Input type="date" className="mt-1" value={to} min={from || undefined} onChange={(e) => { setTo(e.target.value); setPage(1); }} /></label>
        </div>
      </Card>
      <Card className="p-0">
        {data.loading ? <div className="space-y-2 p-5">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)}</div> : data.error ? <ErrorState message={data.error} onRetry={() => data.reload()} /> : rows.length === 0 ? (
          <EmptyState icon={<ShieldCheck className="h-6 w-6" />} title={filtered ? "No violations match these filters" : "No violations recorded"} hint={filtered ? "Try widening the date range or clearing filters." : "Configure restricted zones, a wrong-way lane, speed calibration or a stop line, then analyse a video. Evidence will appear here."} action={filtered && <Button onClick={reset}>Clear filters</Button>} />
        ) : (<div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-line/60 text-xs text-muted"><tr><th className="px-5 py-3 font-medium">Evidence</th><th className="font-medium">Type</th><th className="font-medium">Severity</th><th className="font-medium">Vehicle</th><th className="font-medium">Camera</th><th className="font-medium">When</th><th /></tr></thead>
          <tbody>{rows.map((v) => (
            <tr key={v.id} className="border-b border-line/40 last:border-0 hover:bg-raised/40">
              <td className="px-5 py-3">{v.has_evidence ? <button aria-label={`View evidence for violation ${v.id}`} onClick={() => setOpen(v)} className="block overflow-hidden rounded-lg border border-line"><img loading="lazy" src={mediaUrl(`/api/violations/${v.id}/evidence`)} alt="" className="h-12 w-20 object-cover" /></button> : <span className="grid h-12 w-20 place-items-center rounded-lg bg-raised text-muted"><ImageIcon className="h-4 w-4" /></span>}</td>
              <td><span className="flex items-center gap-2"><i className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLOR[v.category] }} />{CATEGORY_LABEL[v.category] ?? v.category}</span></td>
              <td><Badge color={SEV_COLOR[v.severity]}>{v.severity}</Badge></td>
              <td>{CLASS_LABEL[v.vehicle_class]?.replace(/s$/, "") ?? v.vehicle_class} <span className="num text-muted">#{v.track_id}</span></td>
              <td className="max-w-[180px] truncate">{v.camera_name ?? (v.video_id ? `Video #${v.video_id}` : "-")}</td>
              <td className="whitespace-nowrap">{fmtDateTime(v.timestamp)}{v.is_demo && <span className="ml-2"><DemoBadge text="Demo" /></span>}</td>
              <td className="pr-5 text-right"><Button size="sm" onClick={() => setOpen(v)}>Details</Button></td>
            </tr>))}</tbody></table></div>)}
        {data.data && data.data.total > 0 && <div className="px-5 pb-4"><Pagination page={page} pageSize={12} total={data.data.total} onPage={setPage} /></div>}
      </Card>

      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? `${CATEGORY_LABEL[open.category] ?? open.category} - #${open.track_id}` : ""} wide>
        {open && (<div className="space-y-4">
          {open.has_evidence ? <img src={mediaUrl(`/api/violations/${open.id}/evidence`)} alt="Violation evidence screenshot" className="w-full rounded-xl border border-line" /> : <p className="text-sm text-muted">No screenshot stored.</p>}
          {open.is_demo && <p className="rounded-xl border border-[#A78BFA]/40 bg-[#A78BFA]/10 p-3 text-sm">This is a simulated demo record. It was not produced by the AI pipeline.</p>}
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4"><div><dt className="text-xs text-muted">Severity</dt><dd><Badge color={SEV_COLOR[open.severity]}>{open.severity}</Badge></dd></div><div><dt className="text-xs text-muted">Timestamp</dt><dd>{fmtDateTime(open.timestamp)}</dd></div><div><dt className="text-xs text-muted">Camera / source</dt><dd>{open.camera_name ?? `Video #${open.video_id}`}</dd></div><div><dt className="text-xs text-muted">Frame</dt><dd className="num">{open.frame_index}{open.video_time_s != null ? ` (${open.video_time_s}s)` : ""}</dd></div></dl>
          <div><p className="mb-1 text-xs text-muted">Evidence details</p><pre className="overflow-auto rounded-xl bg-raised/70 p-3 text-xs">{JSON.stringify(open.details, null, 2)}</pre></div>
        </div>)}
      </Modal>
    </>
  );
}
