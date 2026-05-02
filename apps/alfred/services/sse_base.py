"""Shared plumbing for Server-Sent Events streaming orchestrators.

Provides the common mechanics used by streaming services so individual
orchestrators can focus on their domain logic:

- SSE event formatting
- Client-disconnect detection (D5 from the design plan)
- Stale-request idempotency check (D5) — subclasses supply the key
- OpenAI streaming with reasoning-token pass-through
- Structured JSON response parser with markdown-fence stripping

Subclasses implement ``async def run()`` returning an ``AsyncGenerator[str, None]``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Any

from fastapi import Request
from sqlmodel import Session

from alfred.api.dependencies import get_db_session

log = logging.getLogger(__name__)


class SSEStreamOrchestrator:
    """Base class for Server-Sent Events orchestrators with shared plumbing.

    Provides:
    - SSE event formatting
    - Client-disconnect detection (D5 from the design plan)
    - Stale-request idempotency check (D5) — subclasses supply the key
    - OpenAI streaming with reasoning-token pass-through
    - Structured JSON response parser with markdown-fence stripping

    Subclasses implement:
    - async def run() -> AsyncGenerator[str, None]

    Data flow for a typical subclass:
        1. Set up idempotency key (e.g., (card_id, word_count))
        2. Stream OpenAI response via _run_openai_stream_with_reasoning
        3. Parse JSON via _parse_structured_json, yielding one SSE event per top-level key

    The base class's __init__ captures:
        request: fastapi.Request (for disconnect detection)
        db_session_factory: optional factory; defaults to alfred's get_db_session
    """

    def __init__(
        self,
        request: Request | None = None,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self._request = request
        self._uses_default_factory = db_session_factory is None
        if self._uses_default_factory:
            self._db_factory: Callable[[], Session] = self._default_session_factory
        else:
            self._db_factory = db_session_factory

    @staticmethod
    def _default_session_factory() -> Session:
        """Create and return a fresh DB session. Caller closes it."""
        return next(get_db_session())

    @staticmethod
    def _sse(event: str, data: dict[str, Any]) -> str:
        """Format a single SSE event."""
        return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"

    async def _is_disconnected_or_stale(
        self,
        is_stale: Callable[[], bool] | None = None,
    ) -> bool:
        """D5: Check client disconnect + idempotency staleness.

        Returns True when the stream should abort:
        - client has disconnected (FastAPI Request.is_disconnected())
        - OR caller-supplied is_stale() returns True (a newer request has
          superseded this one)

        Safe to call when self._request is None (e.g., in tests) — returns False.
        Exceptions from either check are swallowed and logged at debug level so
        that an intermittent transport hiccup does not tear down a live stream.
        """
        if self._request is not None:
            try:
                if await self._request.is_disconnected():
                    return True
            except Exception:
                log.debug("is_disconnected check failed", exc_info=True)
        if is_stale is not None:
            try:
                if is_stale():
                    return True
            except Exception:
                log.debug("is_stale check failed", exc_info=True)
        return False

    async def _run_openai_stream_with_reasoning(
        self,
        *,
        messages: list[dict[str, str]],
        model: str,
        max_completion_tokens: int = 4096,
        is_stale: Callable[[], bool] | None = None,
    ) -> AsyncGenerator[tuple[str, str], None]:
        """Yield (kind, content) tuples as the OpenAI stream produces them.

        kind is one of: "thinking" (reasoning tokens from o3/o4 models),
                        "completion" (normal response tokens).

        Aborts immediately if disconnected-or-stale at any chunk boundary.

        NOTE: callers of this method are responsible for assembling the
        completion buffer (by concatenating all "completion" values) and
        passing it to _parse_structured_json afterwards. This method does
        not parse; it only emits per-chunk events.
        """
        from alfred.core.llm_factory import get_async_openai_client

        client = get_async_openai_client()
        stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True,
            max_completion_tokens=max_completion_tokens,
        )

        async for chunk in stream:
            if await self._is_disconnected_or_stale(is_stale):
                return
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta

            reasoning = getattr(delta, "reasoning", None) or getattr(
                delta, "reasoning_content", None
            )
            if reasoning:
                yield ("thinking", reasoning)
                continue

            if delta.content:
                yield ("completion", delta.content)

    @staticmethod
    def _parse_structured_json(buffer: str) -> dict[str, Any] | None:
        """Parse a JSON response buffer, stripping markdown fences if present.

        Returns the parsed dict, or None if parsing fails. Callers handle
        the None case (typically by emitting an error SSE event).
        """
        if not buffer:
            return None
        cleaned = buffer.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = "\n".join(cleaned.split("\n")[:-1])
        cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            log.warning("SSE JSON parse failed: %s", exc)
            return None

    async def run(self) -> AsyncGenerator[str, None]:
        """Subclasses must implement this."""
        raise NotImplementedError
        yield  # unreachable, makes the signature an async generator
