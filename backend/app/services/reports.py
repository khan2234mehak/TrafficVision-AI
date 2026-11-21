from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta

from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Camera, TrafficAnalytics, Violation
from app.services import stats
from app.services.common import get_app_settings

PERIODS = {"daily": (timedelta(days=1), "1h"), "weekly": (timedelta(days=7), "1d"), "monthly": (timedelta(days=30), "1d")}


def _safe(v):
    """Neutralise spreadsheet formula injection."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def csv_traffic(db: Session, start: datetime, end: datetime, camera_id: int | None) -> str:
    rows = stats.load_rows(db, start, end, camera_id)
    names = {c.id: c.name for c in db.scalars(select(Camera))}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["bucket_start_utc", "camera", "vehicles", "car", "motorcycle", "bus", "truck", "bicycle",
                "avg_vehicles_in_frame", "density_ratio", "density_level", "data_source"])
    for r in rows:
        cc = r.class_counts or {}
        w.writerow([r.bucket_start.isoformat() + "Z", _safe(names.get(r.camera_id, "")), r.vehicle_count, cc.get("car", 0),
                    cc.get("motorcycle", 0), cc.get("bus", 0), cc.get("truck", 0), cc.get("bicycle", 0),
                    r.avg_vehicles_in_frame, r.density_ratio, r.density_level, "DEMO (simulated)" if r.is_demo else "AI pipeline"])
    return buf.getvalue()


def query_violations(db: Session, start=None, end=None, camera_id=None, category=None, severity=None, search=None):
    q = select(Violation)
    if start:
        q = q.where(Violation.timestamp >= start)
    if end:
        q = q.where(Violation.timestamp <= end)
    if camera_id:
        q = q.where(Violation.camera_id == camera_id)
    if category:
        q = q.where(Violation.category == category)
    if severity:
        q = q.where(Violation.severity == severity)
    if search:
        s = search.strip().lstrip("#")
        if s.isdigit():
            q = q.where((Violation.track_id == int(s)) | (Violation.id == int(s)))
        else:
            q = q.where(Violation.category.ilike(f"%{s.replace(' ', '_')}%") | Violation.vehicle_class.ilike(f"%{s}%"))
    if not stats.include_demo(db):
        q = q.where(Violation.is_demo.is_(False))
    return q


def csv_violations(db: Session, **filters) -> str:
    q = query_violations(db, **filters).order_by(Violation.timestamp.desc())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "timestamp_utc", "camera", "category", "severity", "vehicle_class", "track_id", "details", "data_source"])
    for v in db.scalars(q):
        w.writerow([v.id, v.timestamp.isoformat() + "Z", _safe(v.camera.name if v.camera else ""), v.category, v.severity,
                    v.vehicle_class, v.track_id, _safe(str(v.details)), "DEMO (simulated)" if v.is_demo else "AI pipeline"])
    return buf.getvalue()


def pdf_report(db: Session, period: str, end: datetime, camera_id: int | None, tz_min: int = 0) -> bytes:
    span, interval = PERIODS.get(period, PERIODS["daily"])
    start = end - span
    rows = stats.load_rows(db, start, end, camera_id)
    series = stats.traffic_series(rows, interval, tz_min)
    dist = stats.distribution(rows)
    peaks = stats.peak_hours(rows, tz_min)["peaks"]
    vq = query_violations(db, start, end, camera_id)
    viols = list(db.scalars(vq.order_by(Violation.timestamp.desc()).limit(15)))
    all_v = list(db.scalars(vq))
    cam_name = "All cameras"
    if camera_id and (c := db.get(Camera, camera_id)):
        cam_name = c.name
    thr = get_app_settings(db).density_thresholds
    avg_ratio = sum(r.density_ratio for r in rows) / len(rows) if rows else 0
    has_demo = any(r.is_demo for r in rows) or any(v.is_demo for v in all_v)

    ss = getSampleStyleSheet()
    out = __import__("io").BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"TrafficVision AI {period} report", author="TrafficVision AI")
    el = [Paragraph(f"TrafficVision AI - {period.capitalize()} traffic report", ss["Title"]),
          Paragraph(f"{cam_name} &nbsp;|&nbsp; {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC", ss["Normal"]), Spacer(1, 6)]
    if has_demo:
        el += [Paragraph("<b>Note:</b> this report includes SIMULATED demo data (labelled DEMO in the app). "
                         "Turn off demo mode in Settings to report only AI-pipeline results.", ss["Normal"]), Spacer(1, 6)]
    total = sum(r.vehicle_count for r in rows)
    summary = [["Metric", "Value"], ["Total vehicles counted", f"{total:,}"], ["Violations recorded", str(len(all_v))],
               ["Average density", f"{stats.classify_density(avg_ratio, thr)} ({avg_ratio:.0%})" if rows else "No data"],
               ["Peak hours (local)", ", ".join(p["label"] for p in peaks) or "n/a"]]
    tbl = Table(summary, colWidths=[70 * mm, 90 * mm])
    tbl.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2A55")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                             ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")), ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    el += [tbl, Spacer(1, 10), Paragraph("Vehicle categories", ss["Heading3"])]
    dt = Table([["Category", "Vehicles"]] + [[d["name"].capitalize(), f"{d['value']:,}"] for d in dist], colWidths=[70 * mm, 40 * mm])
    dt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF9")),
                            ("FONTSIZE", (0, 0), (-1, -1), 9)]))
    el += [dt, Spacer(1, 10), Paragraph("Traffic flow", ss["Heading3"])]
    if series:
        pts = series[-24:]
        d = Drawing(170 * mm, 60 * mm)
        bc = VerticalBarChart()
        bc.x, bc.y, bc.width, bc.height = 10, 12, 160 * mm - 10, 50 * mm - 8
        bc.data = [[p["total"] for p in pts]]
        bc.categoryAxis.categoryNames = [p["t"][5:13].replace("T", " ") if interval != "1d" else p["t"][5:10] for p in pts]
        bc.categoryAxis.labels.fontSize = 5
        bc.categoryAxis.labels.angle = 60
        bc.categoryAxis.labels.dy = -8
        bc.valueAxis.labels.fontSize = 6
        bc.bars[0].fillColor = colors.HexColor("#2F7BFF")
        d.add(bc)
        el.append(d)
    else:
        el.append(Paragraph("No traffic data in this period.", ss["Normal"]))
    el += [Spacer(1, 8), Paragraph("Latest violations", ss["Heading3"])]
    if viols:
        vt = Table([["Time (UTC)", "Camera", "Type", "Severity", "Track", "Source"]] +
                   [[v.timestamp.strftime("%m-%d %H:%M"), (v.camera.name if v.camera else "-")[:26], v.category.replace("_", " "),
                     v.severity, str(v.track_id), "DEMO" if v.is_demo else "AI"] for v in viols], repeatRows=1)
        vt.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4D6")), ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEF9")),
                                ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        el.append(vt)
    else:
        el.append(Paragraph("No violations in this period.", ss["Normal"]))
    doc.build(el)
    return out.getvalue()
