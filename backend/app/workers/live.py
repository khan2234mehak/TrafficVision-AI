"""Live monitoring sessions (server webcam, network stream, recorded sample file, or browser webcam)."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings
from app.core.database import session_scope, utcnow
from app.cv.annotate import annotate_frame
from app.cv.detector import ModelWeightsMissing, get_detector
from app.cv.pipeline import TrafficPipeline
from app.models.entities import Camera
from app.schemas.cv_config import CameraCVConfig, default_cv_config
from app.services.common import get_app_settings, safe_join
from app.services.events import hub
from app.services.recorder import EventRecorder

log = logging.getLogger(__name__)


def encode_jpeg(img: np.ndarray, max_w: int = 960, quality: int = 70) -> bytes:
    h, w = img.shape[:2]
    if w > max_w:
        img = cv2.resize(img, (max_w, int(h * max_w / w)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return buf.tobytes() if ok else b""


class LiveSession:
    """Holds one camera's pipeline. `process()` is used both by the capture thread and the browser WebSocket."""

    def __init__(self, cam_id: int, name: str, source_type: str, source: str, cfg: dict, fps_hint: float):
        self.cam_id, self.name, self.source_type, self.source = cam_id, name, source_type, source
        self.cfg = CameraCVConfig(**(cfg or default_cv_config()))
        self.fps_hint = fps_hint
        self.prefs = None
        self.pipe: TrafficPipeline | None = None
        self.rec: EventRecorder | None = None
        self.t0 = time.monotonic()
        self.started_at = utcnow()
        self.frame_i = 0
        self.latest_jpeg: bytes | None = None
        self.stats: dict | None = None
        self.error: str | None = None
        self.finished_note: str | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self._last_push = 0.0
        self._lock = threading.Lock()
        self.fps_measured = 0.0

    def _init_pipe(self, frame: np.ndarray) -> None:
        with session_scope() as db:
            self.prefs = get_app_settings(db)
        h, w = frame.shape[:2]
        self.pipe = TrafficPipeline(get_detector(), self.cfg, w, h, self.fps_hint, self.prefs.confidence, self.prefs.iou,
                                    self.prefs.classes, self.prefs.imgsz, self.prefs.density_thresholds)
        self.rec = EventRecorder(self.cam_id, None, self.name, self.started_at, self.prefs, 60)

    def process(self, frame: np.ndarray) -> tuple[np.ndarray, dict]:
        with self._lock:
            if self.pipe is None:
                self._init_pipe(frame)
            t = time.monotonic() - self.t0
            res = self.pipe.process(frame, self.frame_i, t)
            self.frame_i += 1
            ann = annotate_frame(frame, self.pipe, res)
            self.rec.record(res, ann, t)
            self.stats = self.pipe.snapshot(t)
            self.fps_measured = self.frame_i / max(t, 1e-6)
            self.latest_jpeg = encode_jpeg(ann)
            self._publish(res)
            return ann, self.stats

    def _publish(self, res) -> None:
        now = time.monotonic()
        if now - self._last_push < 0.5:
            return
        self._last_push = now
        hub.publish("traffic", {"type": "live_stats", "camera_id": self.cam_id, "camera_name": self.name,
                                "source_type": self.source_type, "stats": self.stats, "simulated": False,
                                "fps": round(self.fps_measured, 1)})

    def close(self) -> None:
        self.stop_event.set()
        if self.rec:
            self.rec.flush(final=True)


class MonitorManager:
    def __init__(self) -> None:
        self.sessions: dict[int, LiveSession] = {}
        self._lock = threading.Lock()

    def get(self, cam_id: int) -> LiveSession | None:
        return self.sessions.get(cam_id)

    def active_ids(self) -> list[int]:
        return list(self.sessions)

    def start(self, cam: Camera) -> LiveSession:
        with self._lock:
            if cam.id in self.sessions:
                return self.sessions[cam.id]
            if cam.source_type == "none":
                raise ValueError("This camera has no video source. Edit the camera and choose a webcam, stream URL, "
                                 "sample video, or browser webcam.")
            if cam.source_type == "file" and not self._resolve_file(cam.source):
                raise ValueError(f"Sample video '{cam.source}' was not found in the sample_data folder.")
            sess = LiveSession(cam.id, cam.name, cam.source_type, cam.source, cam.config,
                               fps_hint=15.0 if cam.source_type != "browser" else 6.0)
            self.sessions[cam.id] = sess
            if cam.source_type != "browser":
                sess.thread = threading.Thread(target=self._capture_loop, args=(sess,), daemon=True,
                                               name=f"live-{cam.id}")
                sess.thread.start()
            self._set_status(cam.id, "online", None)
            return sess

    def stop(self, cam_id: int, error: str | None = None) -> bool:
        with self._lock:
            sess = self.sessions.pop(cam_id, None)
        if not sess:
            return False
        sess.close()
        if sess.thread and sess.thread is not threading.current_thread():
            sess.thread.join(timeout=5)
        self._set_status(cam_id, "error" if error else "offline", error)
        hub.publish("traffic", {"type": "camera_status", "camera_id": cam_id, "status": "error" if error else "offline",
                                "error": error})
        return True

    def stop_all(self) -> None:
        for cid in list(self.sessions):
            self.stop(cid)

    @staticmethod
    def _set_status(cam_id: int, status: str, err: str | None) -> None:
        try:
            with session_scope() as db:
                c = db.get(Camera, cam_id)
                if c:
                    c.status, c.last_error = status, err
        except Exception:  # noqa: BLE001
            log.exception("could not update camera status")

    @staticmethod
    def _resolve_file(name: str) -> Path | None:
        p = safe_join(settings.sample_dir, name)
        return p if p and p.is_file() else None

    @staticmethod
    def _open(sess: LiveSession) -> cv2.VideoCapture:
        if sess.source_type == "webcam":
            idx = int(sess.source or 0)
            cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW) if os.name == "nt" else cv2.VideoCapture(idx)
        elif sess.source_type == "file":
            cap = cv2.VideoCapture(str(MonitorManager._resolve_file(sess.source)))
        else:
            cap = cv2.VideoCapture(sess.source)
        return cap

    def _capture_loop(self, sess: LiveSession) -> None:
        cap = None
        fail = 0
        try:
            cap = self._open(sess)
            if not cap.isOpened():
                hint = (" Check that it is connected, not used by another app (Zoom/Teams) and that Windows camera "
                        "privacy settings allow desktop apps." if sess.source_type == "webcam" else "")
                raise RuntimeError(f"Could not open the {sess.source_type} source.{hint}")
            src_fps = cap.get(cv2.CAP_PROP_FPS)
            src_fps = src_fps if 1 <= (src_fps or 0) <= 120 else 25.0
            with session_scope() as db:
                stride = get_app_settings(db).live_frame_stride
            sess.fps_hint = max(1.0, src_fps / stride)
            n = 0
            next_t = time.monotonic()
            while not sess.stop_event.is_set():
                ok, frame = cap.read()
                if not ok:
                    if sess.source_type == "file":
                        sess.finished_note = "Recorded file finished."
                        break
                    fail += 1
                    if fail > 5:
                        raise RuntimeError("Lost the video source (no frames received).")
                    cap.release()
                    time.sleep(2)
                    cap = self._open(sess)
                    continue
                fail = 0
                n += 1
                if n % stride:
                    continue
                sess.process(frame)
                if sess.source_type == "file":  # pace recorded files to real time
                    next_t += stride / src_fps
                    delay = next_t - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
                    else:
                        next_t = time.monotonic()
        except ModelWeightsMissing as e:
            sess.error = str(e)
        except Exception as e:  # noqa: BLE001
            log.exception("live session %s failed", sess.cam_id)
            sess.error = str(e)
        finally:
            if cap is not None:
                cap.release()
            if sess.cam_id in self.sessions and self.sessions[sess.cam_id] is sess:
                # auto-stop: record the outcome, keep the error visible to the UI
                err = sess.error
                self.sessions.pop(sess.cam_id, None)
                sess.close()
                self._set_status(sess.cam_id, "error" if err else "offline", err)
                hub.publish("traffic", {"type": "camera_status", "camera_id": sess.cam_id,
                                        "status": "error" if err else "offline", "error": err or sess.finished_note})


monitor = MonitorManager()
