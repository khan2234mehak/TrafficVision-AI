from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass

from app.cv.geometry import Pt, crossing_direction


@dataclass
class CrossingEvent:
    line_id: str
    line_name: str
    track_id: int
    class_name: str
    direction: str
    frame_index: int
    timestamp_s: float


class LineCounter:
    """Counts vehicles crossing one virtual line. A track id is counted at most ONCE per line,
    so jitter around the line or a vehicle that turns back can never inflate the total."""

    def __init__(self, line_id: str, name: str, p1: Pt, p2: Pt, memory: int = 20000):
        self.line_id, self.name, self.p1, self.p2 = line_id, name, p1, p2
        self._prev: OrderedDict[int, Pt] = OrderedDict()
        self._counted: OrderedDict[int, None] = OrderedDict()
        self._memory = memory
        self.counts = {"in": 0, "out": 0}
        self.by_class: dict[str, int] = {}

    @property
    def total(self) -> int:
        return self.counts["in"] + self.counts["out"]

    def update(self, track_id: int, point: Pt, class_name: str, frame_index: int, timestamp_s: float) -> CrossingEvent | None:
        prev = self._prev.get(track_id)
        self._prev[track_id] = point
        self._prev.move_to_end(track_id)
        if len(self._prev) > self._memory:
            self._prev.popitem(last=False)
        if prev is None or track_id in self._counted:
            return None
        direction = crossing_direction(self.p1, self.p2, prev, point)
        if direction is None:
            return None
        self._counted[track_id] = None
        if len(self._counted) > self._memory:
            self._counted.popitem(last=False)
        self.counts[direction] += 1
        self.by_class[class_name] = self.by_class.get(class_name, 0) + 1
        return CrossingEvent(self.line_id, self.name, track_id, class_name, direction, frame_index, timestamp_s)
