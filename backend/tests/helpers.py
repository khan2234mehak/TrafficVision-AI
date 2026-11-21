from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import supervision as sv

COCO = {"bicycle": 1, "car": 2, "motorcycle": 3, "bus": 5, "truck": 7}


class ScriptedDetector:
    """Test double for YOLO: returns boxes computed from the frame counter (the tracker, counter,
    violation engine and everything downstream are the REAL implementations)."""

    def __init__(self, script):
        self.script, self.i = script, 0

    def detect(self, frame, conf, iou, classes, imgsz=640):
        boxes = self.script(self.i) if callable(self.script) else []
        self.i += 1
        if not boxes:
            return sv.Detections.empty()
        xyxy = np.array([[x, y, x + w, y + h] for x, y, w, h, _ in boxes], dtype=float)
        return sv.Detections(xyxy=xyxy, confidence=np.full(len(boxes), 0.9), class_id=np.array([COCO[c] for *_, c in boxes]))


def make_video(path: Path, frames: int = 60, size=(640, 360), fps: int = 20) -> Path:
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    for i in range(frames):
        img = np.full((size[1], size[0], 3), 40, np.uint8)
        cv2.rectangle(img, (0, 200), (size[0], 360), (70, 70, 70), -1)
        cv2.putText(img, f"synthetic test frame {i}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        w.write(img)
    w.release()
    return path


def downward_car(x=100, speed=6, start_y=0, w=60, h=40, cls="car"):
    """Script helper: a vehicle moving down the frame (towards the default counting line)."""
    return lambda i: (x, start_y + i * speed, w, h, cls)
