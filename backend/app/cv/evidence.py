from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from app.core.config import settings

TITLES = {"wrong_way": "WRONG-WAY", "restricted_zone": "RESTRICTED ZONE", "overspeed": "OVERSPEED", "red_light": "RED LIGHT"}


def save_evidence(annotated: np.ndarray, event, camera_name: str, when: datetime) -> str:
    """Write an evidence screenshot (annotated frame + banner) and return its file name."""
    img = annotated.copy()
    h, w = img.shape[:2]
    if w > 1280:
        img = cv2.resize(img, (1280, int(h * 1280 / w)), interpolation=cv2.INTER_AREA)
        sc = 1280 / w
    else:
        sc = 1.0
    x1, y1, x2, y2 = (int(v * sc) for v in event.bbox)
    cv2.rectangle(img, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), (60, 60, 255), 3, cv2.LINE_AA)
    banner = f"{TITLES.get(event.category, event.category.upper())} | {event.class_name} #{event.track_id} | {camera_name} | {when:%Y-%m-%d %H:%M:%S} UTC"
    cv2.rectangle(img, (0, img.shape[0] - 30), (img.shape[1], img.shape[0]), (20, 14, 10), -1)
    cv2.putText(img, banner, (10, img.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA)
    name = f"{uuid.uuid4().hex}.jpg"
    cv2.imwrite(str(settings.evidence_dir / name), img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return name
