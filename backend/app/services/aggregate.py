from __future__ import annotations

from datetime import datetime, timedelta

from app.cv.density import classify_density


class BucketAggregator:
    """Turns per-frame results into TrafficAnalytics rows of `bucket_seconds` each."""

    def __init__(self, bucket_seconds: int, start: datetime, thresholds):
        self.size, self.start, self.thr = bucket_seconds, start, thresholds
        self._idx: int | None = None
        self._reset()

    def _reset(self) -> None:
        self.count, self.classes = 0, {}
        self.veh_sum, self.ratio_sum, self.frames = 0, 0.0, 0

    def _row(self) -> dict | None:
        if self._idx is None or self.frames == 0:
            return None
        ratio = self.ratio_sum / self.frames
        return {"bucket_start": self.start + timedelta(seconds=self._idx * self.size), "bucket_seconds": self.size,
                "vehicle_count": self.count, "class_counts": dict(self.classes),
                "avg_vehicles_in_frame": round(self.veh_sum / self.frames, 2), "density_ratio": round(ratio, 3),
                "density_level": classify_density(ratio, self.thr)}

    def add(self, res, t_s: float) -> dict | None:
        idx = int(t_s // self.size)
        done = None
        if self._idx is not None and idx != self._idx:
            done = self._row()
            self._reset()
        self._idx = idx
        for _, cls in res.new_counted:
            self.count += 1
            self.classes[cls] = self.classes.get(cls, 0) + 1
        self.veh_sum += len(res.vehicles)
        self.ratio_sum += res.density.ratio
        self.frames += 1
        return done

    def flush(self) -> dict | None:
        row = self._row()
        self._reset()
        return row
