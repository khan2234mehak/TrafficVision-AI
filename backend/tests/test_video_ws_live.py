import time

import cv2

from app.core.config import settings
from app.cv.detector import set_detector
from app.workers.live import monitor
from tests.helpers import ScriptedDetector, make_video


def _upload(client, headers, path, name="clip.mp4", ctype="video/mp4"):
    with open(path, "rb") as f:
        return client.post("/api/videos/upload", files={"file": (name, f, ctype)}, headers=headers)


def _wait(client, headers, vid, want=("completed", "failed", "stopped"), timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        s = client.get(f"/api/videos/{vid}/status", headers=headers).json()
        if s["status"] in want:
            return s
        time.sleep(0.2)
    raise AssertionError("video processing timed out")


def test_upload_validation(client, operator_h, viewer_h, tmp_path):
    clip = make_video(tmp_path / "ok.mp4", 10)
    assert _upload(client, viewer_h, clip).status_code == 403  # viewers cannot upload
    with open(clip, "rb") as f:
        assert client.post("/api/videos/upload", files={"file": ("a.txt", f, "text/plain")}, headers=operator_h).status_code == 415
    fake = tmp_path / "fake.mp4"
    fake.write_bytes(b"this is definitely not a video file at all" * 10)
    assert _upload(client, operator_h, fake).status_code == 415  # magic bytes mismatch
    assert _upload(client, operator_h, clip, ctype="image/png").status_code == 415  # mime mismatch
    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    assert _upload(client, operator_h, empty).status_code in (400, 415)
    old = settings.max_upload_mb
    settings.max_upload_mb = 0
    try:
        assert _upload(client, operator_h, clip).status_code == 413
    finally:
        settings.max_upload_mb = old
    assert not list(settings.upload_dir.glob("*")), "rejected uploads must not stay on disk"


def test_full_video_pipeline_with_ws_and_violations(client, admin_h, operator_h, viewer_h, tmp_path):
    # camera with a counting line + a restricted zone the car will dwell in
    cfg = {"counting_lines": [{"id": "l1", "name": "Stop bar", "p1": [0.05, 0.6], "p2": [0.95, 0.6]}],
           "zones": [{"id": "r1", "name": "Bus lane", "type": "restricted", "min_dwell_s": 0.5,
                      "polygon": [[0.1, 0.35], [0.4, 0.35], [0.4, 0.75], [0.1, 0.75]]},
                     {"id": "d1", "name": "Road", "type": "density", "capacity": 3,
                      "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]]}]}
    cam = client.post("/api/cameras", json={"name": "Pipeline cam", "source_type": "none", "config": cfg}, headers=admin_h).json()

    def script(i):  # car drives down through the zone and over the line; a bus follows later
        out = [(100, i * 5, 60, 40, "car")]
        if i > 15:
            out.append((420, (i - 15) * 6, 90, 50, "bus"))
        return out
    set_detector(ScriptedDetector(script))

    clip = make_video(tmp_path / "road.mp4", 70, fps=20)
    up = _upload(client, operator_h, clip, "road.mp4")
    assert up.status_code == 201, up.text
    vid = up.json()["id"]
    assert up.json()["width"] == 640 and up.json()["total_frames"] == 70

    token = operator_h["Authorization"].split()[1]
    with client.websocket_connect(f"/ws/traffic?token={token}") as ws:
        assert ws.receive_json()["type"] == "hello"
        r = client.post("/api/videos/process", json={"video_id": vid, "camera_id": cam["id"]}, headers=operator_h)
        assert r.status_code == 202
        assert client.post("/api/videos/process", json={"video_id": vid}, headers=operator_h).status_code in (202, 409)
        seen = set()
        for _ in range(200):
            msg = ws.receive_json()
            seen.add(msg["type"])
            if msg["type"] == "video_status" and msg["status"] in ("completed", "failed"):
                final = msg
                break
        assert "video_progress" in seen or final["status"] == "completed"
        assert final["status"] == "completed", final
    bad_ws = None
    try:
        with client.websocket_connect("/ws/traffic?token=bad") as w2:
            w2.receive_json()
    except Exception as e:  # noqa: BLE001
        bad_ws = e
    assert bad_ws is not None, "invalid token must be rejected on the websocket"

    st = _wait(client, operator_h, vid)
    assert st["status"] == "completed"
    res = client.get(f"/api/videos/{vid}/result", headers=viewer_h).json()["result"]
    assert res["simulated"] is False and res["frames_processed"] == 70
    assert res["total_count"] == 2 and res["by_class"]["car"] == 1 and res["by_class"]["bus"] == 1
    assert res["by_line"][0]["total"] == 2
    assert res["violations"].get("restricted_zone", 0) >= 1 and "restricted_zone" in res["violation_modules"]
    assert len(res["heatmap"]) == 36 and res["trajectories"]

    # annotated output exists, is a real video, and can be downloaded
    token_q = f"?token={viewer_h['Authorization'].split()[1]}"
    out = client.get(f"/api/videos/{vid}/processed{token_q}")
    assert out.status_code == 200 and len(out.content) > 1000
    assert client.get(f"/api/videos/{vid}/processed?download=true&token={token_q[7:]}").headers["content-disposition"].startswith("attachment")
    p = settings.processed_dir / client.get(f"/api/videos/{vid}", headers=viewer_h).json()["id"].__str__()
    f = next(settings.processed_dir.glob("*_annotated.mp4"))
    cap = cv2.VideoCapture(str(f))
    ok, frame = cap.read()
    assert ok and frame.shape[:2] == (360, 640) and int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) >= 60
    cap.release()
    assert client.get(f"/api/videos/{vid}/processed").status_code == 401  # media requires auth

    # database rows written from REAL processing
    viol = client.get(f"/api/violations?search=restricted", headers=viewer_h).json()
    real = [v for v in viol["items"] if not v["is_demo"] and v["video_id"] == vid]
    assert real and real[0]["has_evidence"] and real[0]["category"] == "restricted_zone"
    ev = client.get(f"/api/violations/{real[0]['id']}/evidence{token_q}")
    assert ev.status_code == 200 and ev.content[:2] == b"\xff\xd8"
    dets = client.get(f"/api/analytics/detections?video_id={vid}", headers=viewer_h).json()
    assert dets["total"] == 2
    heat = client.get(f"/api/analytics/heatmap?video_id={vid}", headers=viewer_h).json()
    assert heat["source"] == "video"
    s = client.get("/api/settings", headers=viewer_h).json()
    client.put("/api/settings", json={**s, "demo_mode": False}, headers=admin_h)
    stats = client.get("/api/dashboard/stats?range=24h", headers=viewer_h).json()
    assert stats["real_rows"] and stats["total_vehicles"] == 2  # dashboard reflects real processing data
    client.put("/api/settings", json={**s, "demo_mode": True}, headers=admin_h)
    pdf = client.get("/api/reports/pdf?period=daily", headers=viewer_h)
    assert pdf.content[:4] == b"%PDF"

    # delete removes the files
    assert client.delete(f"/api/videos/{vid}", headers=operator_h).status_code == 204
    assert client.get(f"/api/videos/{vid}", headers=viewer_h).status_code == 404
    assert not list(settings.processed_dir.glob("*_annotated.mp4"))
    assert client.get(f"/api/violations/{real[0]['id']}/evidence{token_q}").status_code == 404


def test_pause_resume_stop(client, operator_h, tmp_path):
    set_detector(ScriptedDetector(lambda i: (time.sleep(0.05), [])[1]))  # slow detector so we can interact
    clip = make_video(tmp_path / "slow.mp4", 200)
    vid = _upload(client, operator_h, clip).json()["id"]
    assert client.post("/api/videos/process", json={"video_id": vid}, headers=operator_h).status_code == 202
    time.sleep(0.6)
    assert client.post(f"/api/videos/{vid}/pause", headers=operator_h).status_code == 200
    _wait(client, operator_h, vid, want=("paused",), timeout=10)
    p1 = client.get(f"/api/videos/{vid}/status", headers=operator_h).json()["progress"]
    time.sleep(0.8)
    assert client.get(f"/api/videos/{vid}/status", headers=operator_h).json()["progress"] == p1  # really paused
    assert client.post(f"/api/videos/{vid}/resume", headers=operator_h).status_code == 200
    time.sleep(0.6)
    assert client.post(f"/api/videos/{vid}/stop", headers=operator_h).status_code == 200
    st = _wait(client, operator_h, vid, want=("stopped", "completed"))
    assert st["status"] == "stopped" and 0 < st["progress"] < 100
    assert client.post(f"/api/videos/{vid}/stop", headers=operator_h).status_code == 409
    client.delete(f"/api/videos/{vid}", headers=operator_h)


def test_missing_weights_is_graceful(client, operator_h, tmp_path):
    set_detector(None)  # real YoloDetector, no weights in the temp model dir
    clip = make_video(tmp_path / "w.mp4", 5)
    vid = _upload(client, operator_h, clip).json()["id"]
    r = client.post("/api/videos/process", json={"video_id": vid}, headers=operator_h)
    assert r.status_code == 503 and "download_weights" in r.json()["detail"]
    h = client.get("/api/system/health", headers=operator_h).json()
    assert h["model"]["available"] is False
    client.delete(f"/api/videos/{vid}", headers=operator_h)


def test_live_monitoring_with_recorded_file(client, admin_h, operator_h, viewer_h, tmp_path):
    make_video(settings.sample_dir / "live.mp4", 80, fps=20)
    assert "live.mp4" in client.get("/api/sample-videos", headers=viewer_h).json()["files"]
    set_detector(ScriptedDetector(lambda i: [(100, i * 6, 60, 40, "car")]))
    cam = client.post("/api/cameras", json={"name": "Live file cam", "source_type": "file", "source": "live.mp4"}, headers=admin_h)
    assert cam.status_code == 201, cam.text
    cid = cam.json()["id"]
    r = client.post("/api/monitoring/start", json={"camera_id": cid}, headers=operator_h)
    assert r.status_code == 200 and r.json()["mode"] == "server"
    deadline = time.time() + 20
    state = {}
    while time.time() < deadline:
        state = client.get(f"/api/monitoring/{cid}/state", headers=viewer_h).json()
        if state["stats"] and state["stats"]["total_count"] >= 1:
            break
        time.sleep(0.2)
    assert state["stats"]["total_count"] >= 1
    token = viewer_h["Authorization"].split()[1]
    snap = client.get(f"/api/cameras/{cid}/snapshot", headers=viewer_h)
    assert snap.status_code == 200 and snap.content[:2] == b"\xff\xd8"
    assert next(c for c in client.get("/api/cameras", headers=viewer_h).json() if c["id"] == cid)["monitoring"] in (True, False)
    assert client.post("/api/monitoring/stop", json={"camera_id": cid}, headers=operator_h).status_code == 200
    time.sleep(0.3)
    assert monitor.get(cid) is None
    cams = {c["id"]: c for c in client.get("/api/cameras", headers=viewer_h).json()}
    assert cams[cid]["status"] == "offline"
    client.delete(f"/api/cameras/{cid}", headers=admin_h)


def test_browser_webcam_websocket(client, admin_h, operator_h):
    import numpy as np
    set_detector(ScriptedDetector(lambda i: [(100, 20 + i * 8, 60, 40, "car")]))
    cid = client.post("/api/cameras", json={"name": "Browser cam", "source_type": "browser"}, headers=admin_h).json()["id"]
    token = operator_h["Authorization"].split()[1]
    r = client.post("/api/monitoring/start", json={"camera_id": cid}, headers=operator_h)
    assert r.json()["mode"] == "browser"
    with client.websocket_connect(f"/ws/webcam?camera_id={cid}&token={token}") as ws:
        ok, buf = cv2.imencode(".jpg", np.full((360, 640, 3), 90, np.uint8))
        for _ in range(12):
            ws.send_bytes(buf.tobytes())
            msg = ws.receive_json()
            assert msg["type"] == "frame"
        assert msg["stats"]["vehicles_in_frame"] == 1 and msg["image"]
    time.sleep(0.2)
    assert monitor.get(cid) is None  # closing the tab ends the session
    client.delete(f"/api/cameras/{cid}", headers=admin_h)
