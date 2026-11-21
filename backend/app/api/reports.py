from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import viewer
from app.core.database import get_db, utcnow
from app.models.entities import User
from app.services import reports, stats
from app.services.common import log_activity

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _span(start: datetime | None, end: datetime | None) -> tuple[datetime, datetime]:
    end = end or utcnow()
    start = start or end - timedelta(days=7)
    if start > end:
        start, end = end, start
    return start.replace(tzinfo=None), end.replace(tzinfo=None)


@router.get("/summary")
def summary(start: datetime | None = None, end: datetime | None = None, camera_id: int | None = None,
            tz: int = Query(0, ge=-840, le=840), _: User = Depends(viewer), db: Session = Depends(get_db)):
    s, e = _span(start, end)
    rows = stats.load_rows(db, s, e, camera_id)
    days = (e - s).total_seconds() / 86400
    interval = "1h" if days <= 3 else "1d"
    thr = [0.25, 0.5, 0.75]
    return {"start": s.isoformat() + "Z", "end": e.isoformat() + "Z", "interval": interval,
            "total_vehicles": sum(r.vehicle_count for r in rows),
            "series": stats.traffic_series(rows, interval, tz), "distribution": stats.distribution(rows),
            "density": stats.density_series(rows, interval, thr, tz), "peaks": stats.peak_hours(rows, tz)["peaks"],
            "violations": len(list(db.scalars(reports.query_violations(db, s, e, camera_id)))),
            "has_demo": any(r.is_demo for r in rows)}


@router.get("/csv")
def csv_report(request: Request, type: str = Query("traffic", pattern="^(traffic|violations)$"), start: datetime | None = None,
               end: datetime | None = None, camera_id: int | None = None, user: User = Depends(viewer), db: Session = Depends(get_db)):
    s, e = _span(start, end)
    body = reports.csv_traffic(db, s, e, camera_id) if type == "traffic" else reports.csv_violations(db, start=s, end=e, camera_id=camera_id)
    log_activity(db, user, "report_csv", type, request)
    return Response(body, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="trafficvision_{type}_{s:%Y%m%d}_{e:%Y%m%d}.csv"'})


@router.get("/pdf")
def pdf_report(request: Request, period: str = Query("weekly", pattern="^(daily|weekly|monthly)$"), end: datetime | None = None,
               camera_id: int | None = None, tz: int = Query(0, ge=-840, le=840), user: User = Depends(viewer), db: Session = Depends(get_db)):
    end = (end or utcnow()).replace(tzinfo=None)
    data = reports.pdf_report(db, period, end, camera_id, tz)
    log_activity(db, user, "report_pdf", period, request)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="trafficvision_{period}_report_{end:%Y%m%d}.pdf"'})
