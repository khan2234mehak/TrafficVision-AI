import L from "leaflet";
import { MapPin } from "lucide-react";
import { useEffect } from "react";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { Link } from "react-router-dom";
import { Badge, Card, DemoBadge, DensityMeter, EmptyState, ErrorState, LevelBadge, PageHeader, Skeleton } from "../components/ui";
import { useFetch, useInterval } from "../hooks";
import { api } from "../services/api";
import type { Camera } from "../types";
import { LEVEL_COLOR } from "../utils/format";

const STATUS_COLOR = { online: "#34D399", offline: "#64748B", error: "#F87171", demo: "#A78BFA" } as const;

function Fit({ pts }: { pts: [number, number][] }) {
  const map = useMap();
  useEffect(() => { if (pts.length) map.fitBounds(L.latLngBounds(pts), { padding: [50, 50], maxZoom: 14 }); }, [pts.length]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function TrafficMap() {
  const cams = useFetch(async () => (await api.get<Camera[]>("/api/cameras")).data, []);
  useInterval(() => cams.reload(true), 20000);
  const placed = (cams.data ?? []).filter((c) => c.latitude != null && c.longitude != null);
  const pts = placed.map((c) => [c.latitude!, c.longitude!] as [number, number]);
  return (
    <>
      <PageHeader title="Traffic map" subtitle="Camera locations coloured by the latest congestion reading. Marker ring shows camera status." />
      {cams.loading ? <Skeleton className="h-[560px]" /> : cams.error ? <Card><ErrorState message={cams.error} onRetry={() => cams.reload()} /></Card> : placed.length === 0 ? (
        <Card><EmptyState icon={<MapPin className="h-6 w-6" />} title="No cameras with coordinates" hint="Add latitude and longitude to a camera in Camera management to see it here." action={<Link to="/cameras" className="text-cyan hover:underline">Open camera management</Link>} /></Card>
      ) : (
        <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
          <Card className="overflow-hidden p-0">
            <MapContainer center={[28.6139, 77.209]} zoom={11} scrollWheelZoom className="h-[560px] w-full" aria-label="Map of camera locations">
              <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Fit pts={pts} />
              {placed.map((c) => (
                <CircleMarker key={c.id} center={[c.latitude!, c.longitude!]} radius={13} pathOptions={{ color: STATUS_COLOR[c.status], weight: 4, fillColor: LEVEL_COLOR[c.density_level ?? "No data"], fillOpacity: 0.9 }}>
                  <Popup><div className="min-w-[210px] space-y-2 text-sm"><p className="font-display text-base font-semibold">{c.name}</p><p className="text-xs opacity-70">{c.location}</p>
                    <div className="flex items-center gap-2"><Badge color={STATUS_COLOR[c.status]}>{c.status === "demo" ? "demo camera" : c.status}</Badge><LevelBadge level={c.density_level} /></div>
                    <p className="text-xs">Occupancy: <b>{c.density_ratio != null ? `${Math.round(c.density_ratio * 100)}%` : "no data"}</b></p>
                    {c.is_demo && <p className="text-xs opacity-70">Simulated reading (demo data)</p>}
                    {c.source_type !== "none" && <Link to="/live" className="text-cyan underline">Open live view</Link>}</div></Popup>
                </CircleMarker>))}
            </MapContainer>
          </Card>
          <Card className="p-0"><div className="border-b border-line/60 px-5 py-3 text-sm font-semibold">Cameras ({cams.data?.length})</div>
            <ul className="max-h-[510px] overflow-auto">{(cams.data ?? []).map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-3 border-b border-line/40 px-5 py-3 last:border-0"><div className="min-w-0"><p className="truncate text-sm font-medium">{c.name}</p><p className="flex items-center gap-2 text-xs text-muted"><i className="h-2 w-2 rounded-full" style={{ background: STATUS_COLOR[c.status] }} />{c.status === "demo" ? "demo" : c.status}{c.is_demo && <DemoBadge text="Demo" />}{c.latitude == null && " - no coordinates"}</p></div><DensityMeter level={c.density_level} compact /></li>))}</ul></Card>
        </div>
      )}
    </>
  );
}
