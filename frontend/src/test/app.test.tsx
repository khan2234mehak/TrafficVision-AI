import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
const post = vi.fn();
const put = vi.fn();
vi.mock("../services/api", async (orig) => {
  const real = await orig<typeof import("../services/api")>();
  return { ...real, api: { get: (...a: unknown[]) => get(...a), post: (...a: unknown[]) => post(...a), put: (...a: unknown[]) => put(...a), delete: vi.fn() } };
});

import { AuthProvider, ThemeProvider, ToastProvider } from "../context/AppContext";
import { GeometryEditor } from "../components/GeometryEditor";
import { ConfirmDialog, DensityMeter, Pagination } from "../components/ui";
import AppLayout, { NAV } from "../layouts/AppLayout";
import Cameras from "../pages/Cameras";
import Login from "../pages/Login";
import Overview from "../pages/Overview";
import Violations from "../pages/Violations";
import type { CameraConfig } from "../types";
import * as authCtx from "../context/AppContext";

const wrap = (ui: React.ReactNode, path = "/") => render(
  <ThemeProvider><ToastProvider><AuthProvider><MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter></AuthProvider></ToastProvider></ThemeProvider>);

const emptyCfg: CameraConfig = { counting_lines: [], zones: [], signal: { enabled: false, mode: "manual", manual_state: "red", red_seconds: 30, green_seconds: 30, cycle_offset_s: 0, stop_line: null, violation_direction: "in" }, calibration: { enabled: false, meters_per_pixel: null, speed_limit_kmh: 60 } };

beforeEach(() => { get.mockReset(); post.mockReset(); put.mockReset(); localStorage.clear(); });

describe("Login", () => {
  it("validates the form before calling the API", async () => {
    wrap(<Login />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("Enter a valid email address.")).toBeInTheDocument();
    expect(screen.getByText("Enter your password.")).toBeInTheDocument();
    expect(post).not.toHaveBeenCalled();
  });
  it("signs in with valid credentials and shows backend errors", async () => {
    post.mockRejectedValueOnce({ response: { status: 401, data: { detail: "Incorrect email or password." } } });
    wrap(<Login />);
    await userEvent.type(screen.getByLabelText(/^Email/), "a@b.co");
    await userEvent.type(screen.getByLabelText(/^Password/), "whatever1");
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Incorrect email or password.");
    expect(post).toHaveBeenCalledWith("/api/auth/login", { email: "a@b.co", password: "whatever1" });
  });
  it("switches to registration with password rules and fills demo credentials", async () => {
    wrap(<Login />);
    await userEvent.click(screen.getByRole("button", { name: "Fill admin login" }));
    expect(screen.getByLabelText(/^Email/)).toHaveValue("admin@trafficvision.demo");
    await userEvent.click(screen.getByRole("button", { name: /Create one/ }));
    await userEvent.type(screen.getByLabelText(/^Name/), "Mehak");
    await userEvent.clear(screen.getByLabelText(/^Password/));
    await userEvent.type(screen.getByLabelText(/^Password/), "onlyletters");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Include both letters and digits.")).toBeInTheDocument();
  });
});

describe("Navigation", () => {
  it("renders every sidebar entry and navigates", async () => {
    vi.spyOn(authCtx, "useAuth").mockReturnValue({ user: { id: 1, email: "a@b.co", username: "Admin", role: "admin", is_active: true, created_at: "" }, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn(), can: () => true });
    get.mockResolvedValue({ data: { unread: 0, items: [] } });
    wrap(<Routes><Route element={<AppLayout />}>{NAV.map((n) => <Route key={n.to} path={n.to === "/" ? undefined : n.to.slice(1)} index={n.to === "/"} element={<h1>page:{n.label}</h1>} />)}</Route></Routes>);
    const nav = screen.getAllByRole("navigation", { name: "Main" })[0];
    expect(within(nav).getAllByRole("link")).toHaveLength(9);
    for (const label of ["Live Monitoring", "Video Analysis", "Camera Management", "Traffic Analytics", "Violation Detection", "Traffic Map", "Reports", "Settings", "Overview"]) {
      await userEvent.click(within(nav).getByRole("link", { name: label }));
      expect(await screen.findByText(`page:${label}`)).toBeInTheDocument();
    }
    vi.restoreAllMocks();
  });
});

describe("Overview", () => {
  it("renders stats from the API and labels demo data", async () => {
    get.mockImplementation((url: string) => {
      const map: Record<string, unknown> = {
        "/api/dashboard/stats": { range: "24h", total_vehicles: 12345, total_cameras: 5, active_cameras: 0, density: { ratio: 0.6, level: "High" }, total_violations: 7, vehicles_per_minute: 42.5, has_data: true, demo_mode: true, demo_rows: true, real_rows: false, last_update: new Date().toISOString() },
        "/api/system/health": { status: "ok", model: { available: true, device: "cpu", weights: "yolo11n.pt", path: "" }, database: { ok: true, engine: "SQLite" } },
        "/api/settings": { density_thresholds: [0.25, 0.5, 0.75] },
      };
      return Promise.resolve({ data: map[url] ?? (url.includes("density") ? { series: [], thresholds: [0.25, 0.5, 0.75] } : []) });
    });
    wrap(<Overview />);
    expect(await screen.findByText("12,345")).toBeInTheDocument();
    expect(screen.getByText("42.5")).toBeInTheDocument();
    expect(screen.getAllByText("High").length).toBeGreaterThan(0);
    expect(screen.getByText(/simulated demo data/i)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "7 days" }));
    await waitFor(() => expect(get).toHaveBeenCalledWith("/api/dashboard/stats", { params: { range: "7d" } }));
  });
});

describe("Cameras", () => {
  it("validates the add-camera form and posts valid data", async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url === "/api/cameras" ? [] : { files: ["clip.mp4"], folder: "sample_data" } }));
    post.mockResolvedValue({ data: {} });
    vi.spyOn(authCtx, "useAuth").mockReturnValue({ user: { id: 1, email: "a", username: "a", role: "admin", is_active: true, created_at: "" }, loading: false, login: vi.fn(), register: vi.fn(), logout: vi.fn(), can: () => true });
    wrap(<Cameras />);
    expect(await screen.findByText("No cameras yet")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Add camera" })[0]);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add camera" }));
    expect(await within(dialog).findByText(/Give the camera a name/)).toBeInTheDocument();
    await userEvent.type(within(dialog).getByLabelText(/^Name/), "Gate 4");
    await userEvent.type(within(dialog).getByLabelText(/^Latitude/), "999");
    await userEvent.type(within(dialog).getByLabelText(/^Longitude/), "77");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add camera" }));
    expect(await within(dialog).findByText("Latitude must be between -90 and 90.")).toBeInTheDocument();
    await userEvent.clear(within(dialog).getByLabelText(/^Latitude/));
    await userEvent.type(within(dialog).getByLabelText(/^Latitude/), "28.6");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add camera" }));
    await waitFor(() => expect(post).toHaveBeenCalledWith("/api/cameras", expect.objectContaining({ name: "Gate 4", latitude: 28.6, longitude: 77, source_type: "browser" })));
    vi.restoreAllMocks();
  });
});

describe("Violations", () => {
  it("shows an empty state and sends filters to the API", async () => {
    get.mockImplementation((url: string) => Promise.resolve({ data: url === "/api/violations" ? { items: [], total: 0, page: 1, page_size: 12 } : [] }));
    wrap(<Violations />);
    expect(await screen.findByText("No violations recorded")).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Violation type"), "overspeed");
    await waitFor(() => expect(get).toHaveBeenCalledWith("/api/violations", { params: expect.objectContaining({ category: "overspeed", page: 1 }) }));
    expect(await screen.findByText("No violations match these filters")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: "Clear filters" })[0]);
    expect(await screen.findByText("No violations recorded")).toBeInTheDocument();
  });
});

describe("Components", () => {
  it("DensityMeter exposes its level and Pagination buttons work", async () => {
    const onPage = vi.fn();
    render(<><DensityMeter level="Critical" ratio={0.9} /><Pagination page={2} pageSize={10} total={35} onPage={onPage} /></>);
    expect(screen.getByRole("img", { name: "Traffic density Critical" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    await userEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onPage).toHaveBeenNthCalledWith(1, 3);
    expect(onPage).toHaveBeenNthCalledWith(2, 1);
  });
  it("ConfirmDialog confirms and cancels", async () => {
    const ok = vi.fn(), no = vi.fn();
    render(<ConfirmDialog open title="Delete?" message="Sure?" confirmLabel="Yes, delete" danger onConfirm={ok} onCancel={no} />);
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await userEvent.click(screen.getByRole("button", { name: "Yes, delete" }));
    expect(no).toHaveBeenCalled();
    await waitFor(() => expect(ok).toHaveBeenCalled());
  });
  it("GeometryEditor draws a counting line with two clicks and can delete it", async () => {
    const onChange = vi.fn();
    const { container } = render(<GeometryEditor config={emptyCfg} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Counting line/ }));
    const box = container.querySelector(".aspect-video") as HTMLElement;
    box.getBoundingClientRect = () => ({ left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100, x: 0, y: 0, toJSON: () => ({}) });
    fireEvent.click(box, { clientX: 20, clientY: 50 });
    fireEvent.click(box, { clientX: 180, clientY: 50 });
    expect(onChange).toHaveBeenCalledTimes(1);
    const cfg = onChange.mock.calls[0][0] as CameraConfig;
    expect(cfg.counting_lines).toHaveLength(1);
    expect(cfg.counting_lines[0].p1).toEqual([0.1, 0.5]);
    expect(cfg.counting_lines[0].p2).toEqual([0.9, 0.5]);
  });
  it("GeometryEditor finishes a zone only with 3+ points", async () => {
    const onChange = vi.fn();
    const { container } = render(<GeometryEditor config={emptyCfg} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /^Zone$/ }));
    const box = container.querySelector(".aspect-video") as HTMLElement;
    box.getBoundingClientRect = () => ({ left: 0, top: 0, width: 100, height: 100, right: 100, bottom: 100, x: 0, y: 0, toJSON: () => ({}) });
    expect(screen.getByRole("button", { name: "Finish zone" })).toBeDisabled();
    for (const [x, y] of [[10, 10], [90, 10], [50, 80]]) fireEvent.click(box, { clientX: x, clientY: y });
    await userEvent.click(screen.getByRole("button", { name: "Finish zone" }));
    expect((onChange.mock.calls[0][0] as CameraConfig).zones[0].polygon).toHaveLength(3);
  });
});
