"""Agent service — orchestrates LLM + tool calls for the agent chat.

Stub module so that route imports resolve. The full implementation is pending.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable

from sqlmodel import Session


class AgentService:
    """Orchestrates an agentic chat turn with tool calls and streaming."""

    def __init__(self, db: Session) -> None:
        self.db = db

    async def stream_turn(
        self,
        *,
        message: str,
        thread_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        lens: str | None = None,
        model: str | None = None,
        note_context: dict | None = None,
        is_disconnected: Callable[[], bool] | None = None,
    ) -> AsyncIterator[str]:
        """Stream SSE events for one agent turn. Stub yields done immediately."""
        yield "event: done\ndata: {}\n\n"
