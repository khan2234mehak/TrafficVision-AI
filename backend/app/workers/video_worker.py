"""Background video analysis. Heavy inference runs in a worker thread, never on the FastAPI event loop."""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import cv2

from app.core.config import settings
from app.core.database import session_scope, utcnow
from app.cv.annotate import annotate_frame
from app.cv.density import classify_density
from app.cv.detector import ModelWeightsMissing, get_detector
from app.cv.pipeline import TrafficPipeline
from app.cv.video_io import finalize_video
from app.models.entities import Camera, VideoUpload
from app.schemas.cv_config import CameraCVConfig, default_cv_config
from app.services.common import add_notification, get_app_settings
from app.services.events import hub
from app.services.recorder import EventRecorder

log = logging.getLogger(__name__)


class VideoJob:
    def __init__(self, video_id: int, camera_id: int | None, stride: int):
        self.video_id, self.camera_id, self.stride = video_id, camera_id, stride
        self.running = threading.Event()
        self.running.set()
        self.stop_requested = False
        self.preview: bytes | None = None
        self.stats: dict | None = None


class VideoJobManager:
    def __init__(self) -> None:
        self.executor = ThreadPoolExecutor(max_workers=settings.max_concurrent_video_jobs, thread_name_prefix="video")
        self.jobs: dict[int, VideoJob] = {}

    def submit(self, video_id: int, camera_id: int | None, stride: int) -> VideoJob:
        job = VideoJob(video_id, camera_id, stride)
        self.jobs[video_id] = job
        with session_scope() as db:
            v = db.get(VideoUpload, video_id)
            v.status, v.progress, v.error = "queued", 0.0, None
        self.executor.submit(self._guard, job)
        return job

    def get(self, video_id: int) -> VideoJob | None:
        return self.jobs.get(video_id)

    def pause(self, video_id: int) -> bool:
        job = self.jobs.get(video_id)
        if not job:
            return False
        job.running.clear()
        return True

    def resume(self, video_id: int) -> bool:
        job = self.jobs.get(video_id)
        if not job:
            return False
        job.running.set()
        return True

    def stop(self, video_id: int) -> bool:
        job = self.jobs.get(video_id)
        if not job:
            return False
        job.stop_requested = True
        job.running.set()
        return True

    def active_count(self) -> int:
        return len(self.jobs)

    def shutdown(self) -> None:
        for j in self.jobs.values():
            j.stop_requested = True
            j.running.set()
        self.executor.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------
    def _guard(self, job: VideoJob) -> None:
        try:
            self._run(job)
        except ModelWeightsMissing as e:
            self._fail(job, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("video job %s crashed", job.video_id)
            self._fail(job, f"Processing failed: {e}")
        finally:
            self.jobs.pop(job.video_id, None)

    def _fail(self, job: VideoJob, message: str) -> None:
        with session_scope() as db:
            v = db.get(VideoUpload, job.video_id)
            if v:
                v.status, v.error, v.finished_at = "failed", message, utcnow()
        hub.publish("traffic", {"type": "video_status", "video_id": job.video_id, "status": "failed", "error": message})

    def _set_status(self, vid: int, status: str, **fields) -> None:
        with session_scope() as db:
            v = db.get(VideoUpload, vid)
            if v:
                v.status = status
                for k, val in fields.items():
                    setattr(v, k, val)

    def _run(self, job: VideoJob) -> None:
        with session_scope() as db:
            v = db.get(VideoUpload, job.video_id)
            cam = db.get(Camera, job.camera_id) if job.camera_id else None
            cfg = CameraCVConfig(**(cam.config if cam and cam.config else default_cv_config()))
            prefs = get_app_settings(db)
            src = settings.upload_dir / v.stored_name
            stem = v.stored_name.rsplit(".", 1)[0]
            cam_name = cam.name if cam else f"Upload: {v.original_name}"
            cam_id = cam.id if cam else None
        detector = get_detector()
        cap = cv2.VideoCapture(str(src))
        if not cap.isOpened():
            raise RuntimeError("Could not open the uploaded video (unsupported codec?).")
        writer = None
        tmp_out = settings.processed_dir / f"{stem}_tmp.mp4"
        final_out = settings.processed_dir / f"{stem}_annotated.mp4"
        try:
            fps = cap.get(cv2.CAP_PROP_FPS)
            fps = fps if 1 <= (fps or 0) <= 240 else 25.0
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            pipe = TrafficPipeline(detector, cfg, w, h, fps / job.stride, prefs.confidence, prefs.iou,
                                   prefs.classes, prefs.imgsz, prefs.density_thresholds)
            started = utcnow()
            self._set_status(job.video_id, "processing", started_at=started, fps=fps, width=w, height=h,
                             total_frames=total, duration_s=(total / fps if total else None))
            bucket = 10 if (total / fps if total else 0) < 900 else 30
            rec = EventRecorder(cam_id, job.video_id, cam_name, started, prefs, bucket)
            writer = cv2.VideoWriter(str(tmp_out), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
            if not writer.isOpened():
                raise RuntimeError("Could not create the output video file.")

            idx, last_res, t0, last_push, paused_flag = 0, None, time.monotonic(), 0.0, False
            status = "completed"
            while True:
                if job.stop_requested:
                    status = "stopped"
                    break
                if not job.running.is_set():
                    if not paused_flag:
                        self._set_status(job.video_id, "paused")
                        paused_flag = True
                        hub.publish("traffic", {"type": "video_status", "video_id": job.video_id, "status": "paused"})
                    job.running.wait(0.2)
                    continue
                if paused_flag:
                    self._set_status(job.video_id, "processing")
                    paused_flag = False
                    hub.publish("traffic", {"type": "video_status", "video_id": job.video_id, "status": "processing"})
                ok, frame = cap.read()
                if not ok:
                    break
                t_s = idx / fps
                if idx % job.stride == 0 or last_res is None:
                    last_res = pipe.process(frame, idx, t_s)
                    annotated = annotate_frame(frame, pipe, last_res)
                    rec.record(last_res, annotated, t_s)
                else:
                    annotated = annotate_frame(frame, pipe, last_res)
                writer.write(annotated)
                idx += 1
                now = time.monotonic()
                if now - last_push >= 0.5:
                    last_push = now
                    prog = round(100.0 * idx / total, 1) if total else 0.0
                    small = annotated if w <= 960 else cv2.resize(annotated, (960, int(h * 960 / w)))
                    ok2, buf = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ok2:
                        job.preview = buf.tobytes()
                    job.stats = pipe.snapshot(t_s)
                    with session_scope() as db:
                        vv = db.get(VideoUpload, job.video_id)
                        if vv:
                            vv.progress = prog
                    hub.publish("traffic", {"type": "video_progress", "video_id": job.video_id, "progress": prog,
                                            "frame": idx, "total_frames": total, "fps_processing": round(idx / max(now - t0, 1e-6), 1),
                                            "stats": job.stats, "simulated": False})
            writer.release()
            writer = None
            rec.flush(final=True)

            dur = idx / fps
            snap = pipe.snapshot(dur)
            result = {
                "simulated": False,
                "frames_processed": idx, "duration_s": round(dur, 2), "fps": round(fps, 2), "frame_stride": job.stride,
                "processing_seconds": round(time.monotonic() - t0, 1),
                "total_count": snap["total_count"], "unique_tracked": snap["unique_tracked"],
                "by_class": snap["by_class"], "by_line": snap["by_line"],
                "avg_vehicles_per_frame": round(pipe.vehicle_frame_sum / max(pipe.frames, 1), 2),
                "peak_density_ratio": round(pipe.max_density_ratio, 3),
                "peak_density_level": classify_density(pipe.max_density_ratio, prefs.density_thresholds),
                "violations": snap["violations"], "violations_total": rec.violations_saved,
                "violation_modules": snap["active_violation_modules"],
                "model": settings.yolo_model, "confidence": prefs.confidence,
                "heatmap": pipe.heatmap_grid(), "trajectories": pipe.trajectories(),
                "camera": cam_name,
            }
            playable = finalize_video(tmp_out, final_out) if idx else False
            self._set_status(job.video_id, status, progress=100.0 if status == "completed" else round(100.0 * idx / total, 1) if total else 0.0,
                             result=result, processed_name=final_out.name if final_out.exists() else None,
                             browser_playable=playable, finished_at=utcnow())
            with session_scope() as db:
                add_notification(db, "system", "info", f"Video analysis {status}",
                                 f"{result['total_count']} vehicles counted, {rec.violations_saved} violations", cam_id)
            hub.publish("traffic", {"type": "video_status", "video_id": job.video_id, "status": status, "result": result})
        finally:
            cap.release()
            if writer is not None:
                writer.release()
            tmp_out.unlink(missing_ok=True)


video_jobs = VideoJobManager()
