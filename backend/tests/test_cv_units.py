import math

from app.cv.counting import LineCounter
from app.cv.density import DensityAnalyzer, classify_density
from app.cv.geometry import crossing_direction, point_in_polygon
from app.cv.violations import ViolationEngine
from app.schemas.cv_config import CameraCVConfig, Calibration, CountingLine, SignalConfig, Zone


def test_crossing_direction_and_segment_bounds():
    l1, l2 = (0, 100), (200, 100)
    assert crossing_direction(l1, l2, (50, 90), (50, 110)) == "in"
    assert crossing_direction(l1, l2, (50, 110), (50, 90)) == "out"
    assert crossing_direction(l1, l2, (50, 90), (50, 95)) is None
    assert crossing_direction(l1, l2, (300, 90), (300, 110)) is None  # crosses the infinite line, not the segment


def test_line_counter_counts_once_per_track():
    lc = LineCounter("l", "L", (0, 100), (200, 100))
    assert lc.update(1, (50, 90), "car", 0, 0.0) is None
    assert lc.update(1, (50, 110), "car", 1, 0.1).direction == "in"
    assert lc.update(1, (50, 90), "car", 2, 0.2) is None  # back across: not counted again
    assert lc.update(1, (50, 112), "car", 3, 0.3) is None  # jitter across again: still once
    lc.update(2, (60, 90), "bus", 0, 0.0)
    lc.update(2, (60, 110), "bus", 1, 0.1)
    assert lc.total == 2 and lc.by_class == {"car": 1, "bus": 1}


def test_density_levels():
    assert [classify_density(r) for r in (0.1, 0.3, 0.6, 0.9)] == ["Low", "Moderate", "High", "Critical"]
    z = [{"id": "z", "name": "Z", "polygon": [(0, 0), (100, 0), (100, 100), (0, 100)], "capacity": 4}]
    snap = DensityAnalyzer(z).analyze([(10, 10), (20, 20), (30, 30), (500, 500)], 4)
    assert snap.vehicles == 3 and snap.level == "Critical"


def test_point_in_polygon():
    sq = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert point_in_polygon((5, 5), sq) and not point_in_polygon((15, 5), sq)


class V:  # minimal tracked-vehicle stand-in
    def __init__(self, tid, c, cls="car"):
        self.track_id, self.center, self.class_name = tid, c, cls
        self.bbox = (c[0] - 10, c[1] - 10, c[0] + 10, c[1] + 10)


def run(engine, path, tid=1, fps=10, start=0.0):
    out = []
    for i, p in enumerate(path):
        out += engine.update([V(tid, p)], i, start + i / fps)
    return out


def test_wrong_way_needs_zone_and_opposite_motion():
    cfg = CameraCVConfig(zones=[Zone(id="w", name="NB lane", type="wrong_way", direction=(0, 1),
                                     polygon=[(0, 0), (1, 0), (1, 1), (0, 1)])])
    eng = ViolationEngine(cfg, 1000, 1000)
    assert "wrong_way" in eng.active_modules
    ok = run(eng, [(500, 100 + i * 15) for i in range(40)], tid=1)  # allowed direction (down)
    assert ok == []
    bad = run(ViolationEngine(cfg, 1000, 1000), [(500, 900 - i * 15) for i in range(40)], tid=2)
    assert len(bad) == 1 and bad[0].category == "wrong_way" and bad[0].severity == "high"
    still = run(ViolationEngine(cfg, 1000, 1000), [(500, 500)] * 40, tid=3)  # parked vehicle is not "wrong way"
    assert still == []


def test_modules_are_off_without_configuration():
    eng = ViolationEngine(CameraCVConfig(), 1000, 1000)
    assert eng.active_modules == []
    assert run(eng, [(500, 900 - i * 15) for i in range(40)]) == []
    # speed calibration disabled -> no overspeed, even for a very fast vehicle
    cfg = CameraCVConfig(calibration=Calibration(enabled=False, meters_per_pixel=0.1))
    assert ViolationEngine(cfg, 1000, 1000).active_modules == []
    # red light enabled but no stop line -> module stays off
    assert ViolationEngine(CameraCVConfig(signal=SignalConfig(enabled=True)), 1000, 1000).active_modules == []


def test_restricted_zone_requires_dwell():
    cfg = CameraCVConfig(zones=[Zone(id="r", name="Bus lane", type="restricted", min_dwell_s=1.0,
                                     polygon=[(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)])])
    brief = run(ViolationEngine(cfg, 1000, 1000), [(500, 500)] * 5 + [(100, 100)] * 20)  # 0.5 s inside only
    assert brief == []
    stay = run(ViolationEngine(cfg, 1000, 1000), [(500, 500)] * 20)
    assert len(stay) == 1 and stay[0].category == "restricted_zone"


def test_overspeed_with_calibration():
    cfg = CameraCVConfig(calibration=Calibration(enabled=True, meters_per_pixel=0.05, speed_limit_kmh=50))
    # 20 px per frame at 10 fps = 200 px/s = 10 m/s = 36 km/h  -> under the limit
    assert run(ViolationEngine(cfg, 1000, 1000), [(100, 20 * i) for i in range(40)]) == []
    # 60 px per frame = 600 px/s = 30 m/s = 108 km/h -> violation
    ev = run(ViolationEngine(cfg, 3000, 3000), [(100, 60 * i) for i in range(40)])
    assert len(ev) == 1 and ev[0].details["estimated_speed_kmh"] > 100 and ev[0].severity == "high"


def test_red_light_only_when_signal_red():
    sig = dict(enabled=True, stop_line=((0.0, 0.5), (1.0, 0.5)), mode="manual")
    path = [(500, 400 + i * 20) for i in range(12)]  # crosses y=500 moving down ("in")
    red = ViolationEngine(CameraCVConfig(signal=SignalConfig(manual_state="red", **sig)), 1000, 1000)
    assert [e.category for e in run(red, path)] == ["red_light"]
    green = ViolationEngine(CameraCVConfig(signal=SignalConfig(manual_state="green", **sig)), 1000, 1000)
    assert run(green, path) == []
    cyc = ViolationEngine(CameraCVConfig(signal=SignalConfig(mode="cycle", red_seconds=1, green_seconds=100, **{k: v for k, v in sig.items() if k != "mode"})), 1000, 1000)
    assert cyc.signal_state(0.5) == "red" and cyc.signal_state(5) == "green"
