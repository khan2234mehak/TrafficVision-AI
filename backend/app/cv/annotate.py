from __future__ import annotations

import cv2
import numpy as np

from app.cv.constants import CLASS_COLORS

ZONE_COLORS = {"density": (255, 200, 60), "restricted": (60, 60, 255), "wrong_way": (0, 170, 255)}
LEVEL_COLORS = {"Low": (120, 220, 80), "Moderate": (60, 210, 250), "High": (40, 140, 255), "Critical": (60, 60, 240)}


def _label(img, text, x, y, color, scale=0.5):
    (tw, th), base = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    y = max(y, th + 4)
    cv2.rectangle(img, (x, y - th - base - 2), (x + tw + 6, y + 2), color, -1)
    cv2.putText(img, text, (x + 3, y - base + 1), cv2.FONT_HERSHEY_SIMPLEX, scale, (10, 14, 24), 1, cv2.LINE_AA)


def annotate_frame(frame: np.ndarray, pipe, result, show_trails: bool = True, hud: bool = True) -> np.ndarray:
    img = frame.copy()
    h, w = img.shape[:2]
    scale = max(0.45, min(w, h) / 1100)

    overlay = img.copy()
    for z in pipe.zones_px:
        pts = np.array(z["polygon"], dtype=np.int32)
        if z["type"] == "density" and len(pipe.zones_px) == 1:
            continue  # a single whole-frame density zone would just tint everything
        cv2.fillPoly(overlay, [pts], ZONE_COLORS[z["type"]])
        cv2.polylines(img, [pts], True, ZONE_COLORS[z["type"]], 2, cv2.LINE_AA)
        _label(img, z["name"], int(pts[:, 0].min()), int(pts[:, 1].min()) + 16, ZONE_COLORS[z["type"]], 0.45 * scale / 0.5 if scale > 0.5 else 0.45)
        if z["type"] == "wrong_way" and z.get("direction"):
            cx, cy = np.mean(pts, axis=0)
            dx, dy = z["direction"]
            n = max((dx * dx + dy * dy) ** 0.5, 1e-6)
            cv2.arrowedLine(img, (int(cx), int(cy)), (int(cx + dx / n * 60), int(cy + dy / n * 60)), (0, 200, 255), 3, tipLength=0.35)
    img = cv2.addWeighted(overlay, 0.14, img, 0.86, 0)

    counts = {c.line_id: c for c in pipe.counters}
    for lid, name, p1, p2 in pipe.lines_px:
        cv2.line(img, (int(p1[0]), int(p1[1])), (int(p2[0]), int(p2[1])), (255, 230, 0), 2, cv2.LINE_AA)
        c = counts[lid]
        _label(img, f"{name}: {c.total} (in {c.counts['in']} / out {c.counts['out']})", int(p1[0]) + 4, int(p1[1]) - 6, (255, 230, 0), 0.45)
    eng = pipe.violation_engine
    if eng.signal:
        a, b = eng.stop_line
        st = eng.signal_state(result.timestamp_s)
        col = (60, 60, 255) if st == "red" else (90, 220, 90)
        cv2.line(img, (int(a[0]), int(a[1])), (int(b[0]), int(b[1])), col, 3, cv2.LINE_AA)
        _label(img, f"Stop line - signal {st} (configured)", int(a[0]) + 4, int(a[1]) - 6, col, 0.45)

    if show_trails:
        for tid, tr in pipe.trails.items():
            if len(tr) > 1 and any(v.track_id == tid for v in result.vehicles):
                cls = pipe.seen_tracks.get(tid, "car")
                pts = np.array(tr, dtype=np.int32).reshape(-1, 1, 2)
                cv2.polylines(img, [pts], False, CLASS_COLORS.get(cls, (255, 255, 255)), 2, cv2.LINE_AA)

    flagged = {ve.track_id for ve in result.violations}
    for v in result.vehicles:
        x1, y1, x2, y2 = (int(t) for t in v.bbox)
        col = CLASS_COLORS.get(v.class_name, (255, 255, 255))
        if v.track_id in flagged:
            col = (60, 60, 255)
        cv2.rectangle(img, (x1, y1), (x2, y2), col, 2, cv2.LINE_AA)
        txt = f"{v.class_name} #{v.track_id} {v.confidence:.2f}"
        if v.speed_kmh is not None:
            txt += f" {v.speed_kmh:.0f}km/h"
        _label(img, txt, x1, y1, col, 0.5 * scale / 0.5 if scale > 0.5 else 0.5)

    if hud:
        lvl = result.density.level
        text = f"TrafficVision AI | in frame {len(result.vehicles)} | counted {len(pipe.counted_tracks)} | density {lvl}"
        cv2.rectangle(img, (0, 0), (min(w, 560), 26), (24, 16, 10), -1)
        cv2.rectangle(img, (0, 0), (6, 26), LEVEL_COLORS.get(lvl, (200, 200, 200)), -1)
        cv2.putText(img, text, (12, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (240, 235, 230), 1, cv2.LINE_AA)
    return img
