"""Demo data. EVERYTHING created here is flagged is_demo=True and shown as simulated in the UI."""
from __future__ import annotations

import logging
import math
import random
from datetime import timedelta

import cv2
import numpy as np
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import utcnow
from app.core.security import hash_password
from app.cv.constants import ALL_CATEGORIES
from app.cv.density import classify_density
from app.models.entities import Camera, Notification, SystemSetting, TrafficAnalytics, User, Violation
from app.schemas.cv_config import default_cv_config
from app.services.common import log_activity

log = logging.getLogger(__name__)

DEMO_CAMERAS = [  # (name, location, lat, lon, peak vehicles per 15 min)
    ("ITO Junction", "Vikas Marg x Bahadur Shah Zafar Marg, New Delhi", 28.6287, 77.2410, 620),
    ("Connaught Place Outer Circle", "Outer Circle, Connaught Place, New Delhi", 28.6315, 77.2167, 480),
    ("Dhaula Kuan Flyover", "Ring Road / NH-48 junction, New Delhi", 28.5918, 77.1618, 700),
    ("Kashmere Gate ISBT", "Lothian Road, Kashmere Gate, Delhi", 28.6677, 77.2290, 420),
    ("Anand Vihar Interchange", "Anand Vihar, East Delhi", 28.6469, 77.3159, 560),
]
MIX = {"car": 0.60, "motorcycle": 0.24, "bus": 0.05, "truck": 0.08, "bicycle": 0.03}
TZ_MIN = 330  # demo traffic shape follows Indian Standard Time
VIOLATION_MIX = [("wrong_way", "high", 0.25), ("restricted_zone", "medium", 0.35), ("overspeed", "medium", 0.25), ("red_light", "critical", 0.15)]
DEMO_EVIDENCE = {c: f"demo_{c}.jpg" for c in ("wrong_way", "restricted_zone", "overspeed", "red_light")}


def _diurnal(hour_f: float, weekday: int) -> float:
    morning = math.exp(-((hour_f - 9.0) ** 2) / 2.6)
    evening = math.exp(-((hour_f - 18.5) ** 2) / 3.4)
    midday = 0.45 * math.exp(-((hour_f - 13.5) ** 2) / 8)
    night = 0.07
    base = night + 0.85 * morning + 1.0 * evening + midday
    if weekday >= 5:
        base *= 0.72
    return min(1.0, base)


def _make_evidence_images() -> None:
    for cat, fname in DEMO_EVIDENCE.items():
        path = settings.evidence_dir / fname
        if path.exists():
            continue
        img = np.zeros((540, 960, 3), np.uint8)
        for y in range(540):
            img[y, :] = (40 + y // 12, 28 + y // 14, 18 + y // 20)
        cv2.rectangle(img, (0, 330), (960, 540), (50, 50, 55), -1)
        for x in range(0, 960, 120):
            cv2.rectangle(img, (x, 430), (x + 60, 438), (200, 200, 210), -1)
        cv2.rectangle(img, (380, 300), (560, 400), (60, 60, 255), 3)
        cv2.rectangle(img, (385, 330), (555, 395), (90, 90, 100), -1)
        cv2.putText(img, "DEMO - SIMULATED EVIDENCE", (150, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3, cv2.LINE_AA)
        cv2.putText(img, "Not produced by the AI pipeline", (250, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 220, 255), 2, cv2.LINE_AA)
        cv2.putText(img, cat.replace("_", " ").upper(), (390, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (60, 60, 255), 2, cv2.LINE_AA)
        cv2.imwrite(str(path), img)


def seed_users(db: Session) -> None:
    for email, name, pw, role in ((settings.demo_admin_email, "Demo Admin", settings.demo_admin_password, "admin"),
                                  (settings.demo_operator_email, "Demo Operator", settings.demo_operator_password, "operator")):
        if not db.scalar(select(User).where(User.email == email)):
            db.add(User(email=email, username=name, hashed_password=hash_password(pw), role=role))
    db.commit()


def seed_demo(db: Session, days: int = 30) -> None:
    """(Re)generate simulated analytics ending 'now'. Real data is never touched."""
    rnd = random.Random(42)
    _make_evidence_images()
    cams: list[Camera] = []
    for name, loc, lat, lon, peak in DEMO_CAMERAS:
        cam = db.scalar(select(Camera).where(Camera.name == name))
        if not cam:
            cam = Camera(name=name, location=loc, latitude=lat, longitude=lon, source_type="none", status="offline",
                         config=default_cv_config(), is_demo=True)
            db.add(cam)
            db.flush()
        cams.append(cam)
    db.execute(delete(TrafficAnalytics).where(TrafficAnalytics.is_demo.is_(True)))
    db.execute(delete(Violation).where(Violation.is_demo.is_(True)))
    db.execute(delete(Notification).where(Notification.is_demo.is_(True)))

    now = utcnow().replace(second=0, microsecond=0)
    end = now - timedelta(minutes=now.minute % 15)
    start = end - timedelta(days=days)
    rows = []
    t = start
    while t < end:
        local = t + timedelta(minutes=TZ_MIN)
        f = _diurnal(local.hour + local.minute / 60, local.weekday())
        for cam, (_, _, _, _, peak) in zip(cams, DEMO_CAMERAS):
            n = max(0, int(peak * f * rnd.uniform(0.85, 1.12)))
            ratio = min(1.2, 0.04 + 0.95 * (n / peak) * rnd.uniform(0.9, 1.08))
            counts = {c: int(n * MIX[c] * rnd.uniform(0.9, 1.1)) for c in ALL_CATEGORIES}
            rows.append(dict(camera_id=cam.id, bucket_start=t, bucket_seconds=900, vehicle_count=sum(counts.values()),
                             class_counts=counts, avg_vehicles_in_frame=round(ratio * 15, 1),
                             density_ratio=round(ratio, 3), density_level=classify_density(ratio), is_demo=True))
        t += timedelta(minutes=15)
    db.execute(insert(TrafficAnalytics), rows)  # bulk insert: fast first start

    cats, weights = [c for c, _, _ in VIOLATION_MIX], [w for _, _, w in VIOLATION_MIX]
    sev = {c: s for c, s, _ in VIOLATION_MIX}
    for _ in range(70):
        cat = rnd.choices(cats, weights)[0]
        cam = rnd.choice(cams)
        when = end - timedelta(minutes=rnd.randint(10, days * 24 * 60))
        det = {"simulated": True, "note": "Demo record - not detected by the AI pipeline"}
        if cat == "overspeed":
            det.update(estimated_speed_kmh=rnd.randint(72, 110), limit_kmh=60)
        db.add(Violation(camera_id=cam.id, track_id=rnd.randint(1, 900), category=cat, severity=sev[cat],
                         vehicle_class=rnd.choices(["car", "motorcycle", "bus", "truck", "bicycle"], [60, 24, 5, 8, 3])[0], details=det,
                         evidence_name=DEMO_EVIDENCE[cat], frame_index=rnd.randint(30, 9000), timestamp=when, is_demo=True))
    demo_notes = [("congestion", "critical", "Critical congestion - Dhaula Kuan Flyover", "Simulated alert: occupancy above 75%"),
                  ("violation", "warning", "Wrong-way driving - ITO Junction", "Simulated alert (demo data)"),
                  ("congestion", "warning", "High congestion - Anand Vihar Interchange", "Simulated alert (demo data)"),
                  ("system", "info", "Demo mode is on", "Simulated analytics are labelled DEMO. Upload a video to see real AI results.")]
    for i, (k, s, ti, m) in enumerate(demo_notes):
        db.add(Notification(kind=k, severity=s, title=ti, message=m, is_demo=True,
                            created_at=utcnow() - timedelta(minutes=12 * (i + 1))))
    row = db.get(SystemSetting, "demo_seeded")
    if row:
        row.value = {"at": utcnow().isoformat()}
    else:
        db.add(SystemSetting(key="demo_seeded", value={"at": utcnow().isoformat()}))
    db.commit()
    log.info("Demo data generated (%d analytics rows)", len(rows))


def ensure_seed(db: Session) -> None:
    if not settings.seed_demo_data:
        return
    seed_users(db)
    row = db.get(SystemSetting, "demo_seeded")
    stale = True
    if row:
        from datetime import datetime
        try:
            stale = utcnow() - datetime.fromisoformat(row.value["at"]) > timedelta(hours=12)
        except Exception:  # noqa: BLE001
            stale = True
    if stale:
        seed_demo(db)
        log_activity(db, None, "demo_seed", "Simulated demo data generated")
