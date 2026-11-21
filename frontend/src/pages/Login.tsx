import { Cctv, ShieldCheck, Waypoints } from "lucide-react";
import { FormEvent, useState } from "react";
import { Button, Field, Input } from "../components/ui";
import { useAuth } from "../context/AppContext";
import { errMsg } from "../services/api";

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export default function Login() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const validate = () => {
    const e: Record<string, string> = {};
    if (!EMAIL_RE.test(email.trim())) e.email = "Enter a valid email address.";
    if (mode === "register" && username.trim().length < 2) e.username = "Enter your name (at least 2 characters).";
    if (password.length < (mode === "register" ? 8 : 1)) e.password = mode === "register" ? "Use at least 8 characters." : "Enter your password.";
    else if (mode === "register" && !(/[A-Za-z]/.test(password) && /\d/.test(password))) e.password = "Include both letters and digits.";
    setErrors(e);
    return Object.keys(e).length === 0;
  };
  const submit = async (ev: FormEvent) => {
    ev.preventDefault();
    setFormError(null);
    if (!validate()) return;
    setBusy(true);
    try {
      if (mode === "login") await login(email.trim(), password);
      else await register(email.trim(), username.trim(), password);
    } catch (e) { setFormError(errMsg(e)); } finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-[1.1fr_1fr]">
      <section className="relative hidden overflow-hidden p-12 lg:flex lg:flex-col lg:justify-between">
        <div className="flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl bg-raised"><div className="flex flex-col gap-1"><i className="h-2 w-2 rounded-full bg-danger" /><i className="h-2 w-2 rounded-full bg-warn" /><i className="h-2 w-2 rounded-full bg-cyan" /></div></div><span className="font-display text-xl font-semibold">TrafficVision AI</span></div>
        <div className="max-w-xl">
          <h1 className="text-5xl font-semibold leading-[1.08]">See every lane. Count every vehicle. Prove every violation.</h1>
          <p className="mt-5 text-lg text-muted">Upload traffic footage or connect a camera and get YOLO detection, ByteTrack tracking, live counts, congestion levels and evidence-backed alerts in one place.</p>
          <ul className="mt-10 space-y-4 text-sm text-muted">
            <li className="flex gap-3"><Waypoints className="h-5 w-5 shrink-0 text-cyan" />Stable vehicle IDs and duplicate-free line counting</li>
            <li className="flex gap-3"><ShieldCheck className="h-5 w-5 shrink-0 text-cyan" />Violations are only flagged when the zone, signal or calibration is configured</li>
            <li className="flex gap-3"><Cctv className="h-5 w-5 shrink-0 text-cyan" />Works with uploaded videos, webcams and network streams</li>
          </ul>
        </div>
        <p className="text-xs text-muted">Demo mode labels every simulated number so it can never be mistaken for real AI output.</p>
      </section>

      <section className="grid place-items-center p-6">
        <div className="panel w-full max-w-md p-8">
          <h2 className="text-2xl font-semibold">{mode === "login" ? "Sign in" : "Create your account"}</h2>
          <p className="mt-1 text-sm text-muted">{mode === "login" ? "Welcome back to the command center." : "New accounts start as read-only viewers. An admin can upgrade your role."}</p>
          <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
            {mode === "register" && <Field label="Name" error={errors.username}><Input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="name" /></Field>}
            <Field label="Email" error={errors.email}><Input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.com" /></Field>
            <Field label="Password" error={errors.password} hint={mode === "register" ? "At least 8 characters with letters and digits." : undefined}>
              <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"} />
            </Field>
            {formError && <p className="rounded-lg border border-danger/40 bg-danger/10 px-3 py-2 text-sm text-danger" role="alert">{formError}</p>}
            <Button type="submit" variant="primary" className="w-full" loading={busy}>{mode === "login" ? "Sign in" : "Create account"}</Button>
          </form>
          <button className="mt-4 text-sm text-cyan hover:underline" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErrors({}); setFormError(null); }}>
            {mode === "login" ? "No account yet? Create one" : "Already registered? Sign in"}
          </button>
          {mode === "login" && (
            <div className="mt-6 rounded-xl border border-line/70 bg-raised/60 p-4 text-sm">
              <p className="font-medium">Demo accounts</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => { setEmail("admin@trafficvision.demo"); setPassword("Admin@12345"); setErrors({}); }}>Fill admin login</Button>
                <Button size="sm" onClick={() => { setEmail("operator@trafficvision.demo"); setPassword("Operator@12345"); setErrors({}); }}>Fill operator login</Button>
              </div>
              <p className="mt-2 text-xs text-muted">Admin: admin@trafficvision.demo / Admin@12345 - for local demos only.</p>
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
