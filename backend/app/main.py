from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import update

from app.api import analytics, auth, cameras, reports, system, videos, violations, ws
from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.core.logging import setup_logging
from app.models.entities import Camera, VideoUpload
from app.services.events import hub
from app.services.seed import ensure_seed, seed_users
from app.workers.live import monitor
from app.workers.video_worker import video_jobs

log = logging.getLogger("trafficvision")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.debug)
    settings.resolve_secret()  # fail fast in production when SECRET_KEY is missing
    settings.ensure_dirs()
    init_db()
    hub.bind_loop(asyncio.get_running_loop())
    with SessionLocal() as db:
        # nothing can be running right after a restart
        db.execute(update(Camera).values(status="offline"))
        db.execute(update(VideoUpload).where(VideoUpload.status.in_(("queued", "processing", "paused")))
                   .values(status="failed", error="Interrupted by a server restart. Process the video again."))
        db.commit()
        ensure_seed(db)
        if not settings.seed_demo_data and settings.environment != "production":
            seed_users(db)
    log.info("%s started (%s, db=%s)", settings.app_name, settings.environment, "sqlite" if settings.is_sqlite else "postgres")
    yield
    monitor.stop_all()
    video_jobs.shutdown()


app = FastAPI(title=settings.app_name, version="1.0.0", lifespan=lifespan,
              description="Smart traffic monitoring: YOLO detection, ByteTrack tracking, counting, density and violations.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Unexpected server error. Check the backend log for details."}, status_code=500)


for r in (auth.router, system.router, cameras.router, videos.router, violations.router, analytics.router, reports.router, ws.router):
    app.include_router(r)

# Optional: serve the built frontend (used by the Docker image). Not used during `npm run dev`.
_dist = Path(settings.data_dir.parent.parent / "frontend" / "dist")
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        if full_path.startswith(("api/", "ws/")):
            return JSONResponse({"detail": "Not found"}, status_code=404)
        f = (_dist / full_path).resolve()
        if full_path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
