"""Realtime hub for system design sessions.

This is a lightweight in-memory WebSocket broadcaster intended for a single
process deployment (or as a fallback when no pub/sub layer is configured).
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class SystemDesignRealtimeHub:
    """Tracks WebSocket connections and broadcasts session updates."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[session_id].add(websocket)

    async def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            connections = self._connections.get(session_id)
            if not connections:
                return
            connections.discard(websocket)
            if not connections:
                self._connections.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict) -> None:  # noqa: ANN401
        async with self._lock:
            targets = list(self._connections.get(session_id, set()))

        if not targets:
            return

        disconnected: list[WebSocket] = []
        for ws in targets:
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)

        if disconnected:
            async with self._lock:
                live = self._connections.get(session_id)
                if not live:
                    return
                for ws in disconnected:
                    live.discard(ws)
                if not live:
                    self._connections.pop(session_id, None)
