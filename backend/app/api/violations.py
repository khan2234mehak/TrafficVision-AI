from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user_media, viewer
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import User, Violation
from app.schemas.schemas import Page, ViolationOut
from app.services.common import safe_join
from app.services.reports import query_violations

router = APIRouter(prefix="/api/violations", tags=["violations"])


def _out(v: Violation) -> ViolationOut:
    o = ViolationOut.model_validate(v)
    o.camera_name = v.camera.name if v.camera else None
    o.has_evidence = bool(v.evidence_name)
    return o


@router.get("", response_model=Page[ViolationOut])
def list_violations(page: int = Query(1, ge=1), page_size: int = Query(15, ge=1, le=100),
                    category: str | None = None, severity: str | None = None, camera_id: int | None = None,
                    start: datetime | None = None, end: datetime | None = None, search: str | None = Query(None, max_length=60),
                    _: User = Depends(viewer), db: Session = Depends(get_db)):
    q = query_violations(db, start, end, camera_id, category, severity, search)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Violation.timestamp.desc()).offset((page - 1) * page_size).limit(page_size)).unique()
    return Page(items=[_out(v) for v in rows], total=total, page=page, page_size=page_size)


@router.get("/{vid}", response_model=ViolationOut)
def get_violation(vid: int, _: User = Depends(viewer), db: Session = Depends(get_db)):
    v = db.get(Violation, vid)
    if not v:
        raise HTTPException(404, "Violation not found.")
    return _out(v)


@router.get("/{vid}/evidence")
def violation_evidence(vid: int, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    v = db.get(Violation, vid)
    p = safe_join(settings.evidence_dir, v.evidence_name) if v and v.evidence_name else None
    if not p or not p.exists():
        raise HTTPException(404, "No evidence screenshot for this violation.")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
