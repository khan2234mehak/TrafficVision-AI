from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated, Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer, field_validator

UTCDatetime = Annotated[datetime, PlainSerializer(lambda d: d.isoformat() + "Z" if d else None, return_type=str | None)]
T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


# ------------------------------------------------------------------ auth
class RegisterIn(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)
    username: str = Field(min_length=2, max_length=80)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not (re.search(r"[A-Za-z]", v) and re.search(r"\d", v)):
            raise ValueError("password must contain letters and digits")
        return v


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(ORM):
    id: int
    email: str
    username: str
    role: str
    is_active: bool
    created_at: UTCDatetime


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RoleIn(BaseModel):
    role: Literal["admin", "operator", "viewer"]


# ---------------------------------------------------------------- cameras
SourceType = Literal["browser", "webcam", "stream", "file", "none"]


class CameraIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(default="", max_length=255)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    source_type: SourceType = "none"
    source: str = Field(default="", max_length=500)
    config: dict[str, Any] | None = None


class CameraOut(ORM):
    id: int
    name: str
    location: str
    latitude: float | None
    longitude: float | None
    source_type: str
    source: str
    status: str
    last_error: str | None
    config: dict[str, Any]
    is_demo: bool
    created_at: UTCDatetime
    # filled by the API
    density_level: str | None = None
    density_ratio: float | None = None
    monitoring: bool = False


class MonitorStartIn(BaseModel):
    camera_id: int


# ------------------------------------------------------------------ video
class VideoOut(ORM):
    id: int
    original_name: str
    size_bytes: int
    status: str
    progress: float
    camera_id: int | None
    duration_s: float | None
    fps: float | None
    width: int | None
    height: int | None
    total_frames: int | None
    browser_playable: bool
    has_processed: bool = False
    error: str | None
    created_at: UTCDatetime
    started_at: UTCDatetime | None
    finished_at: UTCDatetime | None


class VideoProcessIn(BaseModel):
    video_id: int
    camera_id: int | None = None
    frame_stride: int = Field(default=1, ge=1, le=10)


# -------------------------------------------------------------- violations
class ViolationOut(ORM):
    id: int
    camera_id: int | None
    camera_name: str | None = None
    video_id: int | None
    track_id: int
    category: str
    severity: str
    vehicle_class: str
    details: dict[str, Any]
    has_evidence: bool = False
    frame_index: int
    video_time_s: float | None
    timestamp: UTCDatetime
    is_demo: bool


# ---------------------------------------------------------------- settings
class NotificationPrefs(BaseModel):
    congestion_alerts: bool = True
    violation_alerts: bool = True
    min_congestion_level: Literal["Moderate", "High", "Critical"] = "High"


class AppSettings(BaseModel):
    confidence: float = Field(default=0.35, ge=0.05, le=0.95)
    iou: float = Field(default=0.5, ge=0.1, le=0.95)
    imgsz: Literal[320, 480, 640, 960] = 640
    classes: list[Literal["car", "motorcycle", "bus", "truck", "bicycle"]] = ["car", "motorcycle", "bus", "truck", "bicycle"]
    density_thresholds: tuple[float, float, float] = (0.25, 0.5, 0.75)
    live_frame_stride: int = Field(default=2, ge=1, le=10)
    demo_mode: bool = True
    notifications: NotificationPrefs = NotificationPrefs()

    @field_validator("density_thresholds")
    @classmethod
    def ordered(cls, v):
        if not (0 < v[0] < v[1] < v[2] <= 2):
            raise ValueError("density thresholds must be increasing")
        return v

    @field_validator("classes")
    @classmethod
    def non_empty(cls, v):
        if not v:
            raise ValueError("select at least one vehicle category")
        return v


class NotificationOut(ORM):
    id: int
    kind: str
    severity: str
    title: str
    message: str
    camera_id: int | None
    is_read: bool
    is_demo: bool
    created_at: UTCDatetime


class ActivityOut(ORM):
    id: int
    user_email: str
    action: str
    detail: str
    ip: str | None
    created_at: UTCDatetime
