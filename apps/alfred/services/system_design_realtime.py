from __future__ import annotations

from collections import defaultdict
from typing import Any, DefaultDict, Set

from fastapi import WebSocket


class SystemDesignRealtimeHub:
    def __init__(self) -> None:
        self._sessions: DefaultDict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._sessions[session_id].add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        self._sessions[session_id].discard(websocket)
        if not self._sessions[session_id]:
            self._sessions.pop(session_id, None)

    async def broadcast(self, session_id: str, payload: dict[str, Any]) -> None:
        for websocket in list(self._sessions.get(session_id, set())):
            await websocket.send_json(payload)
