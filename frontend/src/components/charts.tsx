import { ReactNode } from "react";
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Area, AreaChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DensityPoint, DistPoint, HourPoint, TrafficPoint } from "../types";
import { CATEGORY_COLOR, CATEGORY_LABEL, CLASS_COLOR, CLASS_LABEL, LEVEL_COLOR, fmtDateTime, fmtNum, fmtTime } from "../utils/format";

const axis = { stroke: "rgb(var(--muted))", fontSize: 11, tickLine: false, axisLine: false } as const;
const grid = <CartesianGrid stroke="rgb(var(--line))" strokeOpacity={0.5} vertical={false} />;

function Tip({ active, payload, label, labelFmt }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string; labelFmt?: (l: string) => string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass px-3 py-2 text-xs shadow-panel">
      <p className="mb-1 font-medium">{labelFmt && label ? labelFmt(label) : label}</p>
      {payload.map((p) => (
        <p key={p.name} className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} />{p.name}: <b className="num">{fmtNum(p.value)}</b></p>
      ))}
    </div>
  );
}

export function ChartBox({ children, height = 260, empty }: { children: ReactNode; height?: number; empty?: boolean }) {
  if (empty) return <div className="grid place-items-center text-sm text-muted" style={{ height }}>No data for this period yet.</div>;
  return <div style={{ height }} className="w-full"><ResponsiveContainer width="100%" height="100%">{children as never}</ResponsiveContainer></div>;
}

export function TrafficAreaChart({ data, daily, height }: { data: TrafficPoint[]; daily?: boolean; height?: number }) {
  return (
    <ChartBox empty={!data.length} height={height}>
      <AreaChart data={data} margin={{ left: -4, right: 8, top: 8 }}>
        <defs><linearGradient id="gBrand" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#3B82FF" stopOpacity={0.5} /><stop offset="100%" stopColor="#3B82FF" stopOpacity={0} /></linearGradient></defs>
        {grid}
        <XAxis dataKey="t" {...axis} tickFormatter={(v: string) => fmtTime(v, daily)} minTickGap={28} />
        <YAxis {...axis} width={58} tickFormatter={(v: number) => fmtNum(v)} />
        <Tooltip content={<Tip labelFmt={fmtDateTime} />} />
        <Area type="monotone" dataKey="total" name="Vehicles" stroke="#3B82FF" strokeWidth={2} fill="url(#gBrand)" />
      </AreaChart>
    </ChartBox>
  );
}

export function ClassBarChart({ data, daily, height }: { data: TrafficPoint[]; daily?: boolean; height?: number }) {
  return (
    <ChartBox empty={!data.length} height={height}>
      <BarChart data={data} margin={{ left: -4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey="t" {...axis} tickFormatter={(v: string) => fmtTime(v, daily)} minTickGap={28} />
        <YAxis {...axis} width={58} />
        <Tooltip content={<Tip labelFmt={fmtDateTime} />} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {Object.keys(CLASS_COLOR).map((k) => <Bar key={k} dataKey={k} name={CLASS_LABEL[k]} stackId="a" fill={CLASS_COLOR[k]} />)}
      </BarChart>
    </ChartBox>
  );
}

export function DistributionDonut({ data, kind = "class", height = 240 }: { data: DistPoint[]; kind?: "class" | "violation"; height?: number }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const color = (n: string) => (kind === "class" ? CLASS_COLOR[n] : CATEGORY_COLOR[n]) ?? "#64748B";
  const label = (n: string) => (kind === "class" ? CLASS_LABEL[n] : CATEGORY_LABEL[n]) ?? n;
  return (
    <ChartBox empty={!total} height={height}>
      <PieChart>
        <Pie data={data.map((d) => ({ ...d, name: label(d.name), key: d.name }))} dataKey="value" nameKey="name" innerRadius="58%" outerRadius="86%" paddingAngle={3} stroke="none">
          {data.map((d) => <Cell key={d.name} fill={color(d.name)} />)}
        </Pie>
        <Tooltip content={<Tip />} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
      </PieChart>
    </ChartBox>
  );
}

export function DensityLine({ data, thresholds, daily, height }: { data: DensityPoint[]; thresholds: number[]; daily?: boolean; height?: number }) {
  const pts = data.map((d) => ({ ...d, pct: Math.round(d.avg_ratio * 100), peak: Math.round(d.peak_ratio * 100) }));
  const colors = ["Moderate", "High", "Critical"];
  return (
    <ChartBox empty={!data.length} height={height}>
      <LineChart data={pts} margin={{ left: -4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey="t" {...axis} tickFormatter={(v: string) => fmtTime(v, daily)} minTickGap={28} />
        <YAxis {...axis} width={58} unit="%" domain={[0, (m: number) => Math.max(100, Math.ceil(m / 10) * 10)]} />
        <Tooltip content={<Tip labelFmt={fmtDateTime} />} />
        {thresholds.map((t, i) => (
          <Line key={t} dataKey={() => Math.round(t * 100)} name={`${colors[i]} threshold`} stroke={LEVEL_COLOR[colors[i]]} strokeDasharray="4 4" strokeOpacity={0.55} dot={false} legendType="none" activeDot={false} />
        ))}
        <Line type="monotone" dataKey="pct" name="Average occupancy %" stroke="#22D3EE" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="peak" name="Peak occupancy %" stroke="#F87171" strokeWidth={1.5} dot={false} strokeOpacity={0.8} />
      </LineChart>
    </ChartBox>
  );
}

export function HourlyBars({ data, height }: { data: HourPoint[]; height?: number }) {
  const max = Math.max(...data.map((d) => d.avg_vehicles), 1);
  return (
    <ChartBox empty={!data.some((d) => d.avg_vehicles)} height={height}>
      <BarChart data={data} margin={{ left: -4, right: 8, top: 8 }}>
        {grid}
        <XAxis dataKey="hour" {...axis} tickFormatter={(h: number) => `${h}h`} interval={1} />
        <YAxis {...axis} width={58} />
        <Tooltip content={<Tip labelFmt={(l) => `${String(l).padStart(2, "0")}:00`} />} />
        <Bar dataKey="avg_vehicles" name="Avg vehicles" radius={[4, 4, 0, 0]}>
          {data.map((d) => <Cell key={d.hour} fill={d.avg_vehicles > max * 0.8 ? "#F87171" : d.avg_vehicles > max * 0.55 ? "#FBBF24" : "#3B82FF"} />)}
        </Bar>
      </BarChart>
    </ChartBox>
  );
}
