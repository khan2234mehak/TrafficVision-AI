"""Analytics queries. Aggregation is done in Python so it works identically on SQLite and PostgreSQL."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.cv.constants import ALL_CATEGORIES, DEFAULT_DENSITY_THRESHOLDS
from app.cv.density import classify_density
from app.models.entities import Camera, TrafficAnalytics, Violation
from app.services.common import get_app_settings

RANGES = {"1h": timedelta(hours=1), "6h": timedelta(hours=6), "24h": timedelta(hours=24),
          "7d": timedelta(days=7), "30d": timedelta(days=30)}
INTERVALS = {"5m": 300, "15m": 900, "1h": 3600, "1d": 86400}


def default_interval(range_key: str) -> str:
    return {"1h": "5m", "6h": "15m", "24h": "1h", "7d": "1h", "30d": "1d"}.get(range_key, "1h")


def range_start(range_key: str) -> datetime:
    return utcnow() - RANGES.get(range_key, RANGES["24h"])


def include_demo(db: Session) -> bool:
    return get_app_settings(db).demo_mode


def load_rows(db: Session, start: datetime, end: datetime | None = None, camera_id: int | None = None) -> list[TrafficAnalytics]:
    q = select(TrafficAnalytics).where(TrafficAnalytics.bucket_start >= start)
    if end:
        q = q.where(TrafficAnalytics.bucket_start <= end)
    if camera_id:
        q = q.where(TrafficAnalytics.camera_id == camera_id)
    if not include_demo(db):
        q = q.where(TrafficAnalytics.is_demo.is_(False))
    return list(db.scalars(q.order_by(TrafficAnalytics.bucket_start)))


def _floor(dt: datetime, seconds: int, tz_min: int) -> datetime:
    local = dt + timedelta(minutes=tz_min)
    epoch = int((local - datetime(1970, 1, 1)).total_seconds())
    local_floor = datetime(1970, 1, 1) + timedelta(seconds=epoch - epoch % seconds)
    return local_floor - timedelta(minutes=tz_min)  # back to UTC for the API


def traffic_series(rows, interval: str, tz_min: int = 0) -> list[dict]:
    sec = INTERVALS.get(interval, 3600)
    acc: dict[datetime, dict] = {}
    for r in rows:
        k = _floor(r.bucket_start, sec, tz_min)
        a = acc.setdefault(k, {"t": k, "total": 0, **{c: 0 for c in ALL_CATEGORIES}})
        a["total"] += r.vehicle_count
        for c, n in (r.class_counts or {}).items():
            if c in a:
                a[c] += n
    return [{**v, "t": v["t"].isoformat() + "Z"} for _, v in sorted(acc.items())]


def density_series(rows, interval: str, thresholds=DEFAULT_DENSITY_THRESHOLDS, tz_min: int = 0) -> list[dict]:
    sec = INTERVALS.get(interval, 3600)
    acc: dict[datetime, list[float]] = defaultdict(list)
    for r in rows:
        acc[_floor(r.bucket_start, sec, tz_min)].append(r.density_ratio)
    out = []
    for k, vals in sorted(acc.items()):
        avg = sum(vals) / len(vals)
        out.append({"t": k.isoformat() + "Z", "avg_ratio": round(avg, 3), "level": classify_density(avg, thresholds),
                    "peak_ratio": round(max(vals), 3)})
    return out


def distribution(rows) -> list[dict]:
    tot = {c: 0 for c in ALL_CATEGORIES}
    for r in rows:
        for c, n in (r.class_counts or {}).items():
            if c in tot:
                tot[c] += n
    return [{"name": c, "value": v} for c, v in tot.items()]


def hourly_flow(rows, tz_min: int = 0) -> list[dict]:
    """Average vehicles per hour-of-day (local time) across the days present in the data."""
    per_day_hour: dict[tuple, int] = defaultdict(int)
    for r in rows:
        local = r.bucket_start + timedelta(minutes=tz_min)
        per_day_hour[(local.date(), local.hour)] += r.vehicle_count
    days_by_hour: dict[int, list[int]] = defaultdict(list)
    for (_, hr), n in per_day_hour.items():
        days_by_hour[hr].append(n)
    return [{"hour": h, "label": f"{h:02d}:00", "avg_vehicles": round(sum(days_by_hour[h]) / len(days_by_hour[h])) if days_by_hour[h] else 0}
            for h in range(24)]


def peak_hours(rows, tz_min: int = 0, top: int = 3) -> dict:
    hourly = hourly_flow(rows, tz_min)
    ranked = sorted(hourly, key=lambda x: x["avg_vehicles"], reverse=True)[:top]
    return {"hourly": hourly, "peaks": [p for p in ranked if p["avg_vehicles"] > 0]}


def violation_distribution(db: Session, start: datetime) -> list[dict]:
    q = select(Violation.category, func.count(Violation.id)).where(Violation.timestamp >= start)
    if not include_demo(db):
        q = q.where(Violation.is_demo.is_(False))
    return [{"name": c, "value": n} for c, n in db.execute(q.group_by(Violation.category)).all()]


def count_violations(db: Session, start: datetime | None = None) -> int:
    q = select(func.count(Violation.id))
    if start:
        q = q.where(Violation.timestamp >= start)
    if not include_demo(db):
        q = q.where(Violation.is_demo.is_(False))
    return db.scalar(q) or 0


def latest_density_by_camera(db: Session) -> dict[int, tuple[float, str]]:
    since = utcnow() - timedelta(hours=24)
    rows = load_rows(db, since)
    thr = get_app_settings(db).density_thresholds
    latest: dict[int, TrafficAnalytics] = {}
    for r in rows:
        if r.camera_id is not None:
            latest[r.camera_id] = r  # rows are ordered by bucket_start ascending
    return {cid: (r.density_ratio, classify_density(r.density_ratio, thr)) for cid, r in latest.items()}


def dashboard_stats(db: Session, active_camera_ids: list[int], range_key: str = "24h") -> dict:
    start = range_start(range_key)
    rows = load_rows(db, start)
    total = sum(r.vehicle_count for r in rows)
    thr = get_app_settings(db).density_thresholds
    last_ts = max((r.bucket_start for r in rows), default=None)
    recent = [r for r in rows if last_ts and r.bucket_start >= last_ts - timedelta(minutes=15)]
    per_cam: dict = defaultdict(list)
    for r in recent:
        per_cam[r.camera_id].append(r)
    vpm = 0.0
    ratios = []
    for rs in per_cam.values():
        secs = sum(x.bucket_seconds for x in rs) or 1
        vpm += sum(x.vehicle_count for x in rs) * 60 / secs
        ratios.append(sum(x.density_ratio for x in rs) / len(rs))
    ratio = sum(ratios) / len(ratios) if ratios else 0.0
    n_cams = db.scalar(select(func.count(Camera.id))) or 0
    return {
        "range": range_key, "total_vehicles": total, "total_cameras": n_cams,
        "active_cameras": len(active_camera_ids),
        "density": {"ratio": round(ratio, 3), "level": classify_density(ratio, thr) if ratios else "No data"},
        "total_violations": count_violations(db, start),
        "vehicles_per_minute": round(vpm, 1),
        "has_data": bool(rows),
        "demo_mode": include_demo(db),
        "demo_rows": any(r.is_demo for r in rows),
        "real_rows": any(not r.is_demo for r in rows),
        "last_update": (last_ts.isoformat() + "Z") if last_ts else None,
    }
