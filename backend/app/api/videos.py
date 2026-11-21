from __future__ import annotations

import uuid
from pathlib import Path

import cv2
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import current_user_media, operator, viewer
from app.core.config import settings
from app.core.database import get_db
from app.cv.detector import ModelWeightsMissing, ensure_detector_ready
from app.cv.video_io import probe_video
from app.models.entities import Camera, User, VideoUpload, Violation
from app.schemas.schemas import Page, VideoOut, VideoProcessIn
from app.services.common import log_activity, max_upload_bytes, safe_join
from app.workers.live import encode_jpeg
from app.workers.video_worker import video_jobs

router = APIRouter(prefix="/api/videos", tags=["videos"])
ALLOWED = {".mp4": {"video/mp4", "application/octet-stream"}, ".mov": {"video/quicktime", "video/mp4", "application/octet-stream"},
           ".avi": {"video/x-msvideo", "video/avi", "video/msvideo", "application/x-troff-msvideo", "application/octet-stream"}}


def _looks_like(ext: str, head: bytes) -> bool:
    if ext in (".mp4", ".mov"):
        return head[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"wide", b"skip", b"pnot")
    return head[:4] == b"RIFF" and head[8:12] == b"AVI "


def _out(v: VideoUpload) -> VideoOut:
    o = VideoOut.model_validate(v)
    o.has_processed = bool(v.processed_name)
    return o


def _get(db: Session, vid: int) -> VideoUpload:
    v = db.get(VideoUpload, vid)
    if not v:
        raise HTTPException(404, "Video not found.")
    return v


@router.get("", response_model=Page[VideoOut])
def list_videos(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
                _: User = Depends(viewer), db: Session = Depends(get_db)):
    total = db.scalar(select(func.count(VideoUpload.id))) or 0
    rows = db.scalars(select(VideoUpload).order_by(VideoUpload.id.desc()).offset((page - 1) * page_size).limit(page_size))
    return Page(items=[_out(v) for v in rows], total=total, page=page, page_size=page_size)


@router.post("/upload", response_model=VideoOut, status_code=201)
async def upload_video(request: Request, file: UploadFile = File(...), user: User = Depends(operator), db: Session = Depends(get_db)):
    name = Path(file.filename or "").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(415, "Unsupported file type. Upload an MP4, AVI or MOV video.")
    if (file.content_type or "application/octet-stream").lower() not in ALLOWED[ext]:
        raise HTTPException(415, f"The file's content type ({file.content_type}) does not match a {ext} video.")
    limit = max_upload_bytes()
    stored = f"{uuid.uuid4().hex}{ext}"
    dest = settings.upload_dir / stored
    size, head = 0, b""
    try:
        with dest.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                if not head:
                    head = chunk[:16]
                    if not _looks_like(ext, head):
                        raise HTTPException(415, "The file content is not a valid video of the declared type.")
                size += len(chunk)
                if size > limit:
                    raise HTTPException(413, f"File too large. The limit is {settings.max_upload_mb} MB.")
                out.write(chunk)
        if size == 0:
            raise HTTPException(400, "The uploaded file is empty.")
        info = probe_video(dest)
        if not info:
            raise HTTPException(422, "The video could not be decoded. Try re-exporting it as H.264 MP4.")
    except HTTPException:
        dest.unlink(missing_ok=True)
        raise
    except Exception:
        dest.unlink(missing_ok=True)
        raise
    v = VideoUpload(user_id=user.id, original_name=name[:255], stored_name=stored, size_bytes=size, status="uploaded",
                    fps=info["fps"], width=info["width"], height=info["height"], total_frames=info["total_frames"],
                    duration_s=info["duration_s"])
    db.add(v)
    db.commit()
    log_activity(db, user, "video_upload", f"{name} ({size // 1024} KB)", request)
    return _out(v)


@router.post("/process", response_model=VideoOut, status_code=202)
def process_video(data: VideoProcessIn, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    v = _get(db, data.video_id)
    if video_jobs.get(v.id) or v.status in ("queued", "processing", "paused"):
        raise HTTPException(409, "This video is already being processed.")
    if data.camera_id and not db.get(Camera, data.camera_id):
        raise HTTPException(404, "Camera not found.")
    try:
        ensure_detector_ready()
    except ModelWeightsMissing as e:
        raise HTTPException(503, str(e)) from e
    if v.processed_name:
        (settings.processed_dir / v.processed_name).unlink(missing_ok=True)
        v.processed_name, v.result, v.browser_playable = None, None, False
    v.camera_id = data.camera_id
    db.commit()
    video_jobs.submit(v.id, data.camera_id, data.frame_stride)
    log_activity(db, user, "video_process", v.original_name, request)
    db.refresh(v)
    return _out(v)


def _control(action: str, vid: int, user: User, request: Request, db: Session):
    v = _get(db, vid)
    ok = getattr(video_jobs, action)(vid)
    if not ok:
        raise HTTPException(409, "This video is not currently being processed.")
    log_activity(db, user, f"video_{action}", v.original_name, request)
    return {"video_id": vid, "action": action, "ok": True}


@router.post("/{vid}/pause")
def pause(vid: int, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    return _control("pause", vid, user, request, db)


@router.post("/{vid}/resume")
def resume(vid: int, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    return _control("resume", vid, user, request, db)


@router.post("/{vid}/stop")
def stop(vid: int, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    return _control("stop", vid, user, request, db)


@router.get("/{vid}", response_model=VideoOut)
def get_video(vid: int, _: User = Depends(viewer), db: Session = Depends(get_db)):
    return _out(_get(db, vid))


@router.get("/{vid}/status")
def video_status(vid: int, _: User = Depends(viewer), db: Session = Depends(get_db)):
    v = _get(db, vid)
    job = video_jobs.get(vid)
    return {"id": v.id, "status": v.status, "progress": v.progress, "error": v.error,
            "stats": job.stats if job else None, "has_result": v.result is not None}


@router.get("/{vid}/result")
def video_result(vid: int, _: User = Depends(viewer), db: Session = Depends(get_db)):
    v = _get(db, vid)
    if not v.result:
        raise HTTPException(409, "No result yet. Processing has not finished.")
    return {"video": _out(v), "result": v.result}


@router.get("/{vid}/preview")
def video_preview(vid: int, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    job = video_jobs.get(vid)
    if not job or not job.preview:
        raise HTTPException(404, "No live preview available.")
    return Response(job.preview, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/{vid}/frame")
def video_frame(vid: int, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    v = _get(db, vid)
    cap = cv2.VideoCapture(str(settings.upload_dir / v.stored_name))
    try:
        ok, frame = cap.read()
    finally:
        cap.release()
    if not ok:
        raise HTTPException(404, "Could not read a frame from this video.")
    return Response(encode_jpeg(frame, 1280, 80), media_type="image/jpeg")


@router.get("/{vid}/original")
def video_original(vid: int, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    v = _get(db, vid)
    p = safe_join(settings.upload_dir, v.stored_name)
    if not p or not p.exists():
        raise HTTPException(404, "The original file is no longer on disk.")
    mt = {".mp4": "video/mp4", ".mov": "video/quicktime", ".avi": "video/x-msvideo"}.get(p.suffix, "application/octet-stream")
    return FileResponse(p, media_type=mt, filename=v.original_name, content_disposition_type="inline")


@router.get("/{vid}/processed")
def video_processed(vid: int, download: bool = False, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    v = _get(db, vid)
    p = safe_join(settings.processed_dir, v.processed_name or "")
    if not v.processed_name or not p or not p.exists():
        raise HTTPException(404, "No processed video yet.")
    stem = Path(v.original_name).stem
    return FileResponse(p, media_type="video/mp4", filename=f"{stem}_annotated.mp4",
                        content_disposition_type="attachment" if download else "inline")


@router.delete("/{vid}", status_code=204)
def delete_video(vid: int, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    v = _get(db, vid)
    video_jobs.stop(vid)
    for name in db.scalars(select(Violation.evidence_name).where(Violation.video_id == vid)):
        if name:
            (settings.evidence_dir / name).unlink(missing_ok=True)
    (settings.upload_dir / v.stored_name).unlink(missing_ok=True)
    if v.processed_name:
        (settings.processed_dir / v.processed_name).unlink(missing_ok=True)
    label = v.original_name
    db.delete(v)
    db.commit()
    log_activity(db, user, "video_delete", label, request)
    return Response(status_code=204)
