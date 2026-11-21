from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

import cv2

log = logging.getLogger(__name__)


def probe_video(path: Path) -> dict | None:
    cap = cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():
            return None
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        ok, _ = cap.read()
        if not ok or w <= 0 or h <= 0:
            return None
        fps = fps if 1 <= fps <= 240 else 25.0
        return {"fps": fps, "total_frames": max(n, 0), "width": w, "height": h, "duration_s": n / fps if n > 0 else None}
    finally:
        cap.release()


def finalize_video(tmp_path: Path, out_path: Path) -> bool:
    """Re-encode OpenCV's MPEG-4 output to H.264 so browsers can play it. Returns True if playable.
    Falls back to the raw file (download still works) when ffmpeg is unavailable."""
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as e:  # noqa: BLE001
        log.warning("ffmpeg unavailable (%s); keeping OpenCV output", e)
        exe = shutil.which("ffmpeg")
    if exe:
        cmd = [exe, "-y", "-loglevel", "error", "-i", str(tmp_path), "-c:v", "libx264", "-preset", "veryfast",
               "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out_path)]
        try:
            subprocess.run(cmd, check=True, timeout=3600, capture_output=True)
            tmp_path.unlink(missing_ok=True)
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("ffmpeg transcode failed: %s", e)
    shutil.move(str(tmp_path), str(out_path))
    return False
