"""Persists pipeline events (detections, line crossings, violations, analytics buckets) and raises alerts."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

from app.core.database import session_scope
from app.cv.constants import DENSITY_LEVELS
from app.cv.evidence import save_evidence
from app.models.entities import DetectionRecord, TrafficAnalytics, VehicleCount, Violation
from app.schemas.schemas import AppSettings
from app.services.aggregate import BucketAggregator
from app.services.common import add_notification
from app.services.events import hub

log = logging.getLogger(__name__)
CATEGORY_LABEL = {"wrong_way": "Wrong-way driving", "restricted_zone": "Restricted-zone intrusion",
                  "overspeed": "Overspeeding", "red_light": "Red-light violation"}


class EventRecorder:
    def __init__(self, camera_id: int | None, video_id: int | None, camera_name: str, start: datetime,
                 prefs: AppSettings, bucket_seconds: int, emit_alerts: bool = True):
        self.camera_id, self.video_id, self.camera_name, self.start = camera_id, video_id, camera_name, start
        self.prefs, self.emit_alerts = prefs, emit_alerts
        self.agg = BucketAggregator(bucket_seconds, start, prefs.density_thresholds)
        self._rows: list = []
        self._last_flush = time.monotonic()
        self._cong_since: float | None = None
        self._cong_last_alert = -1e9
        self.violations_saved = 0

    def _when(self, t_s: float) -> datetime:
        return self.start + timedelta(seconds=t_s)

    def record(self, res, annotated, t_s: float) -> None:
        w = self._when(t_s)
        for v in res.new_tracks:
            self._rows.append(DetectionRecord(camera_id=self.camera_id, video_id=self.video_id, track_id=v.track_id,
                                              class_name=v.class_name, confidence=round(v.confidence, 3),
                                              frame_index=res.frame_index, video_time_s=round(t_s, 2),
                                              bbox=[int(x) for x in v.bbox], timestamp=w))
        for c in res.crossings:
            self._rows.append(VehicleCount(camera_id=self.camera_id, video_id=self.video_id, line_id=c.line_id,
                                           line_name=c.line_name, track_id=c.track_id, class_name=c.class_name,
                                           direction=c.direction, timestamp=w))
        alerts = []
        for ve in res.violations:
            evidence = save_evidence(annotated, ve, self.camera_name, w)
            self._rows.append(Violation(camera_id=self.camera_id, video_id=self.video_id, track_id=ve.track_id,
                                        category=ve.category, severity=ve.severity, vehicle_class=ve.class_name,
                                        details=ve.details, evidence_name=evidence, frame_index=ve.frame_index,
                                        video_time_s=round(t_s, 2), timestamp=w, is_demo=False))
            self.violations_saved += 1
            alerts.append(ve)
        row = self.agg.add(res, t_s)
        if row:
            self._rows.append(TrafficAnalytics(camera_id=self.camera_id, video_id=self.video_id, is_demo=False, **row))
        for ve in alerts:
            self._alert_violation(ve)
        self._check_congestion(res, t_s)
        if alerts or len(self._rows) >= 300 or time.monotonic() - self._last_flush > 2.0:
            self.flush()

    def _alert_violation(self, ve) -> None:
        if not (self.emit_alerts and self.prefs.notifications.violation_alerts):
            return
        title = f"{CATEGORY_LABEL.get(ve.category, ve.category)} - {self.camera_name}"
        msg = f"{ve.class_name} #{ve.track_id} ({ve.severity} severity)"
        with session_scope() as db:
            add_notification(db, "violation", "critical" if ve.severity in ("high", "critical") else "warning",
                             title, msg, self.camera_id)
        hub.publish("alerts", {"type": "violation", "title": title, "message": msg, "severity": ve.severity,
                               "camera_id": self.camera_id, "simulated": False})

    def _check_congestion(self, res, t_s: float) -> None:
        if not (self.emit_alerts and self.prefs.notifications.congestion_alerts):
            return
        lvl = DENSITY_LEVELS.index(res.density.level)
        if lvl < DENSITY_LEVELS.index(self.prefs.notifications.min_congestion_level):
            self._cong_since = None
            return
        self._cong_since = self._cong_since if self._cong_since is not None else t_s
        if t_s - self._cong_since >= 3.0 and t_s - self._cong_last_alert >= 300:
            self._cong_last_alert = t_s
            title = f"{res.density.level} congestion - {self.camera_name}"
            msg = f"{res.density.vehicles} vehicles in the monitored zones (occupancy {res.density.ratio:.0%})"
            with session_scope() as db:
                add_notification(db, "congestion", "critical" if res.density.level == "Critical" else "warning",
                                 title, msg, self.camera_id)
            hub.publish("alerts", {"type": "congestion", "title": title, "message": msg,
                                   "severity": res.density.level.lower(), "camera_id": self.camera_id, "simulated": False})

    def flush(self, final: bool = False) -> None:
        if final:
            row = self.agg.flush()
            if row:
                self._rows.append(TrafficAnalytics(camera_id=self.camera_id, video_id=self.video_id, is_demo=False, **row))
        self._last_flush = time.monotonic()
        if not self._rows:
            return
        rows, self._rows = self._rows, []
        try:
            with session_scope() as db:
                db.add_all(rows)
        except Exception:  # noqa: BLE001
            log.exception("failed to persist %d rows", len(rows))
