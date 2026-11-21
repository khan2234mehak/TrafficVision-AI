from __future__ import annotations

import platform
import shutil
import time
from datetime import datetime

import psutil
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.deps import admin, viewer
from app.core.config import settings
from app.core.database import get_db
from app.cv.detector import resolve_device, weights_available, weights_path
from app.models.entities import ActivityLog, Notification, User
from app.schemas.schemas import ActivityOut, AppSettings, NotificationOut
from app.services import seed, stats
from app.services.common import get_app_settings, log_activity, save_app_settings
from app.services.events import hub
from app.workers.live import monitor
from app.workers.video_worker import video_jobs

router = APIRouter(tags=["system"])
STARTED = time.time()
_device_cache: str | None = None


@router.get("/api/health")
def health():
    return {"status": "ok", "app": settings.app_name}


@router.get("/api/system/health")
def system_health(_: User = Depends(viewer), db: Session = Depends(get_db)):
    global _device_cache
    if _device_cache is None:
        _device_cache = resolve_device()
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    disk = shutil.disk_usage(settings.data_dir)
    mem = psutil.virtual_memory()
    return {
        "status": "ok" if db_ok else "degraded", "database": {"ok": db_ok, "engine": "SQLite" if settings.is_sqlite else "PostgreSQL"},
        "model": {"weights": settings.yolo_model, "available": weights_available(), "path": str(weights_path()), "device": _device_cache},
        "cpu_percent": psutil.cpu_percent(interval=None), "memory_percent": mem.percent,
        "disk": {"free_gb": round(disk.free / 1e9, 1), "total_gb": round(disk.total / 1e9, 1), "percent": round(100 * disk.used / disk.total, 1)},
        "active_cameras": len(monitor.active_ids()), "active_video_jobs": video_jobs.active_count(),
        "websocket_clients": hub.connection_count(), "uptime_s": int(time.time() - STARTED),
        "python": platform.python_version(), "environment": settings.environment,
    }


@router.get("/api/settings", response_model=AppSettings)
def read_settings(_: User = Depends(viewer), db: Session = Depends(get_db)):
    return get_app_settings(db)


@router.put("/api/settings", response_model=AppSettings)
def write_settings(data: AppSettings, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    save_app_settings(db, data)
    log_activity(db, user, "settings_update", f"confidence={data.confidence}, demo_mode={data.demo_mode}", request)
    return data


@router.post("/api/demo/refresh")
def refresh_demo(request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    if not settings.seed_demo_data:
        raise HTTPException(400, "Demo data is disabled (SEED_DEMO_DATA=false).")
    seed.seed_demo(db)
    log_activity(db, user, "demo_refresh", "", request)
    return {"ok": True}


@router.get("/api/notifications")
def notifications(limit: int = 30, _: User = Depends(viewer), db: Session = Depends(get_db)):
    q = select(Notification)
    if not stats.include_demo(db):
        q = q.where(Notification.is_demo.is_(False))
    rows = list(db.scalars(q.order_by(Notification.created_at.desc()).limit(min(limit, 100))))
    unread = sum(1 for r in rows if not r.is_read)
    return {"unread": unread, "items": [NotificationOut.model_validate(r) for r in rows]}


@router.post("/api/notifications/read-all")
def read_all(_: User = Depends(viewer), db: Session = Depends(get_db)):
    for n in db.scalars(select(Notification).where(Notification.is_read.is_(False))):
        n.is_read = True
    db.commit()
    return {"ok": True}


@router.get("/api/logs/activity", response_model=list[ActivityOut])
def activity(limit: int = 100, _: User = Depends(admin), db: Session = Depends(get_db)):
    return list(db.scalars(select(ActivityLog).order_by(ActivityLog.id.desc()).limit(min(limit, 500))))
