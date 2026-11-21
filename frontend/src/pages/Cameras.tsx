import { Cctv, MapPin, Pencil, Play, Plus, Settings2, Trash2 } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Badge, Button, Card, ConfirmDialog, DemoBadge, DensityMeter, EmptyState, ErrorState, Field, Input, Modal, PageHeader, Select, Skeleton } from "../components/ui";
import { useAuth, useToast } from "../context/AppContext";
import { useFetch } from "../hooks";
import { api, errMsg } from "../services/api";
import type { Camera, SourceType } from "../types";

const SRC_LABEL: Record<SourceType, string> = { browser: "Browser webcam", webcam: "Server webcam", stream: "Network stream (RTSP/HTTP)", file: "Recorded sample video", none: "No source (map only)" };
const STATUS_COLOR = { online: "#34D399", offline: "#64748B", error: "#F87171", demo: "#A78BFA" } as const;

interface FormState { name: string; location: string; latitude: string; longitude: string; source_type: SourceType; source: string }
const blank: FormState = { name: "", location: "", latitude: "", longitude: "", source_type: "browser", source: "" };

export default function Cameras() {
  const { can } = useAuth();
  const toast = useToast();
  const nav = useNavigate();
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  const samples = useFetch(async () => (await api.get<{ files: string[]; folder: string }>("/api/sample-videos")).data, []);
  const [editing, setEditing] = useState<Camera | "new" | null>(null);
  const [form, setForm] = useState<FormState>(blank);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [del, setDel] = useState<Camera | null>(null);

  useEffect(() => {
    if (editing === "new") setForm(blank);
    else if (editing) setForm({ name: editing.name, location: editing.location, latitude: editing.latitude?.toString() ?? "", longitude: editing.longitude?.toString() ?? "", source_type: editing.source_type, source: editing.source });
    setErrors({});
  }, [editing]);

  const validate = () => {
    const e: Record<string, string> = {};
    if (form.name.trim().length < 2) e.name = "Give the camera a name (2+ characters).";
    const lat = form.latitude === "" ? null : Number(form.latitude), lon = form.longitude === "" ? null : Number(form.longitude);
    if (lat != null && !(lat >= -90 && lat <= 90)) e.latitude = "Latitude must be between -90 and 90.";
    if (lon != null && !(lon >= -180 && lon <= 180)) e.longitude = "Longitude must be between -180 and 180.";
    if ((lat == null) !== (lon == null)) e.latitude = e.latitude ?? "Enter both latitude and longitude, or neither.";
    if (form.source_type === "webcam" && form.source !== "" && !/^\d{1,2}$/.test(form.source)) e.source = "Use a device number such as 0 or 1.";
    if (form.source_type === "stream" && !/^(rtsp|rtsps|http|https):\/\//i.test(form.source)) e.source = "Enter a URL starting with rtsp:// or http(s)://";
    if (form.source_type === "file" && !form.source) e.source = "Choose a video from the sample_data folder.";
    setErrors(e);
    return !Object.keys(e).length;
  };
  const save = async (ev: FormEvent) => {
    ev.preventDefault();
    if (!validate()) return;
    setSaving(true);
    const body = { name: form.name.trim(), location: form.location.trim(), latitude: form.latitude === "" ? null : Number(form.latitude), longitude: form.longitude === "" ? null : Number(form.longitude), source_type: form.source_type, source: form.source };
    try {
      if (editing === "new") await api.post("/api/cameras", body); else if (editing) await api.put(`/api/cameras/${editing.id}`, body);
      toast.push("success", editing === "new" ? "Camera added" : "Camera updated"); setEditing(null); await cams.reload(true);
    } catch (e) { toast.push("error", errMsg(e)); } finally { setSaving(false); }
  };
  const remove = async () => {
    if (!del) return;
    try { await api.delete(`/api/cameras/${del.id}`); toast.push("success", `${del.name} deleted`); setDel(null); await cams.reload(true); } catch (e) { toast.push("error", errMsg(e)); }
  };

  const list = cams.data ?? [];
  return (
    <>
      <PageHeader title="Camera management" subtitle="Register the cameras that feed the platform: browser webcams, server webcams, network streams or recorded sample videos."
        actions={can("admin") && <Button variant="primary" onClick={() => setEditing("new")}><Plus className="h-4 w-4" />Add camera</Button>} />
      {cams.loading ? <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-52" />)}</div> : cams.error ? <Card><ErrorState message={cams.error} onRetry={() => cams.reload()} /></Card> : list.length === 0 ? (
        <Card><EmptyState icon={<Cctv className="h-6 w-6" />} title="No cameras yet" hint="Add your first camera to start live monitoring and see it on the map." action={can("admin") && <Button variant="primary" onClick={() => setEditing("new")}>Add camera</Button>} /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {list.map((c) => (
            <Card key={c.id} className="flex flex-col">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0"><h3 className="truncate font-display text-base font-semibold">{c.name}</h3><p className="mt-1 flex items-center gap-1 text-xs text-muted"><MapPin className="h-3.5 w-3.5 shrink-0" /><span className="truncate">{c.location || "No location"}</span></p></div>
                <Badge color={STATUS_COLOR[c.status]}>{c.status === "demo" ? "Demo camera" : c.status}</Badge>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm"><div><p className="text-xs text-muted">Source</p><p>{SRC_LABEL[c.source_type]}</p>{c.source && <p className="truncate text-xs text-muted">{c.source}</p>}</div>
                <div><p className="text-xs text-muted">Latest density</p><DensityMeter level={c.density_level} ratio={c.density_ratio} compact />{c.density_level ? <p className="mt-1 text-xs">{c.density_level}</p> : <p className="text-xs text-muted">No data</p>}</div></div>
              <p className="mt-3 text-xs text-muted">{c.config?.counting_lines?.length ?? 0} counting lines - {c.config?.zones?.length ?? 0} zones</p>
              {c.last_error && c.status === "error" && <p className="mt-2 rounded-lg bg-danger/10 p-2 text-xs text-danger">{c.last_error}</p>}
              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                {c.source_type !== "none" && <Button size="sm" variant="primary" onClick={() => nav("/live")}><Play className="h-4 w-4" />Open live view</Button>}
                <Link to={`/settings?camera=${c.id}&tab=detection`}><Button size="sm"><Settings2 className="h-4 w-4" />Detection setup</Button></Link>
                {can("admin") && <><Button size="sm" aria-label={`Edit ${c.name}`} onClick={() => setEditing(c)}><Pencil className="h-4 w-4" /></Button><Button size="sm" variant="danger" aria-label={`Delete ${c.name}`} onClick={() => setDel(c)}><Trash2 className="h-4 w-4" /></Button></>}
              </div>
              {c.is_demo && <div className="mt-3"><DemoBadge text="Demo camera: simulated analytics, no video feed" /></div>}
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!editing} onClose={() => setEditing(null)} title={editing === "new" ? "Add camera" : "Edit camera"}>
        <form onSubmit={save} className="space-y-4" noValidate>
          <Field label="Name" error={errors.name}><Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. ITO Junction north" /></Field>
          <Field label="Location"><Input value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} placeholder="Street or junction" /></Field>
          <div className="grid grid-cols-2 gap-3"><Field label="Latitude" error={errors.latitude}><Input inputMode="decimal" value={form.latitude} onChange={(e) => setForm({ ...form, latitude: e.target.value })} placeholder="28.6139" /></Field>
            <Field label="Longitude" error={errors.longitude}><Input inputMode="decimal" value={form.longitude} onChange={(e) => setForm({ ...form, longitude: e.target.value })} placeholder="77.2090" /></Field></div>
          <Field label="Video source"><Select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value as SourceType, source: "" })}>{(Object.keys(SRC_LABEL) as SourceType[]).map((k) => <option key={k} value={k}>{SRC_LABEL[k]}</option>)}</Select></Field>
          {form.source_type === "webcam" && <Field label="Device number" error={errors.source} hint="0 is the first camera connected to the machine running the backend."><Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="0" /></Field>}
          {form.source_type === "stream" && <Field label="Stream URL" error={errors.source}><Input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} placeholder="rtsp://user:pass@192.168.1.10:554/stream" /></Field>}
          {form.source_type === "file" && <Field label="Sample video" error={errors.source} hint={samples.data?.files.length ? "Plays once through the real AI pipeline." : `No videos found. Copy an MP4 into ${samples.data?.folder ?? "the sample_data folder"}.`}><Select value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })}><option value="">Choose a file...</option>{samples.data?.files.map((f) => <option key={f} value={f}>{f}</option>)}</Select></Field>}
          {form.source_type === "browser" && <p className="text-xs text-muted">The browser sends webcam frames to the backend for analysis. Needs camera permission and localhost or HTTPS.</p>}
          <div className="flex justify-end gap-2 pt-2"><Button type="button" onClick={() => setEditing(null)}>Cancel</Button><Button type="submit" variant="primary" loading={saving}>{editing === "new" ? "Add camera" : "Save changes"}</Button></div>
        </form>
      </Modal>
      <ConfirmDialog open={!!del} danger title="Delete this camera?" message={`${del?.name} and its analytics history will be removed. This cannot be undone.`} confirmLabel="Delete camera" onConfirm={remove} onCancel={() => setDel(null)} />
    </>
  );
}
