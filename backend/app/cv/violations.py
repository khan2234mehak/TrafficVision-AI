"""Configurable violation modules.

Every module only runs when its prerequisites are configured, and every violation is emitted at most
once per (module, track). Nothing is labelled a violation from ordinary movement alone.

* wrong_way        -> needs a zone of type "wrong_way" with an allowed `direction` vector
* restricted_zone  -> needs a zone of type "restricted"
* overspeed        -> needs calibration.enabled + meters_per_pixel (single-camera speed is approximate)
* red_light        -> needs signal.enabled + stop_line (signal state is configured, not seen in video)
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from app.cv.geometry import Pt, crossing_direction, point_in_polygon
from app.schemas.cv_config import CameraCVConfig

SEVERITY = {"wrong_way": "high", "restricted_zone": "medium", "overspeed": "medium", "red_light": "critical"}


@dataclass
class ViolationEvent:
    category: str
    track_id: int
    class_name: str
    severity: str
    frame_index: int
    timestamp_s: float
    bbox: tuple[float, float, float, float]
    details: dict = field(default_factory=dict)


class SpeedEstimator:
    def __init__(self, meters_per_pixel: float):
        self.mpp = meters_per_pixel
        self._hist: dict[int, deque] = {}
        self.speed: dict[int, float] = {}

    def update(self, track_id: int, p: Pt, t: float) -> float | None:
        h = self._hist.setdefault(track_id, deque(maxlen=40))
        h.append((t, p[0], p[1]))
        # use the oldest sample that is at least 0.5 s old
        ref = None
        for sample in h:
            if t - sample[0] >= 0.5:
                ref = sample
            else:
                break
        if ref is None:
            return self.speed.get(track_id)
        dt = t - ref[0]
        dist_px = math.hypot(p[0] - ref[1], p[1] - ref[2])
        kmh = dist_px * self.mpp / dt * 3.6
        prev = self.speed.get(track_id)
        self.speed[track_id] = kmh if prev is None else 0.6 * prev + 0.4 * kmh
        return self.speed[track_id]

    def forget(self, active: set[int]) -> None:
        for tid in list(self._hist):
            if tid not in active and len(self._hist[tid]) and len(self._hist) > 400:
                self._hist.pop(tid, None)
                self.speed.pop(tid, None)


class ViolationEngine:
    def __init__(self, cfg: CameraCVConfig, width: int, height: int):
        self.w, self.h = width, height
        self.diag = math.hypot(width, height)
        sx = lambda p: (p[0] * width, p[1] * height)  # noqa: E731
        self.wrong_way = [(z.id, z.name, [sx(p) for p in z.polygon], z.direction) for z in cfg.zones
                          if z.type == "wrong_way" and z.direction and math.hypot(*z.direction) > 1e-6]
        self.restricted = [(z.id, z.name, [sx(p) for p in z.polygon], z.min_dwell_s) for z in cfg.zones
                           if z.type == "restricted"]
        self.speed: SpeedEstimator | None = None
        self.limit = cfg.calibration.speed_limit_kmh
        if cfg.calibration.enabled and cfg.calibration.meters_per_pixel:
            self.speed = SpeedEstimator(cfg.calibration.meters_per_pixel)
        self.signal = None
        if cfg.signal.enabled and cfg.signal.stop_line:
            self.signal = cfg.signal
            self.stop_line = (sx(cfg.signal.stop_line[0]), sx(cfg.signal.stop_line[1]))
        self._hist: dict[int, deque] = {}
        self._emitted: set[tuple] = set()
        self._ww_score: dict[tuple, int] = {}
        self._inside_since: dict[tuple, float] = {}
        self._over_since: dict[int, float] = {}
        self._last_pos: dict[int, Pt] = {}

    @property
    def active_modules(self) -> list[str]:
        mods = []
        if self.wrong_way: mods.append("wrong_way")
        if self.restricted: mods.append("restricted_zone")
        if self.speed: mods.append("overspeed")
        if self.signal: mods.append("red_light")
        return mods

    def signal_state(self, t: float) -> str | None:
        if not self.signal:
            return None
        s = self.signal
        if s.mode == "manual":
            return s.manual_state
        phase = (t + s.cycle_offset_s) % (s.red_seconds + s.green_seconds)
        return "red" if phase < s.red_seconds else "green"

    def _emit(self, key: tuple, ev: ViolationEvent, out: list[ViolationEvent]) -> None:
        if key in self._emitted:
            return
        self._emitted.add(key)
        out.append(ev)

    def update(self, vehicles, frame_index: int, t: float) -> list[ViolationEvent]:
        """vehicles: iterable of objects with track_id, class_name, bbox, center."""
        out: list[ViolationEvent] = []
        if not self.active_modules:
            return out
        for v in vehicles:
            tid, c = v.track_id, v.center
            hist = self._hist.setdefault(tid, deque(maxlen=60))
            hist.append((t, c[0], c[1]))
            base = dict(track_id=tid, class_name=v.class_name, frame_index=frame_index, timestamp_s=t, bbox=v.bbox)

            for zid, zname, poly, allowed in self.wrong_way:
                key = ("wrong_way", tid, zid)
                if key in self._emitted or not point_in_polygon(c, poly):
                    continue
                old = next((s for s in hist if t - s[0] >= 0.6), None)
                if old is None:
                    continue
                dx, dy = c[0] - old[1], c[1] - old[2]
                mag = math.hypot(dx, dy)
                if mag < 0.015 * self.diag:
                    continue
                cos = (dx * allowed[0] + dy * allowed[1]) / (mag * math.hypot(*allowed))
                score = self._ww_score.get((tid, zid), 0)
                score = score + 1 if cos < -0.5 else max(0, score - 1)
                self._ww_score[(tid, zid)] = score
                if score >= 6:
                    self._emit(key, ViolationEvent("wrong_way", severity=SEVERITY["wrong_way"], details={
                        "zone": zname, "alignment_cos": round(cos, 2),
                        "rule": "moved against the configured allowed direction for 6+ consecutive checks"}, **base), out)

            for zid, zname, poly, dwell in self.restricted:
                key = ("restricted", tid, zid)
                if key in self._emitted:
                    continue
                if point_in_polygon(c, poly):
                    since = self._inside_since.setdefault((tid, zid), t)
                    if t - since >= dwell:
                        self._emit(key, ViolationEvent("restricted_zone", severity=SEVERITY["restricted_zone"], details={
                            "zone": zname, "dwell_s": round(t - since, 1)}, **base), out)
                else:
                    self._inside_since.pop((tid, zid), None)

            if self.speed:
                kmh = self.speed.update(tid, c, t)
                key = ("overspeed", tid)
                if kmh is not None and key not in self._emitted:
                    if kmh > self.limit:
                        since = self._over_since.setdefault(tid, t)
                        if t - since >= 1.0:
                            sev = "high" if kmh > self.limit * 1.3 else SEVERITY["overspeed"]
                            self._emit(key, ViolationEvent("overspeed", severity=sev, details={
                                "estimated_speed_kmh": round(kmh, 1), "limit_kmh": self.limit,
                                "note": "single-camera estimate, accuracy depends on calibration"}, **base), out)
                    else:
                        self._over_since.pop(tid, None)

            if self.signal:
                prev = self._last_pos.get(tid)
                key = ("red_light", tid)
                if prev is not None and key not in self._emitted:
                    d = crossing_direction(self.stop_line[0], self.stop_line[1], prev, c)
                    state = self.signal_state(t)
                    if d == self.signal.violation_direction and state == "red":
                        self._emit(key, ViolationEvent("red_light", severity=SEVERITY["red_light"], details={
                            "signal_state": state, "signal_source": self.signal.mode,
                            "note": "signal state is configured, not detected from the image"}, **base), out)
            self._last_pos[tid] = c

        if len(self._hist) > 600:  # bounded memory for long-running live sessions
            keep = {v.track_id for v in vehicles}
            for tid in [k for k in self._hist if k not in keep][:300]:
                self._hist.pop(tid, None)
                self._last_pos.pop(tid, None)
        return out
