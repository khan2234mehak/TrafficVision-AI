import numpy as np

from app.cv.annotate import annotate_frame
from app.cv.pipeline import TrafficPipeline
from app.schemas.cv_config import CameraCVConfig, CountingLine, Zone, default_cv_config
from tests.helpers import ScriptedDetector

W, H, FPS = 640, 360, 20


def make_pipe(script, cfg=None):
    cfg = CameraCVConfig(**(cfg or default_cv_config()))
    return TrafficPipeline(ScriptedDetector(script), cfg, W, H, FPS, confidence=0.35)


def run(pipe, frames):
    frame = np.zeros((H, W, 3), np.uint8)
    results = []
    for i in range(frames):
        results.append(pipe.process(frame, i, i / FPS))
    return results


def test_two_vehicles_tracked_and_counted_once():
    # default line sits at y = 0.6 * 360 = 216; both vehicles travel downwards through it
    def script(i):
        return [(100, i * 6, 60, 40, "car"), (400, 20 + i * 5, 90, 50, "bus")]
    pipe = make_pipe(script)
    results = run(pipe, 60)
    ids = {v.track_id for r in results for v in r.vehicles}
    assert len(ids) == 2, "ByteTrack should keep one stable id per vehicle"
    snap = pipe.snapshot(60 / FPS)
    assert snap["total_count"] == 2
    assert snap["by_class"]["car"] == 1 and snap["by_class"]["bus"] == 1
    assert snap["by_line"][0]["in"] == 2 and snap["by_line"][0]["out"] == 0
    assert sum(len(r.crossings) for r in results) == 2  # no duplicate counts
    assert snap["unique_tracked"] == 2


def test_no_detections_is_safe_and_density_low():
    pipe = make_pipe(lambda i: [])
    results = run(pipe, 10)
    assert results[-1].vehicles == [] and results[-1].density.level == "Low"
    assert pipe.snapshot(1.0)["total_count"] == 0


def test_congestion_levels_from_zone_capacity():
    cfg = default_cv_config()
    cfg["zones"][0]["capacity"] = 4
    script = lambda i: [(20 + k * 120, 100, 60, 40, "car") for k in range(5)]  # 5 static vehicles
    pipe = make_pipe(script, cfg)
    last = run(pipe, 15)[-1]
    assert last.density.vehicles == 5 and last.density.level == "Critical"


def test_no_lines_counts_unique_tracks():
    cfg = CameraCVConfig(zones=[Zone(id="z", name="Z", type="density", polygon=[(0, 0), (1, 0), (1, 1), (0, 1)])]).model_dump(mode="json")
    pipe = make_pipe(lambda i: [(50 + i * 3, 100, 60, 40, "motorcycle")], cfg)
    run(pipe, 20)
    assert pipe.snapshot(1.0)["total_count"] == 1 and pipe.snapshot(1.0)["by_class"]["motorcycle"] == 1


def test_class_filter_and_annotation():
    pipe = make_pipe(lambda i: [(100, 50 + i * 4, 60, 40, "car")])
    pipe.classes = ["bus"]  # cars disabled in settings
    res = run(pipe, 12)
    assert all(not r.vehicles for r in res)
    pipe2 = make_pipe(lambda i: [(100, 50 + i * 4, 60, 40, "car")])
    frame = np.zeros((H, W, 3), np.uint8)
    r = None
    for i in range(10):
        r = pipe2.process(frame, i, i / FPS)
    out = annotate_frame(frame, pipe2, r)
    assert out.shape == frame.shape and out.sum() > 0  # boxes/HUD were drawn


def test_heatmap_and_trajectories_collected():
    pipe = make_pipe(lambda i: [(100 + i * 4, 100, 60, 40, "car")])
    run(pipe, 60)
    grid = pipe.heatmap_grid()
    assert len(grid) == 36 and len(grid[0]) == 64 and max(max(r) for r in grid) == 1.0
    assert pipe.trajectories()
