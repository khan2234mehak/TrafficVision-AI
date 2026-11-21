# Testing - what was actually run

Environment used to build this: Linux sandbox, Python 3.12, Node 22, **no GPU, PyTorch not installable (disk)**, no camera, no internet except package registries and GitHub.

## Executed and passing
| Suite | Command | Result |
|---|---|---|
| Backend (pytest) | `cd backend && python -m pytest` | **29 passed** |
| Frontend unit/UI (vitest + Testing Library) | `cd frontend && npm test` | **11 passed** |
| TypeScript | `npm run typecheck` | clean |
| Production build | `npm run build` | succeeds |
| Live smoke test | backend + Vite dev server driven by headless Chromium (Playwright): login, every page loads, mobile layout, no JS errors apart from OpenStreetMap tiles (no internet in the sandbox) | passed |
| Weights download | `python scripts/download_weights.py` fetched `yolo11n.pt` (5.6 MB) from GitHub releases | passed |

### Backend coverage
* Geometry, line counter (once per track, direction, segment bounds), density levels, every violation module including "off without configuration".
* Pipeline with **real ByteTrack**: stable IDs, per-class counts, heatmap/trajectories, class filtering, annotation.
* Auth (validation, duplicate email, 401, RBAC for viewer/operator/admin), camera CRUD + validation (path traversal, bad URL, coordinates), settings validation, activity log, system health.
* Demo data labelled and hideable; dashboard/analytics/peak hours/violations filters/search/evidence/CSV/PDF/notifications.
* Upload validation (extension, MIME, magic bytes, empty, size limit, cleanup of rejected files).
* **Full video flow**: upload -> background processing -> WebSocket progress -> annotated H.264 output readable by OpenCV -> DB rows (analytics, detections, violations + evidence) -> dashboard reflects the real data -> delete removes files.
* Pause / resume / stop, missing-weights `503`, live monitoring with a recorded file, browser-webcam WebSocket round trip, WebSocket auth rejection.

### Frontend coverage
Login/register validation + backend errors, all 9 sidebar links navigate, Overview renders API data + demo label + range switch, camera form validation and payload, violation filters/empty states, density meter, pagination, confirm dialog, geometry editor (draw line/zone). One real bug was found and fixed by these tests: modals stole input focus on every keystroke.

## NOT verified (be upfront in an interview)
1. **Real YOLO inference** - a scripted detector replaced YOLO in all tests. Detection quality, speed and GPU use are untested here.
2. **PostgreSQL**, **Docker build/compose**, **Vercel/Render** deployment files.
3. **Physical webcam, RTSP streams** and browser `getUserMedia` (only the server side of the browser-webcam WebSocket was exercised).
4. Windows-specific behaviour (scripts were written for PowerShell but run on Linux only as bash equivalents; `cv2.CAP_DSHOW` path untested).
5. Automated responsive/visual regression - layouts were checked by eye on desktop and a 390 px mobile viewport only.
6. Load/performance and security penetration testing.

First thing to do on your machine: run one real traffic video and check counts against what you see.
