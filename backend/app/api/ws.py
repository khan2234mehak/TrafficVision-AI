from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.deps import _user_from_token
from app.core.database import SessionLocal
from app.services.events import hub
from fastapi import HTTPException

router = APIRouter()


async def _serve(ws: WebSocket, channel: str, token: str | None) -> None:
    with SessionLocal() as db:
        try:
            _user_from_token(db, token)
        except HTTPException:
            await ws.close(code=4401)
            return
    await hub.connect(channel, ws)
    try:
        await ws.send_json({"type": "hello", "channel": channel})
        while True:
            await ws.receive_text()  # clients send 'ping' keep-alives
    except WebSocketDisconnect:
        pass
    finally:
        hub.disconnect(channel, ws)


@router.websocket("/ws/traffic")
async def ws_traffic(ws: WebSocket, token: str | None = None):
    await _serve(ws, "traffic", token)


@router.websocket("/ws/alerts")
async def ws_alerts(ws: WebSocket, token: str | None = None):
    await _serve(ws, "alerts", token)
