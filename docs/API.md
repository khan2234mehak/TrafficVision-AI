# REST API

Interactive docs: `http://localhost:8000/docs`. All routes except `/api/health`, `/api/auth/*` need `Authorization: Bearer <token>` (media routes also accept `?token=`). Roles: **viewer** read, **operator** + run analysis/monitoring/upload, **admin** + cameras/settings/users/logs.

| Method | Path | Role | Notes |
|---|---|---|---|
| POST | `/api/auth/register` | public | creates a *viewer*; password >= 8 chars with letters + digits |
| POST | `/api/auth/login` | public | returns `access_token` + user |
| GET | `/api/auth/me` | any | |
| GET/PUT | `/api/users`, `/api/users/{id}/role` | admin | |
| GET | `/api/dashboard/stats` `?range=24h|7d|30d` | any | totals, active cameras, density, violations, vehicles/min |
| GET | `/api/dashboard/traffic-trends`, `/vehicle-distribution`, `/violation-distribution`, `/hourly-flow` | any | |
| POST | `/api/videos/upload` | operator | multipart `file`; MP4/AVI/MOV, size + MIME + magic-byte checks |
| POST | `/api/videos/process` | operator | `{video_id, camera_id?, frame_stride}` -> 202; 503 if weights missing |
| POST | `/api/videos/{id}/pause|resume|stop` | operator | |
| GET | `/api/videos`, `/api/videos/{id}`, `/{id}/status`, `/{id}/result` | any | result = counts, density, violations, heatmap, trajectories |
| GET | `/api/videos/{id}/original|processed|preview|frame` | any (media) | `processed?download=true` forces download |
| DELETE | `/api/videos/{id}` | operator | removes files, evidence, rows |
| GET/POST/PUT/DELETE | `/api/cameras[/{id}]` | any / admin | `config` holds lines, zones, signal, calibration |
| GET | `/api/cameras/{id}/snapshot`, `/api/sample-videos` | any | |
| POST | `/api/monitoring/start|stop` | operator | `{camera_id}` |
| GET | `/api/monitoring/status`, `/{id}/state`, `/stream/{id}` (MJPEG) | any | |
| GET | `/api/violations` | any | filters: `category, severity, camera_id, start, end, search`, pagination |
| GET | `/api/violations/{id}`, `/{id}/evidence` | any | |
| GET | `/api/analytics/traffic`, `/density`, `/peak-hours`, `/heatmap`, `/detections` | any | `tz` = minutes offset for local hours |
| GET | `/api/reports/summary`, `/csv?type=traffic|violations`, `/pdf?period=daily|weekly|monthly` | any | |
| GET/PUT | `/api/settings` | any / admin | confidence, IoU, size, classes, thresholds, demo mode, alerts |
| GET | `/api/notifications`, POST `/read-all` | any | |
| GET | `/api/logs/activity` | admin | |
| GET | `/api/system/health`, `/api/health` | any / public | |
| POST | `/api/demo/refresh` | admin | regenerate simulated data |
