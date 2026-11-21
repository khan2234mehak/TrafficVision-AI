import { AlertTriangle, ChevronLeft, ChevronRight, Loader2, X } from "lucide-react";
import { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, useEffect, useId, useRef, useState } from "react";
import { cx, LEVEL_COLOR } from "../utils/format";

export function Card({ className, children, ...p }: { className?: string; children: ReactNode } & React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cx("panel p-5", className)} {...p}>{children}</div>;
}

export function CardHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h3 className="text-[15px] font-semibold">{title}</h3>
        {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "danger" | "subtle"; loading?: boolean; size?: "sm" | "md" };
export function Button({ variant = "subtle", loading, size = "md", className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: "bg-brand text-white hover:brightness-110 shadow-[0_8px_24px_-10px_rgb(var(--brand))]",
    subtle: "bg-raised text-ink hover:bg-line/60 border border-line/70",
    ghost: "text-muted hover:text-ink hover:bg-raised",
    danger: "bg-danger/15 text-danger hover:bg-danger/25 border border-danger/40",
  }[variant];
  return (
    <button
      className={cx("inline-flex items-center justify-center gap-2 rounded-xl font-medium transition disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm", v, className)}
      disabled={disabled || loading}
      {...p}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

export function Badge({ children, color = "#64748B", className }: { children: ReactNode; color?: string; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium", className)}
      style={{ background: `${color}22`, color, border: `1px solid ${color}44` }}>
      {children}
    </span>
  );
}
export const DemoBadge = ({ text = "Demo data" }: { text?: string }) => <Badge color="#A78BFA">{text}</Badge>;
export const LevelBadge = ({ level }: { level: string | null | undefined }) => <Badge color={LEVEL_COLOR[level ?? "No data"] ?? "#64748B"}>{level ?? "No data"}</Badge>;

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx("skeleton", className)} aria-hidden />;
}

export function EmptyState({ icon, title, hint, action }: { icon: ReactNode; title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-12 text-center">
      <div className="mb-1 grid h-12 w-12 place-items-center rounded-2xl bg-raised text-brand">{icon}</div>
      <p className="font-display text-base font-semibold">{title}</p>
      {hint && <p className="max-w-sm text-sm text-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-10 text-center" role="alert">
      <AlertTriangle className="h-8 w-8 text-danger" aria-hidden />
      <p className="max-w-md text-sm text-muted">{message}</p>
      {onRetry && <Button size="sm" onClick={onRetry}>Try again</Button>}
    </div>
  );
}

export function Tooltip({ text, children }: { text: string; children: ReactNode }) {
  const id = useId();
  return (
    <span className="group relative inline-flex" aria-describedby={id}>
      {children}
      <span id={id} role="tooltip" className="pointer-events-none absolute -top-2 left-1/2 z-50 w-max max-w-[240px] -translate-x-1/2 -translate-y-full rounded-lg border border-line bg-raised px-2.5 py-1.5 text-xs text-ink opacity-0 shadow-panel transition group-focus-within:opacity-100 group-hover:opacity-100">
        {text}
      </span>
    </span>
  );
}

export function Modal({ open, onClose, title, children, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; wide?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && closeRef.current();
    document.addEventListener("keydown", onKey);
    ref.current?.focus(); // focus once on open (not on every re-render, which would steal focus while typing)
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[1500] grid place-items-center bg-black/60 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title}
        className={cx("panel max-h-[92vh] w-full overflow-auto p-6", wide ? "max-w-3xl" : "max-w-md")}>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button aria-label="Close dialog" onClick={onClose} className="rounded-lg p-1 text-muted hover:bg-raised hover:text-ink"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", danger, onConfirm, onCancel }:
  { open: boolean; title: string; message: string; confirmLabel?: string; danger?: boolean; onConfirm: () => void | Promise<void>; onCancel: () => void }) {
  const [busy, setBusy] = useState(false);
  return (
    <Modal open={open} onClose={onCancel} title={title}>
      <p className="mb-6 text-sm text-muted">{message}</p>
      <div className="flex justify-end gap-2">
        <Button onClick={onCancel}>Cancel</Button>
        <Button variant={danger ? "danger" : "primary"} loading={busy} onClick={async () => { setBusy(true); try { await onConfirm(); } finally { setBusy(false); } }}>{confirmLabel}</Button>
      </div>
    </Modal>
  );
}

export function Field({ label, hint, error, children }: { label: string; hint?: string; error?: string | null; children: ReactNode }) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block font-medium">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-danger" role="alert">{error}</span>}
    </label>
  );
}
const inputCls = "w-full rounded-xl border border-line bg-bg/60 px-3 py-2 text-sm placeholder:text-muted/70 focus:border-brand focus:outline-none";
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cx(inputCls, p.className)} />;
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={cx(inputCls, "pr-8", p.className)} />;

export function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint?: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div><p className="text-sm font-medium">{label}</p>{hint && <p className="text-xs text-muted">{hint}</p>}</div>
      <button role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
        className={cx("relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition", checked ? "bg-brand" : "bg-line")}>
        <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all", checked ? "left-[22px]" : "left-0.5")} />
      </button>
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, label }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[]; label: string }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-xl border border-line bg-bg/50 p-0.5">
      {options.map((o) => (
        <button key={o.value} aria-pressed={value === o.value} onClick={() => onChange(o.value)}
          className={cx("rounded-[10px] px-3 py-1 text-xs font-medium transition", value === o.value ? "bg-brand text-white" : "text-muted hover:text-ink")}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function ProgressBar({ value, color = "rgb(var(--brand))" }: { value: number; color?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-raised" role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full transition-all duration-500" style={{ width: `${Math.min(100, Math.max(0, value))}%`, background: color }} />
    </div>
  );
}

/** The signature element: a four-lamp signal that lights up with congestion. */
export function DensityMeter({ level, ratio, compact }: { level: string | null | undefined; ratio?: number | null; compact?: boolean }) {
  const order = ["Low", "Moderate", "High", "Critical"];
  const lit = order.indexOf(level ?? "") + 1;
  return (
    <div className="flex items-center gap-2" role="img" aria-label={`Traffic density ${level ?? "no data"}`}>
      <div className="flex gap-1">
        {order.map((l, i) => (
          <span key={l} className={cx("rounded-sm transition-all", compact ? "h-3 w-2.5" : "h-5 w-4")}
            style={{ background: i < lit ? LEVEL_COLOR[order[lit - 1]] : "rgb(var(--line))", boxShadow: i === lit - 1 ? `0 0 12px ${LEVEL_COLOR[l]}88` : undefined }} />
        ))}
      </div>
      {!compact && <span className="text-sm font-medium">{level ?? "No data"}{ratio != null && level && level !== "No data" ? <span className="num ml-1 text-muted">{Math.round(ratio * 100)}%</span> : null}</span>}
    </div>
  );
}

export function Pagination({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex items-center justify-between gap-3 pt-4 text-sm text-muted">
      <span className="num">{total === 0 ? "0 results" : `${(page - 1) * pageSize + 1}-${Math.min(total, page * pageSize)} of ${total}`}</span>
      <div className="flex items-center gap-1">
        <Button size="sm" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft className="h-4 w-4" /></Button>
        <span className="num px-2">Page {page} / {pages}</span>
        <Button size="sm" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

export function StatCard({ label, value, hint, icon, accent = "rgb(var(--brand))", children }:
  { label: string; value: ReactNode; hint?: ReactNode; icon: ReactNode; accent?: string; children?: ReactNode }) {
  return (
    <Card className="relative overflow-hidden">
      <div className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} />
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm text-muted">{label}</p>
          <p className="num mt-1 font-display text-3xl font-semibold leading-none">{value}</p>
          {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
          {children}
        </div>
        <div className="grid h-10 w-10 shrink-0 place-items-center rounded-xl" style={{ background: `${accent}22`, color: accent }}>{icon}</div>
      </div>
    </Card>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
