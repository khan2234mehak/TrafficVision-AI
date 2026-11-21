"""SQLAlchemy models. `is_demo` marks simulated rows so they are never confused with real AI output."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, utcnow


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    username: Mapped[str] = mapped_column(String(80))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="viewer")  # admin | operator | viewer
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Camera(Base):
    __tablename__ = "cameras"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    location: Mapped[str] = mapped_column(String(255), default="")
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    # browser | webcam | stream | file | none
    source_type: Mapped[str] = mapped_column(String(20), default="none")
    source: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), default="offline")  # online | offline | error
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class VideoUpload(Base):
    __tablename__ = "video_uploads"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_name: Mapped[str] = mapped_column(String(255))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    processed_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    browser_playable: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_frames: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DetectionRecord(Base):
    """One record per tracked vehicle (written when the track is first confirmed)."""
    __tablename__ = "detection_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True, index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=True, index=True)
    track_id: Mapped[int] = mapped_column(Integer)
    class_name: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float)
    frame_index: Mapped[int] = mapped_column(Integer, default=0)
    video_time_s: Mapped[float] = mapped_column(Float, default=0.0)
    bbox: Mapped[list] = mapped_column(JSON, default=list)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class VehicleCount(Base):
    """One row per counting-line crossing."""
    __tablename__ = "vehicle_counts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True, index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=True, index=True)
    line_id: Mapped[str] = mapped_column(String(40))
    line_name: Mapped[str] = mapped_column(String(120))
    track_id: Mapped[int] = mapped_column(Integer)
    class_name: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(10))  # in | out
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Violation(Base):
    __tablename__ = "violations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True, index=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=True, index=True)
    track_id: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(30), index=True)  # wrong_way | restricted_zone | overspeed | red_light
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    vehicle_class: Mapped[str] = mapped_column(String(30), default="car")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    evidence_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    frame_index: Mapped[int] = mapped_column(Integer, default=0)
    video_time_s: Mapped[float | None] = mapped_column(Float, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    camera = relationship("Camera", lazy="joined")


class TrafficAnalytics(Base):
    """Time-bucketed traffic aggregates used by every chart."""
    __tablename__ = "traffic_analytics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="CASCADE"), nullable=True)
    video_id: Mapped[int | None] = mapped_column(ForeignKey("video_uploads.id", ondelete="CASCADE"), nullable=True)
    bucket_start: Mapped[datetime] = mapped_column(DateTime)
    bucket_seconds: Mapped[int] = mapped_column(Integer, default=900)
    vehicle_count: Mapped[int] = mapped_column(Integer, default=0)  # vehicles that crossed a line (or new tracks)
    class_counts: Mapped[dict] = mapped_column(JSON, default=dict)
    avg_vehicles_in_frame: Mapped[float] = mapped_column(Float, default=0.0)
    density_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    density_level: Mapped[str] = mapped_column(String(10), default="Low")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    __table_args__ = (Index("ix_ta_bucket_camera", "bucket_start", "camera_id"),)


class SystemSetting(Base):
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class ActivityLog(Base):
    __tablename__ = "activity_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_email: Mapped[str] = mapped_column(String(255), default="system")
    action: Mapped[str] = mapped_column(String(60), index=True)
    detail: Mapped[str] = mapped_column(String(500), default="")
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(20))  # violation | congestion | system
    severity: Mapped[str] = mapped_column(String(10), default="info")
    title: Mapped[str] = mapped_column(String(160))
    message: Mapped[str] = mapped_column(String(500), default="")
    camera_id: Mapped[int | None] = mapped_column(ForeignKey("cameras.id", ondelete="SET NULL"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
