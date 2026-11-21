from __future__ import annotations

from dataclasses import dataclass, field

from app.cv.constants import DEFAULT_DENSITY_THRESHOLDS, DENSITY_LEVELS
from app.cv.geometry import Pt, point_in_polygon


def classify_density(ratio: float, thresholds=DEFAULT_DENSITY_THRESHOLDS) -> str:
    for level, limit in zip(DENSITY_LEVELS, thresholds):
        if ratio < limit:
            return level
    return DENSITY_LEVELS[-1]


@dataclass
class DensitySnapshot:
    ratio: float = 0.0
    level: str = "Low"
    vehicles: int = 0
    zones: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"ratio": round(self.ratio, 3), "level": self.level, "vehicles": self.vehicles, "zones": self.zones}


class DensityAnalyzer:
    """Occupancy = vehicles inside the zone / zone capacity (vehicles that mean 'full')."""

    def __init__(self, zones_px: list[dict], thresholds=DEFAULT_DENSITY_THRESHOLDS):
        # each zone dict: id, name, polygon(px), capacity
        self.zones = zones_px
        self.thresholds = tuple(thresholds)

    def analyze(self, centers: list[Pt], frame_vehicle_count: int) -> DensitySnapshot:
        if not self.zones:  # fall back to a whole-frame zone with default capacity
            ratio = frame_vehicle_count / 15
            return DensitySnapshot(ratio, classify_density(ratio, self.thresholds), frame_vehicle_count, [])
        zone_info, total, cap = [], 0, 0
        for z in self.zones:
            n = sum(1 for c in centers if point_in_polygon(c, z["polygon"]))
            ratio = n / z["capacity"]
            zone_info.append({"id": z["id"], "name": z["name"], "vehicles": n, "ratio": round(ratio, 3),
                              "level": classify_density(ratio, self.thresholds)})
            total += n
            cap += z["capacity"]
        ratio = total / cap if cap else 0.0
        return DensitySnapshot(ratio, classify_density(ratio, self.thresholds), total, zone_info)
