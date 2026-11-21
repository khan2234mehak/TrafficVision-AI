"""Detector abstraction. The default implementation wraps Ultralytics YOLO (YOLO11)."""
from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Protocol

import numpy as np
import supervision as sv

from app.core.config import settings
from app.cv.constants import CLASS_IDS_BY_NAME, VEHICLE_CLASSES

log = logging.getLogger(__name__)


class ModelWeightsMissing(RuntimeError):
    pass


class Detector(Protocol):
    def detect(self, frame: np.ndarray, conf: float, iou: float, classes: list[str], imgsz: int) -> sv.Detections: ...


def resolve_device() -> str:
    if settings.device != "auto":
        return settings.device
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda:0"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
    except Exception:  # torch missing or broken
        pass
    return "cpu"


def weights_path() -> Path:
    p = Path(settings.yolo_model)
    return p if p.is_absolute() else settings.model_dir / p


def weights_available() -> bool:
    return weights_path().exists()


class YoloDetector:
    def __init__(self) -> None:
        self._model = None
        self._lock = threading.Lock()  # one inference at a time (CPU/GPU are shared by all jobs)
        self.device = "cpu"

    def _load(self) -> None:
        path = weights_path()
        if not path.exists():
            raise ModelWeightsMissing(
                f"YOLO weights not found at {path}. Run `python scripts/download_weights.py` "
                "(or scripts\\setup.ps1 on Windows) to download them.")
        try:
            from ultralytics import YOLO
        except ImportError as e:  # pragma: no cover
            raise ModelWeightsMissing("ultralytics is not installed. Run `pip install -r backend/requirements.txt`.") from e
        self.device = resolve_device()
        log.info("Loading YOLO weights %s on %s", path.name, self.device)
        self._model = YOLO(str(path))

    def detect(self, frame, conf, iou, classes, imgsz=640) -> sv.Detections:
        with self._lock:
            if self._model is None:
                self._load()
            ids = [CLASS_IDS_BY_NAME[c] for c in classes if c in CLASS_IDS_BY_NAME] or list(VEHICLE_CLASSES)
            res = self._model.predict(frame, conf=conf, iou=iou, classes=ids, imgsz=imgsz,
                                      device=self.device, verbose=False)[0]
        return sv.Detections.from_ultralytics(res)


_detector: Detector | None = None
_detector_lock = threading.Lock()


def get_detector() -> Detector:
    global _detector
    with _detector_lock:
        if _detector is None:
            _detector = YoloDetector()
        return _detector


def set_detector(det: Detector | None) -> None:
    """Dependency-injection hook used by the automated tests."""
    global _detector
    _detector = det


def ensure_detector_ready() -> None:
    """Fail fast (with a helpful message) when the real YOLO detector has no weights."""
    det = get_detector()
    if isinstance(det, YoloDetector) and not weights_available():
        raise ModelWeightsMissing(
            f"YOLO weights not found at {weights_path()}. Run `python scripts/download_weights.py` "
            "(Windows: scripts\\setup.ps1) and restart the backend.")
