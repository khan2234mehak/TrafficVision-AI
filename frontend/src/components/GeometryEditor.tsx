import { Crosshair, Eraser, Minus, Pentagon, Ruler, Trash2, TrafficCone } from "lucide-react";
import { MouseEvent, useRef, useState } from "react";
import type { CameraConfig, Point, Zone } from "../types";
import { cx } from "../utils/format";
import { Button, Input, Select } from "./ui";

type Tool = "none" | "line" | "zone" | "stop" | "calibrate";
const DIRS: Record<string, Point> = { Down: [0, 1], Up: [0, -1], Left: [-1, 0], Right: [1, 0] };
const ZCOLOR = { density: "#22D3EE", restricted: "#F87171", wrong_way: "#FB923C" } as const;
const uid = (p: string) => `${p}-${Math.random().toString(36).slice(2, 7)}`;
const pts = (p: Point[]) => p.map(([x, y]) => `${x},${y}`).join(" ");

/** Click-to-draw editor for counting lines, zones, the stop line and the speed calibration scale. Coordinates are 0..1. */
export function GeometryEditor({ config, onChange, background }: { config: CameraConfig; onChange: (c: CameraConfig) => void; background?: string | null }) {
  const box = useRef<HTMLDivElement>(null);
  const [tool, setTool] = useState<Tool>("none");
  const [draft, setDraft] = useState<Point[]>([]);
  const [zoneType, setZoneType] = useState<Zone["type"]>("restricted");
  const [dirName, setDirName] = useState("Down");
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [realMeters, setRealMeters] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  const reset = () => { setTool("none"); setDraft([]); setMsg(null); };
  const click = (e: MouseEvent) => {
    if (tool === "none" || !box.current) return;
    const r = box.current.getBoundingClientRect();
    const p: Point = [Math.min(1, Math.max(0, +((e.clientX - r.left) / r.width).toFixed(4))), Math.min(1, Math.max(0, +((e.clientY - r.top) / r.height).toFixed(4)))];
    const next = [...draft, p];
    if (tool === "line" && next.length === 2) {
      onChange({ ...config, counting_lines: [...config.counting_lines, { id: uid("line"), name: `Line ${config.counting_lines.length + 1}`, p1: next[0], p2: next[1] }] });
      reset();
    } else if (tool === "stop" && next.length === 2) {
      onChange({ ...config, signal: { ...config.signal, stop_line: [next[0], next[1]] } });
      reset();
    } else if (tool === "calibrate" && next.length === 2) {
      setDraft(next);
      setMsg("Enter the real-world length of this segment in metres, then press Apply scale.");
    } else if (tool !== "line" && tool !== "stop" && tool !== "calibrate") setDraft(next);
    else setDraft(next);
  };
  const finishZone = () => {
    if (draft.length < 3) return;
    const z: Zone = { id: uid("zone"), name: `${zoneType === "density" ? "Density" : zoneType === "restricted" ? "Restricted" : "Lane"} zone ${config.zones.length + 1}`,
      type: zoneType, polygon: draft, capacity: 15, min_dwell_s: 1, direction: zoneType === "wrong_way" ? DIRS[dirName] : null };
    onChange({ ...config, zones: [...config.zones, z] });
    reset();
  };
  const applyScale = () => {
    const m = parseFloat(realMeters);
    if (!natural || draft.length !== 2 || !(m > 0)) { setMsg("Draw two points and enter a positive length."); return; }
    const px = Math.hypot((draft[1][0] - draft[0][0]) * natural.w, (draft[1][1] - draft[0][1]) * natural.h);
    if (px < 5) { setMsg("The two points are too close together."); return; }
    onChange({ ...config, calibration: { ...config.calibration, meters_per_pixel: +(m / px).toPrecision(4) } });
    setMsg(`Scale set: ${(m / px).toPrecision(3)} m per pixel.`);
    setDraft([]); setTool("none");
  };
  const upd = (patch: Partial<CameraConfig>) => onChange({ ...config, ...patch });
  const toolBtn = (t: Tool, icon: React.ReactNode, label: string, disabled = false) => (
    <Button size="sm" variant={tool === t ? "primary" : "subtle"} disabled={disabled} aria-pressed={tool === t} onClick={() => { setDraft([]); setMsg(null); setTool(tool === t ? "none" : t); }}>{icon}{label}</Button>
  );
  const hint = { none: "Pick a tool, then click on the frame.", line: "Click two points to place the counting line. Vehicles crossing top-to-bottom (left-to-right line) count as 'in'.",
    zone: "Click the corners of the zone, then press Finish zone.", stop: "Click two points to place the stop line.", calibrate: "Click both ends of something you know the length of (e.g. a lane marking)." }[tool];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        {toolBtn("line", <Minus className="h-4 w-4" />, "Counting line")}
        {toolBtn("zone", <Pentagon className="h-4 w-4" />, "Zone")}
        {toolBtn("stop", <TrafficCone className="h-4 w-4" />, "Stop line")}
        {toolBtn("calibrate", <Ruler className="h-4 w-4" />, "Speed scale", !natural)}
        {tool === "zone" && (
          <>
            <Select aria-label="Zone type" className="!w-auto" value={zoneType} onChange={(e) => setZoneType(e.target.value as Zone["type"])}>
              <option value="restricted">Restricted zone</option><option value="wrong_way">Wrong-way lane</option><option value="density">Density zone</option>
            </Select>
            {zoneType === "wrong_way" && (
              <Select aria-label="Allowed direction" className="!w-auto" value={dirName} onChange={(e) => setDirName(e.target.value)}>
                {Object.keys(DIRS).map((d) => <option key={d} value={d}>Allowed: {d}</option>)}
              </Select>
            )}
            <Button size="sm" variant="primary" disabled={draft.length < 3} onClick={finishZone}>Finish zone</Button>
          </>
        )}
        {draft.length > 0 && <Button size="sm" variant="ghost" onClick={reset}><Eraser className="h-4 w-4" />Cancel drawing</Button>}
      </div>
      <p className="text-xs text-muted">{hint}{!natural && " (Speed scale needs a background frame.)"}</p>

      <div ref={box} onClick={click} className={cx("relative aspect-video w-full overflow-hidden rounded-xl border border-line bg-bg", tool !== "none" && "cursor-crosshair")}>
        {background && <img src={background} alt="Camera frame used as drawing background" className="absolute inset-0 h-full w-full object-fill opacity-90"
          onLoad={(e) => setNatural({ w: e.currentTarget.naturalWidth, h: e.currentTarget.naturalHeight })} onError={() => setNatural(null)} />}
        {!background && <div className="absolute inset-0 grid place-items-center text-xs text-muted">No background frame - drawing on a blank 16:9 canvas</div>}
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" className="absolute inset-0 h-full w-full">
          {config.zones.map((z) => (
            <g key={z.id}><polygon points={pts(z.polygon)} fill={ZCOLOR[z.type]} fillOpacity={0.18} stroke={ZCOLOR[z.type]} strokeWidth={0.004} vectorEffect="non-scaling-stroke" />
              {z.type === "wrong_way" && z.direction && (() => { const cx0 = z.polygon.reduce((s, p) => s + p[0], 0) / z.polygon.length, cy0 = z.polygon.reduce((s, p) => s + p[1], 0) / z.polygon.length;
                return <line x1={cx0} y1={cy0} x2={cx0 + z.direction[0] * 0.08} y2={cy0 + z.direction[1] * 0.12} stroke="#FB923C" strokeWidth={3} vectorEffect="non-scaling-stroke" markerEnd="url(#arrow)" />; })()}
            </g>))}
          {config.counting_lines.map((l) => <line key={l.id} x1={l.p1[0]} y1={l.p1[1]} x2={l.p2[0]} y2={l.p2[1]} stroke="#FACC15" strokeWidth={3} vectorEffect="non-scaling-stroke" />)}
          {config.signal.stop_line && <line x1={config.signal.stop_line[0][0]} y1={config.signal.stop_line[0][1]} x2={config.signal.stop_line[1][0]} y2={config.signal.stop_line[1][1]} stroke="#F87171" strokeWidth={4} strokeDasharray="0.02 0.01" vectorEffect="non-scaling-stroke" />}
          {draft.length > 1 && <polyline points={pts(draft)} fill="none" stroke="#FFFFFF" strokeWidth={2} strokeDasharray="6 4" vectorEffect="non-scaling-stroke" />}
          <defs><marker id="arrow" markerWidth="6" markerHeight="6" refX="3" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 z" fill="#FB923C" /></marker></defs>
        </svg>
        {draft.map(([x, y], i) => <span key={i} className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white bg-brand" style={{ left: `${x * 100}%`, top: `${y * 100}%` }} />)}
      </div>

      {tool === "calibrate" && draft.length === 2 && (
        <div className="flex flex-wrap items-end gap-2">
          <label className="text-sm">Real length (m)<Input className="mt-1 !w-36" inputMode="decimal" value={realMeters} onChange={(e) => setRealMeters(e.target.value)} placeholder="e.g. 3.5" /></label>
          <Button variant="primary" onClick={applyScale}><Crosshair className="h-4 w-4" />Apply scale</Button>
        </div>
      )}
      {msg && <p className="text-xs text-cyan" role="status">{msg}</p>}

      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-2">
          <p className="text-sm font-medium">Counting lines ({config.counting_lines.length})</p>
          {config.counting_lines.length === 0 && <p className="text-xs text-muted">No lines. Vehicles will be counted once each when first tracked.</p>}
          {config.counting_lines.map((l) => (
            <div key={l.id} className="flex items-center gap-2">
              <Input aria-label="Line name" value={l.name} onChange={(e) => upd({ counting_lines: config.counting_lines.map((x) => (x.id === l.id ? { ...x, name: e.target.value } : x)) })} />
              <Button size="sm" variant="danger" aria-label={`Delete ${l.name}`} onClick={() => upd({ counting_lines: config.counting_lines.filter((x) => x.id !== l.id) })}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </div>
        <div className="space-y-2">
          <p className="text-sm font-medium">Zones ({config.zones.length})</p>
          {config.zones.length === 0 && <p className="text-xs text-muted">No zones. Density uses the whole frame; zone-based violations stay off.</p>}
          {config.zones.map((z) => (
            <div key={z.id} className="flex items-center gap-2">
              <span className="h-3 w-3 shrink-0 rounded-sm" style={{ background: ZCOLOR[z.type] }} />
              <Input aria-label="Zone name" value={z.name} onChange={(e) => upd({ zones: config.zones.map((x) => (x.id === z.id ? { ...x, name: e.target.value } : x)) })} />
              {z.type === "density" && <Input aria-label="Zone capacity" type="number" min={1} className="!w-20" title="Vehicles that mean 'full'" value={z.capacity} onChange={(e) => upd({ zones: config.zones.map((x) => (x.id === z.id ? { ...x, capacity: Math.max(1, +e.target.value || 1) } : x)) })} />}
              <Button size="sm" variant="danger" aria-label={`Delete ${z.name}`} onClick={() => upd({ zones: config.zones.filter((x) => x.id !== z.id) })}><Trash2 className="h-4 w-4" /></Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
