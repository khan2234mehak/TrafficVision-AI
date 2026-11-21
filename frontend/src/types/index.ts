export type Role = "admin" | "operator" | "viewer";
export interface User { id: number; email: string; username: string; role: Role; is_active: boolean; created_at: string }
export type DensityLevel = "Low" | "Moderate" | "High" | "Critical" | "No data";
export type Point = [number, number];

export interface CountingLine { id: string; name: string; p1: Point; p2: Point }
export interface Zone {
  id: string; name: string; type: "density" | "restricted" | "wrong_way";
  polygon: Point[]; direction?: Point | null; capacity: number; min_dwell_s: number;
}
export interface SignalConfig {
  enabled: boolean; mode: "manual" | "cycle"; manual_state: "red" | "green"; red_seconds: number; green_seconds: number;
  cycle_offset_s: number; stop_line: [Point, Point] | null; violation_direction: "in" | "out";
}
export interface Calibration { enabled: boolean; meters_per_pixel: number | null; speed_limit_kmh: number }
export interface CameraConfig { counting_lines: CountingLine[]; zones: Zone[]; signal: SignalConfig; calibration: Calibration }

export type SourceType = "browser" | "webcam" | "stream" | "file" | "none";
export interface Camera {
  id: number; name: string; location: string; latitude: number | null; longitude: number | null;
  source_type: SourceType; source: string; status: "online" | "offline" | "error" | "demo"; last_error: string | null;
  config: CameraConfig; is_demo: boolean; created_at: string;
  density_level: DensityLevel | null; density_ratio: number | null; monitoring: boolean;
}

export interface DashboardStats {
  range: string; total_vehicles: number; total_cameras: number; active_cameras: number;
  density: { ratio: number; level: DensityLevel }; total_violations: number; vehicles_per_minute: number;
  has_data: boolean; demo_mode: boolean; demo_rows: boolean; real_rows: boolean; last_update: string | null;
}
export interface TrafficPoint { t: string; total: number; car: number; motorcycle: number; bus: number; truck: number; bicycle: number }
export interface DistPoint { name: string; value: number }
export interface DensityPoint { t: string; avg_ratio: number; level: DensityLevel; peak_ratio: number }
export interface HourPoint { hour: number; label: string; avg_vehicles: number }

export interface LiveStats {
  vehicles_in_frame: number; total_count: number; unique_tracked: number; by_class: Record<string, number>;
  by_line: { id: string; name: string; in: number; out: number; total: number }[];
  density: { ratio: number; level: DensityLevel; vehicles: number; zones: { id: string; name: string; vehicles: number; level: DensityLevel }[] };
  vehicles_per_minute: number; violations: Record<string, number>; active_violation_modules: string[]; signal_state: string | null;
}

export interface Video {
  id: number; original_name: string; size_bytes: number; status: "uploaded" | "queued" | "processing" | "paused" | "completed" | "failed" | "stopped";
  progress: number; camera_id: number | null; duration_s: number | null; fps: number | null; width: number | null; height: number | null;
  total_frames: number | null; browser_playable: boolean; has_processed: boolean; error: string | null; created_at: string;
}
export interface VideoResult {
  frames_processed: number; duration_s: number; fps: number; processing_seconds: number; total_count: number; unique_tracked: number;
  by_class: Record<string, number>; by_line: { id: string; name: string; in: number; out: number; total: number }[];
  avg_vehicles_per_frame: number; peak_density_ratio: number; peak_density_level: DensityLevel;
  violations: Record<string, number>; violations_total: number; violation_modules: string[]; model: string;
  heatmap: number[][]; trajectories: number[][][]; camera: string;
}

export interface Violation {
  id: number; camera_id: number | null; camera_name: string | null; video_id: number | null; track_id: number; category: string;
  severity: "low" | "medium" | "high" | "critical"; vehicle_class: string; details: Record<string, unknown>; has_evidence: boolean;
  frame_index: number; video_time_s: number | null; timestamp: string; is_demo: boolean;
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface AppSettings {
  confidence: number; iou: number; imgsz: 320 | 480 | 640 | 960; classes: string[]; density_thresholds: [number, number, number];
  live_frame_stride: number; demo_mode: boolean;
  notifications: { congestion_alerts: boolean; violation_alerts: boolean; min_congestion_level: "Moderate" | "High" | "Critical" };
}
export interface AppNotification { id: number; kind: string; severity: string; title: string; message: string; camera_id: number | null; is_read: boolean; is_demo: boolean; created_at: string }
export interface ActivityLog { id: number; user_email: string; action: string; detail: string; ip: string | null; created_at: string }
export interface SystemHealth {
  status: string; database: { ok: boolean; engine: string }; model: { weights: string; available: boolean; path: string; device: string };
  cpu_percent: number; memory_percent: number; disk: { free_gb: number; total_gb: number; percent: number };
  active_cameras: number; active_video_jobs: number; websocket_clients: number; uptime_s: number; python: string; environment: string;
}
