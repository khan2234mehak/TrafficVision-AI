from __future__ import annotations

import json
from pathlib import Path

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.models.entities import ActivityLog, Notification, SystemSetting, User
from app.schemas.schemas import AppSettings

SETTINGS_KEY = "app"


def log_activity(db: Session, user: User | None, action: str, detail: str = "", request: Request | None = None) -> None:
    ip = request.client.host if request and request.client else None
    db.add(ActivityLog(user_id=user.id if user else None, user_email=user.email if user else "system",
                       action=action, detail=detail[:500], ip=ip, created_at=utcnow()))
    db.commit()


def get_app_settings(db: Session) -> AppSettings:
    row = db.get(SystemSetting, SETTINGS_KEY)
    if not row:
        return AppSettings()
    try:
        return AppSettings(**row.value)
    except Exception:
        return AppSettings()


def save_app_settings(db: Session, s: AppSettings) -> None:
    row = db.get(SystemSetting, SETTINGS_KEY)
    if row:
        row.value = json.loads(s.model_dump_json())
        row.updated_at = utcnow()
    else:
        db.add(SystemSetting(key=SETTINGS_KEY, value=json.loads(s.model_dump_json())))
    db.commit()


def add_notification(db: Session, kind: str, severity: str, title: str, message: str = "",
                     camera_id: int | None = None, is_demo: bool = False) -> Notification:
    n = Notification(kind=kind, severity=severity, title=title[:160], message=message[:500],
                     camera_id=camera_id, is_demo=is_demo, created_at=utcnow())
    db.add(n)
    db.commit()
    return n


def safe_join(base: Path, name: str) -> Path | None:
    """Resolve `name` inside `base`, refusing traversal."""
    p = (base / name).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        return None
    return p


def max_upload_bytes() -> int:
    return settings.max_upload_mb * 1024 * 1024
