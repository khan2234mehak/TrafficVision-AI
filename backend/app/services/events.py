"""WebSocket fan-out hub. Worker threads publish thread-safely; the event loop does the sending."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

log = logging.getLogger(__name__)


class EventHub:
    def __init__(self) -> None:
        self.channels: dict[str, set[WebSocket]] = defaultdict(set)
        self.loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop

    async def connect(self, channel: str, ws: WebSocket) -> None:
        await ws.accept()
        self.channels[channel].add(ws)

    def disconnect(self, channel: str, ws: WebSocket) -> None:
        self.channels[channel].discard(ws)

    def connection_count(self) -> int:
        return sum(len(v) for v in self.channels.values())

    async def _broadcast(self, channel: str, payload: dict) -> None:
        dead = []
        for ws in list(self.channels[channel]):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)

    def publish(self, channel: str, payload: dict) -> None:
        """Safe to call from any thread."""
        if not self.loop or not self.channels[channel]:
            return
        try:
            asyncio.run_coroutine_threadsafe(self._broadcast(channel, payload), self.loop)
        except RuntimeError:  # loop closed during shutdown
            log.debug("event loop closed, dropping event")


hub = EventHub()
