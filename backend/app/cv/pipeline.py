"""Frame -> detections -> ByteTrack -> counting / density / violations."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field

import numpy as np
import supervision as sv

from app.cv.constants import ALL_CATEGORIES, DEFAULT_DENSITY_THRESHOLDS, VEHICLE_CLASSES
from app.cv.counting import CrossingEvent, LineCounter
from app.cv.density import DensityAnalyzer, DensitySnapshot
from app.cv.detector import Detector
from app.cv.violations import ViolationEngine, ViolationEvent
from app.schemas.cv_config import CameraCVConfig

HEAT_W, HEAT_H = 64, 36


@dataclass
class TrackedVehicle:
    track_id: int
    class_name: str
    confidence: float
    bbox: tuple[float, float, float, float]
    center: tuple[float, float]
    speed_kmh: float | None = None


@dataclass
class FrameResult:
    frame_index: int
    timestamp_s: float
    vehicles: list[TrackedVehicle] = field(default_factory=list)
    new_tracks: list[TrackedVehicle] = field(default_factory=list)
    crossings: list[CrossingEvent] = field(default_factory=list)
    violations: list[ViolationEvent] = field(default_factory=list)
    new_counted: list[tuple[int, str]] = field(default_factory=list)  # (track_id, class) counted for the first time
    density: DensitySnapshot = field(default_factory=DensitySnapshot)


class TrafficPipeline:
    def __init__(self, detector: Detector, config: CameraCVConfig, width: int, height: int, fps: float,
                 confidence: float = 0.35, iou: float = 0.5, classes: list[str] | None = None,
                 imgsz: int = 640, density_thresholds=DEFAULT_DENSITY_THRESHOLDS):
        self.detector, self.cfg = detector, config
        self.w, self.h, self.fps = width, height, max(1.0, fps)
        self.confidence, self.iou, self.imgsz = confidence, iou, imgsz
        self.classes = [c for c in (classes or ALL_CATEGORIES) if c in ALL_CATEGORIES] or ALL_CATEGORIES

        # ByteTrack: detections down to a low score feed the 2nd association stage, tracks are
        # *activated* only by detections above the user's confidence threshold.
        self.tracker = sv.ByteTrack(track_activation_threshold=confidence, lost_track_buffer=int(self.fps * 1.5),
                                    minimum_matching_threshold=0.8, frame_rate=int(self.fps),
                                    minimum_consecutive_frames=2)
        px = lambda p: (p[0] * width, p[1] * height)  # noqa: E731
        self.lines_px = [(l.id, l.name, px(l.p1), px(l.p2)) for l in config.counting_lines]
        self.counters = [LineCounter(i, n, a, b) for i, n, a, b in self.lines_px]
        self.zones_px = [{"id": z.id, "name": z.name, "polygon": [px(p) for p in z.polygon], "capacity": z.capacity,
                          "type": z.type, "direction": z.direction} for z in config.zones]
        self.density = DensityAnalyzer([z for z in self.zones_px if z["type"] == "density"], density_thresholds)
        self.violation_engine = ViolationEngine(config, width, height)

        self.seen_tracks: dict[int, str] = {}
        self.counted_tracks: dict[int, str] = {}
        self.violation_totals: dict[str, int] = {}
        self.trails: dict[int, deque] = {}
        self._last_seen: dict[int, int] = {}
        self.heat = np.zeros((HEAT_H, HEAT_W), dtype=np.float32)
        self.frames = 0
        self.vehicle_frame_sum = 0
        self.max_density_ratio = 0.0
        self.last: FrameResult | None = None
        self._flow: deque = deque()  # (t) of newly counted vehicles for vehicles/min
        self.history_tracks: dict[int, list] = {}  # sampled trajectories for the movement view

    # ------------------------------------------------------------------ core
    def process(self, frame: np.ndarray, frame_index: int, timestamp_s: float) -> FrameResult:
        det_conf = min(self.confidence, 0.1)
        dets = self.detector.detect(frame, det_conf, self.iou, self.classes, self.imgsz)
        if len(dets):
            dets = dets[np.isin(dets.class_id, list(VEHICLE_CLASSES))]
        tracked = self.tracker.update_with_detections(dets) if len(dets) else self.tracker.update_with_detections(sv.Detections.empty())

        res = FrameResult(frame_index, timestamp_s)
        engine_speed = self.violation_engine.speed
        for i in range(len(tracked)):
            if tracked.tracker_id is None or tracked.tracker_id[i] is None:
                continue
            tid = int(tracked.tracker_id[i])
            cls = VEHICLE_CLASSES.get(int(tracked.class_id[i]), "car")
            if cls not in self.classes:
                continue
            x1, y1, x2, y2 = (float(v) for v in tracked.xyxy[i])
            conf = float(tracked.confidence[i]) if tracked.confidence is not None else 0.0
            v = TrackedVehicle(tid, cls, conf, (x1, y1, x2, y2), ((x1 + x2) / 2, (y1 + y2) / 2))
            res.vehicles.append(v)
            if tid not in self.seen_tracks:
                self.seen_tracks[tid] = cls
                res.new_tracks.append(v)
            self._last_seen[tid] = frame_index
            tr = self.trails.setdefault(tid, deque(maxlen=40))
            tr.append(v.center)
            hist = self.history_tracks.setdefault(tid, [])
            if frame_index % max(1, int(self.fps // 2)) == 0:
                hist.append((round(v.center[0] / self.w, 4), round(v.center[1] / self.h, 4)))
            hx = min(HEAT_W - 1, max(0, int(v.center[0] / self.w * HEAT_W)))
            hy = min(HEAT_H - 1, max(0, int(v.center[1] / self.h * HEAT_H)))
            self.heat[hy, hx] += 1

            for lc in self.counters:
                ev = lc.update(tid, v.center, cls, frame_index, timestamp_s)
                if ev:
                    res.crossings.append(ev)
                    if tid not in self.counted_tracks:
                        self.counted_tracks[tid] = cls
                        res.new_counted.append((tid, cls))
                        self._flow.append(timestamp_s)

        if engine_speed:
            for v in res.vehicles:
                v.speed_kmh = engine_speed.speed.get(v.track_id)
        res.violations = self.violation_engine.update(res.vehicles, frame_index, timestamp_s)
        for ve in res.violations:
            self.violation_totals[ve.category] = self.violation_totals.get(ve.category, 0) + 1
        res.density = self.density.analyze([v.center for v in res.vehicles], len(res.vehicles))
        self.max_density_ratio = max(self.max_density_ratio, res.density.ratio)

        if not self.counters:  # no lines configured -> every confirmed unique track counts once
            for v in res.new_tracks:
                self.counted_tracks[v.track_id] = v.class_name
                res.new_counted.append((v.track_id, v.class_name))
                self._flow.append(timestamp_s)
        while self._flow and timestamp_s - self._flow[0] > 60:
            self._flow.popleft()

        self.frames += 1
        self.vehicle_frame_sum += len(res.vehicles)
        if frame_index % 120 == 0:
            self._prune(frame_index)
        self.last = res
        return res

    def _prune(self, frame_index: int) -> None:
        horizon = int(self.fps * 5)
        for tid in [t for t, f in self._last_seen.items() if frame_index - f > horizon]:
            self._last_seen.pop(tid, None)
            self.trails.pop(tid, None)

    # ------------------------------------------------------------ aggregates
    def counts_by_class(self) -> dict[str, int]:
        out = {c: 0 for c in ALL_CATEGORIES}
        for cls in self.counted_tracks.values():
            out[cls] = out.get(cls, 0) + 1
        return out

    def vehicles_per_minute(self, now_s: float) -> float:
        window = min(60.0, max(now_s, 1.0))
        recent = sum(1 for t in self._flow if now_s - t <= 60)
        return round(recent * 60.0 / window, 1)

    def heatmap_grid(self) -> list[list[float]]:
        m = float(self.heat.max())
        grid = (self.heat / m) if m > 0 else self.heat
        return np.round(grid, 3).tolist()

    def trajectories(self, limit: int = 60) -> list[list[list[float]]]:
        longest = sorted(self.history_tracks.values(), key=len, reverse=True)[:limit]
        return [[list(p) for p in t] for t in longest if len(t) >= 3]

    def snapshot(self, now_s: float) -> dict:
        r = self.last
        return {
            "vehicles_in_frame": len(r.vehicles) if r else 0,
            "total_count": len(self.counted_tracks),
            "unique_tracked": len(self.seen_tracks),
            "by_class": self.counts_by_class(),
            "by_line": [{"id": c.line_id, "name": c.name, "in": c.counts["in"], "out": c.counts["out"],
                         "total": c.total, "by_class": c.by_class} for c in self.counters],
            "density": r.density.as_dict() if r else DensitySnapshot().as_dict(),
            "vehicles_per_minute": self.vehicles_per_minute(now_s),
            "violations": dict(self.violation_totals),
            "active_violation_modules": self.violation_engine.active_modules,
            "signal_state": self.violation_engine.signal_state(now_s),
        }
