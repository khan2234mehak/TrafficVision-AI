from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import viewer
from app.core.database import get_db
from app.models.entities import Camera, DetectionRecord, User, VideoUpload
from app.schemas.schemas import Page
from app.services import stats
from app.services.common import get_app_settings
from app.workers.live import monitor

router = APIRouter(tags=["analytics"])
RangeQ = Query("24h", pattern="^(1h|6h|24h|7d|30d)$")
IntervalQ = Query(None, pattern="^(5m|15m|1h|1d)$")


# ------------------------------------------------------------------ dashboard
@router.get("/api/dashboard/stats")
def dashboard_stats(range: str = RangeQ, _: User = Depends(viewer), db: Session = Depends(get_db)):
    return stats.dashboard_stats(db, monitor.active_ids(), range)


@router.get("/api/dashboard/traffic-trends")
def traffic_trends(range: str = RangeQ, interval: str | None = IntervalQ, camera_id: int | None = None, tz: int = Query(0, ge=-840, le=840),
                   _: User = Depends(viewer), db: Session = Depends(get_db)):
    rows = stats.load_rows(db, stats.range_start(range), None, camera_id)
    return stats.traffic_series(rows, interval or stats.default_interval(range), tz)


@router.get("/api/dashboard/vehicle-distribution")
def vehicle_distribution(range: str = RangeQ, camera_id: int | None = None, _: User = Depends(viewer), db: Session = Depends(get_db)):
    return stats.distribution(stats.load_rows(db, stats.range_start(range), None, camera_id))


@router.get("/api/dashboard/violation-distribution")
def violation_distribution(range: str = RangeQ, _: User = Depends(viewer), db: Session = Depends(get_db)):
    return stats.violation_distribution(db, stats.range_start(range))


@router.get("/api/dashboard/hourly-flow")
def hourly_flow(range: str = Query("7d", pattern="^(24h|7d|30d)$"), tz: int = Query(0, ge=-840, le=840),
                _: User = Depends(viewer), db: Session = Depends(get_db)):
    return stats.hourly_flow(stats.load_rows(db, stats.range_start(range)), tz)


# ------------------------------------------------------------------ analytics
@router.get("/api/analytics/traffic")
def analytics_traffic(range: str = RangeQ, interval: str | None = IntervalQ, camera_id: int | None = None,
                      tz: int = Query(0, ge=-840, le=840), _: User = Depends(viewer), db: Session = Depends(get_db)):
    rows = stats.load_rows(db, stats.range_start(range), None, camera_id)
    series = stats.traffic_series(rows, interval or stats.default_interval(range), tz)
    return {"range": range, "interval": interval or stats.default_interval(range), "series": series,
            "total": sum(p["total"] for p in series), "distribution": stats.distribution(rows)}


@router.get("/api/analytics/density")
def analytics_density(range: str = RangeQ, interval: str | None = IntervalQ, camera_id: int | None = None,
                      tz: int = Query(0, ge=-840, le=840), _: User = Depends(viewer), db: Session = Depends(get_db)):
    rows = stats.load_rows(db, stats.range_start(range), None, camera_id)
    thr = get_app_settings(db).density_thresholds
    series = stats.density_series(rows, interval or stats.default_interval(range), thr, tz)
    return {"range": range, "thresholds": thr, "series": series}


@router.get("/api/analytics/peak-hours")
def analytics_peak(range: str = Query("7d", pattern="^(24h|7d|30d)$"), camera_id: int | None = None,
                   tz: int = Query(0, ge=-840, le=840), _: User = Depends(viewer), db: Session = Depends(get_db)):
    return stats.peak_hours(stats.load_rows(db, stats.range_start(range), None, camera_id), tz)


@router.get("/api/analytics/heatmap")
def analytics_heatmap(video_id: int | None = None, camera_id: int | None = None, _: User = Depends(viewer), db: Session = Depends(get_db)):
    """Heatmap grid (rows x cols, 0..1) and sampled vehicle trajectories from REAL processing only."""
    if video_id:
        v = db.get(VideoUpload, video_id)
        if not v or not v.result:
            raise HTTPException(404, "No result for this video yet.")
        return {"source": "video", "heatmap": v.result.get("heatmap"), "trajectories": v.result.get("trajectories", []),
                "label": v.original_name}
    if camera_id:
        s = monitor.get(camera_id)
        if s and s.pipe:
            return {"source": "live", "heatmap": s.pipe.heatmap_grid(), "trajectories": s.pipe.trajectories(), "label": s.name}
        raise HTTPException(404, "This camera is not being monitored right now.")
    raise HTTPException(400, "Provide video_id or camera_id.")


@router.get("/api/analytics/detections")
def detection_history(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), class_name: str | None = None,
                      video_id: int | None = None, camera_id: int | None = None, start: datetime | None = None, end: datetime | None = None,
                      _: User = Depends(viewer), db: Session = Depends(get_db)):
    q = select(DetectionRecord)
    if class_name:
        q = q.where(DetectionRecord.class_name == class_name)
    if video_id:
        q = q.where(DetectionRecord.video_id == video_id)
    if camera_id:
        q = q.where(DetectionRecord.camera_id == camera_id)
    if start:
        q = q.where(DetectionRecord.timestamp >= start)
    if end:
        q = q.where(DetectionRecord.timestamp <= end)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(DetectionRecord.id.desc()).offset((page - 1) * page_size).limit(page_size))
    names = {c.id: c.name for c in db.scalars(select(Camera))}
    items = [{"id": r.id, "camera": names.get(r.camera_id), "video_id": r.video_id, "track_id": r.track_id, "class_name": r.class_name,
              "confidence": r.confidence, "frame_index": r.frame_index, "video_time_s": r.video_time_s,
              "timestamp": r.timestamp.isoformat() + "Z"} for r in rows]
    return Page(items=items, total=total, page=page, page_size=page_size)
