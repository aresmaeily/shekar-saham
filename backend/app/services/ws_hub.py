"""هاب WebSocket برای پوش لحظه‌ای به کلاینت‌ها."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any
from fastapi import WebSocket

logger = logging.getLogger("shekar.ws")


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()
        self.total_connections = 0
        self.messages_sent = 0
        self.last_broadcast_ts: float = 0.0

    @property
    def count(self) -> int:
        return len(self._clients)

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)
            self.total_connections += 1
        await self.send_one(
            ws,
            {
                "type": "hello",
                "ts": time.time(),
                "message": "connected to shekar-saham live feed",
                "clients": self.count,
            },
        )

    async def disconnect(self, ws: WebSocket) -> None:
        async with self._lock:
            self._clients.discard(ws)

    async def send_one(self, ws: WebSocket, payload: dict[str, Any]) -> None:
        try:
            await ws.send_text(json.dumps(payload, ensure_ascii=False, default=str))
            self.messages_sent += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug("send_one failed: %s", exc)
            await self.disconnect(ws)

    async def broadcast(self, payload: dict[str, Any]) -> int:
        payload = {**payload, "ts": payload.get("ts") or time.time()}
        text = json.dumps(payload, ensure_ascii=False, default=str)
        async with self._lock:
            clients = list(self._clients)
        dead: list[WebSocket] = []
        sent = 0
        for ws in clients:
            try:
                await ws.send_text(text)
                sent += 1
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)
        self.messages_sent += sent
        self.last_broadcast_ts = time.time()
        return sent

    def status(self) -> dict[str, Any]:
        return {
            "clients": self.count,
            "total_connections": self.total_connections,
            "messages_sent": self.messages_sent,
            "last_broadcast_ts": self.last_broadcast_ts,
        }


ws_hub = ConnectionManager()
