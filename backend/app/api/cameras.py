from __future__ import annotations

import asyncio
import base64
import re
from pathlib import Path

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import _user_from_token, admin, current_user_media, operator, viewer
from app.core.config import settings
from app.core.database import SessionLocal, get_db
from app.cv.detector import ModelWeightsMissing, ensure_detector_ready
from app.models.entities import Camera, User
from app.schemas.cv_config import CameraCVConfig, default_cv_config
from app.schemas.schemas import CameraIn, CameraOut, MonitorStartIn
from app.services import stats
from app.services.common import log_activity, safe_join
from app.workers.live import encode_jpeg, monitor

router = APIRouter(tags=["cameras"])
VIDEO_EXT = {".mp4", ".avi", ".mov"}


def _validate_source(data: CameraIn) -> tuple[str, str]:
    st, src = data.source_type, data.source.strip()
    if st in ("browser", "none"):
        return st, ""
    if st == "webcam":
        if not re.fullmatch(r"\d{1,2}", src or "0"):
            raise HTTPException(422, "Webcam source must be a device index such as 0 or 1.")
        return st, src or "0"
    if st == "stream":
        if not re.match(r"^(rtsp|rtsps|http|https)://", src, re.I):
            raise HTTPException(422, "Stream URL must start with rtsp://, rtsps://, http:// or https://")
        return st, src
    if st == "file":
        if Path(src).suffix.lower() not in VIDEO_EXT or "/" in src or "\\" in src:
            raise HTTPException(422, "Choose a .mp4, .avi or .mov file from the sample_data folder.")
        p = safe_join(settings.sample_dir, src)
        if not p or not p.is_file():
            raise HTTPException(422, f"'{src}' was not found in the sample_data folder.")
        return st, src
    raise HTTPException(422, "Unknown source type.")


def _cfg(data: CameraIn) -> dict:
    if data.config is None:
        return default_cv_config()
    try:
        return CameraCVConfig(**data.config).model_dump(mode="json")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Invalid detection configuration: {e}") from e


def _out(db: Session, cams: list[Camera]) -> list[CameraOut]:
    dens = stats.latest_density_by_camera(db)
    outs = []
    for c in cams:
        o = CameraOut.model_validate(c)
        sess = monitor.get(c.id)
        o.monitoring = sess is not None
        if sess and sess.stats:
            o.density_level, o.density_ratio = sess.stats["density"]["level"], sess.stats["density"]["ratio"]
        elif c.id in dens:
            o.density_ratio, o.density_level = dens[c.id]
        if o.monitoring:
            o.status = "online"
        elif c.is_demo and c.status != "error":
            o.status = "demo"
        outs.append(o)
    return outs


@router.get("/api/cameras", response_model=list[CameraOut])
def list_cameras(_: User = Depends(viewer), db: Session = Depends(get_db)):
    return _out(db, list(db.scalars(select(Camera).order_by(Camera.id))))


@router.get("/api/sample-videos")
def sample_videos(_: User = Depends(viewer)):
    files = sorted(p.name for p in settings.sample_dir.glob("*") if p.suffix.lower() in VIDEO_EXT)
    return {"folder": str(settings.sample_dir), "files": files}


@router.post("/api/cameras", response_model=CameraOut, status_code=201)
def create_camera(data: CameraIn, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    if db.scalar(select(Camera).where(Camera.name == data.name.strip())):
        raise HTTPException(409, "A camera with this name already exists.")
    st, src = _validate_source(data)
    cam = Camera(name=data.name.strip(), location=data.location, latitude=data.latitude, longitude=data.longitude,
                 source_type=st, source=src, config=_cfg(data), status="offline", is_demo=False)
    db.add(cam)
    db.commit()
    log_activity(db, user, "camera_create", cam.name, request)
    return _out(db, [cam])[0]


@router.put("/api/cameras/{cam_id}", response_model=CameraOut)
def update_camera(cam_id: int, data: CameraIn, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    cam = db.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    dup = db.scalar(select(Camera).where(Camera.name == data.name.strip(), Camera.id != cam_id))
    if dup:
        raise HTTPException(409, "A camera with this name already exists.")
    st, src = _validate_source(data)
    cam.name, cam.location, cam.latitude, cam.longitude = data.name.strip(), data.location, data.latitude, data.longitude
    cam.source_type, cam.source = st, src
    if data.config is not None:
        cam.config = _cfg(data)
    if monitor.get(cam_id):
        monitor.stop(cam_id)  # configuration changed -> restart explicitly
    db.commit()
    log_activity(db, user, "camera_update", cam.name, request)
    return _out(db, [cam])[0]


@router.delete("/api/cameras/{cam_id}", status_code=204)
def delete_camera(cam_id: int, request: Request, user: User = Depends(admin), db: Session = Depends(get_db)):
    cam = db.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    monitor.stop(cam_id)
    name = cam.name
    db.delete(cam)
    db.commit()
    log_activity(db, user, "camera_delete", name, request)
    return Response(status_code=204)


@router.get("/api/cameras/{cam_id}/snapshot")
def camera_snapshot(cam_id: int, _: User = Depends(current_user_media), db: Session = Depends(get_db)):
    """A still frame used as the background of the zone / line editor."""
    cam = db.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    sess = monitor.get(cam_id)
    if sess and sess.latest_jpeg:
        return Response(sess.latest_jpeg, media_type="image/jpeg")
    if cam.source_type == "file":
        p = safe_join(settings.sample_dir, cam.source)
        cap = cv2.VideoCapture(str(p)) if p else None
        if cap is not None and cap.isOpened():
            ok, frame = cap.read()
            cap.release()
            if ok:
                return Response(encode_jpeg(frame, 1280, 80), media_type="image/jpeg")
    raise HTTPException(404, "No frame available. Start monitoring this camera or pick an uploaded video as the background.")


# ----------------------------------------------------------------- monitoring
@router.post("/api/monitoring/start")
def monitoring_start(data: MonitorStartIn, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    cam = db.get(Camera, data.camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    try:
        ensure_detector_ready()
        sess = monitor.start(cam)
    except ModelWeightsMissing as e:
        raise HTTPException(503, str(e)) from e
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    log_activity(db, user, "monitoring_start", cam.name, request)
    return {"camera_id": cam.id, "mode": "browser" if cam.source_type == "browser" else "server",
            "source_type": cam.source_type, "stream_url": f"/api/monitoring/stream/{cam.id}", "started": True}


@router.post("/api/monitoring/stop")
def monitoring_stop(data: MonitorStartIn, request: Request, user: User = Depends(operator), db: Session = Depends(get_db)):
    cam = db.get(Camera, data.camera_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    stopped = monitor.stop(cam.id)
    log_activity(db, user, "monitoring_stop", cam.name, request)
    return {"camera_id": cam.id, "stopped": stopped}


@router.get("/api/monitoring/status")
def monitoring_status(_: User = Depends(viewer), db: Session = Depends(get_db)):
    out = []
    for cid in monitor.active_ids():
        s = monitor.get(cid)
        if s:
            out.append({"camera_id": cid, "camera_name": s.name, "source_type": s.source_type, "stats": s.stats,
                        "fps": round(s.fps_measured, 1), "started_at": s.started_at.isoformat() + "Z"})
    return out


@router.get("/api/monitoring/{cam_id}/state")
def monitoring_state(cam_id: int, _: User = Depends(viewer), db: Session = Depends(get_db)):
    cam = db.get(Camera, cam_id)
    if not cam:
        raise HTTPException(404, "Camera not found.")
    s = monitor.get(cam_id)
    return {"camera_id": cam_id, "active": s is not None, "status": "online" if s else cam.status, "error": cam.last_error,
            "stats": s.stats if s else None, "fps": round(s.fps_measured, 1) if s else 0}


@router.get("/api/monitoring/stream/{cam_id}")
async def monitoring_stream(cam_id: int, request: Request, token: str | None = None):
    """MJPEG stream of the annotated frames (token via query string because <img> cannot send headers)."""
    with SessionLocal() as db:
        _user_from_token(db, token)
    if not monitor.get(cam_id):
        raise HTTPException(404, "This camera is not being monitored. Press Start first.")

    async def gen():
        last = None
        while True:
            if await request.is_disconnected():
                break
            s = monitor.get(cam_id)
            if not s:
                break
            jpg = s.latest_jpeg
            if jpg is not None and jpg is not last:
                last = jpg
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(jpg)).encode() + b"\r\n\r\n" + jpg + b"\r\n"
            await asyncio.sleep(0.04)

    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame",
                             headers={"Cache-Control": "no-store"})


@router.websocket("/ws/webcam")
async def ws_browser_webcam(ws: WebSocket, camera_id: int, token: str | None = None):
    """Browser webcam: the client sends JPEG frames, the server answers with the annotated frame + stats."""
    with SessionLocal() as db:
        try:
            user = _user_from_token(db, token)
        except HTTPException:
            await ws.close(code=4401)
            return
        if user.role not in ("operator", "admin"):
            await ws.close(code=4403)
            return
    sess = monitor.get(camera_id)
    await ws.accept()
    if not sess or sess.source_type != "browser":
        await ws.send_json({"type": "error", "message": "Press Start on a 'Browser webcam' camera first."})
        await ws.close()
        return
    loop = asyncio.get_running_loop()
    try:
        while True:
            data = await ws.receive_bytes()
            frame = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
            if frame is None:
                await ws.send_json({"type": "error", "message": "Could not decode frame."})
                continue
            try:
                ann, st = await loop.run_in_executor(None, sess.process, frame)
            except ModelWeightsMissing as e:
                await ws.send_json({"type": "error", "message": str(e)})
                break
            img = await loop.run_in_executor(None, encode_jpeg, ann, 960, 70)
            await ws.send_json({"type": "frame", "stats": st, "image": base64.b64encode(img).decode(), "fps": round(sess.fps_measured, 1)})
    except WebSocketDisconnect:
        pass
    finally:
        # a closed browser tab ends the session so the camera never stays 'online' by mistake
        if monitor.get(camera_id) is sess:
            monitor.stop(camera_id)
