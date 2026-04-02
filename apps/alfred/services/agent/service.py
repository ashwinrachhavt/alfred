"""Agent service — OpenAI-powered streaming agent with tool calls.

Streams SSE events for the agent chat endpoint. Uses AsyncOpenAI directly
for streaming with function calling, tool dispatch, and reasoning extraction.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from openai import AsyncOpenAI, APITimeoutError, RateLimitError
from sqlmodel import Session

from alfred.core.settings import settings
from alfred.services.agent.tools import TOOL_SCHEMAS, execute_tool

logger = logging.getLogger(__name__)

# Max tool-call rounds per turn to prevent infinite loops.
MAX_TOOL_ROUNDS = 5

# Timeouts (seconds) per tool type.
_TOOL_TIMEOUTS: dict[str, int] = {
    "search_kb": 30,
    "get_zettel": 30,
    "create_zettel": 60,
    "update_zettel": 60,
}

# Models that use reasoning (o-series).
_REASONING_MODELS = {"o3", "o3-mini", "o4-mini"}

# Models that require max_completion_tokens instead of max_tokens.
_MAX_COMPLETION_TOKEN_PREFIXES = ("gpt-5",)


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _build_system_prompt(
    lens: str | None = None,
    note_context: dict | None = None,
) -> str:
    """Build a system prompt for the agent."""
    parts = [
        "You are Alfred, a knowledge assistant that helps users ingest, decompose, "
        "connect, and capitalize on what they know. You have access to a knowledge base "
        "of zettels (atomic knowledge cards). Use the available tools to search, create, "
        "retrieve, and update knowledge cards when relevant.",
        "",
        "Guidelines:",
        "- Be concise and substantive. Avoid filler.",
        "- When the user asks about their knowledge, search first before answering.",
        "- When creating zettels, use clear titles and well-structured markdown content.",
        "- Surface connections between ideas when you notice them.",
    ]

    if lens:
        parts.append("")
        parts.append(
            f"The user has selected the '{lens}' lens. Adapt your tone and analytical "
            f"approach accordingly (e.g., more {lens} framing, terminology, and depth)."
        )

    if note_context:
        title = note_context.get("title", "Untitled")
        preview = note_context.get("content_preview", "")
        parts.append("")
        parts.append(f"Context: The user is currently viewing the note '{title}'.")
        if preview:
            parts.append(f"Note preview: {preview[:500]}")

    # Check for new knowledge notifications
    try:
        from alfred.services.knowledge_notifications import get_pending_notifications

        notifications = get_pending_notifications(limit=3)
        if notifications:
            parts.append("")
            parts.append("New knowledge arrived since your last conversation:")
            for n in notifications:
                linked_count = len(n.get("linked_to", [])) or n.get("linked_to_count", 0)
                line = f"- '{n['zettel_title']}'"
                if linked_count:
                    line += f" (linked to {linked_count} existing cards)"
                source = n.get("source_document")
                if source:
                    line += f" from '{source}'"
                parts.append(line)
            parts.append(
                "Mention these if relevant to the user's question. "
                "You can use search_kb to find more details."
            )
    except Exception:
        pass  # Never block prompt building on notification failures

    return "\n".join(parts)


def _is_reasoning_model(model: str) -> bool:
    """Check if a model is an o-series reasoning model."""
    return any(model.startswith(p) for p in _REASONING_MODELS)


def _uses_max_completion_tokens(model: str) -> bool:
    """Check if a model requires max_completion_tokens parameter."""
    return any(model.startswith(p) for p in _MAX_COMPLETION_TOKEN_PREFIXES) or _is_reasoning_model(model)


def _make_client() -> AsyncOpenAI:
    """Create an AsyncOpenAI client from settings."""
    kwargs: dict[str, object] = {}
    if settings.openai_api_key:
        val = settings.openai_api_key.get_secret_value()
        if val:
            kwargs["api_key"] = val
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    if settings.openai_organization:
        kwargs["organization"] = settings.openai_organization
    return AsyncOpenAI(**kwargs)


class AgentService:
    """Orchestrates an agentic chat turn with tool calls and streaming."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = _make_client()
        return self._client

    async def stream_turn(
        self,
        *,
        message: str,
        thread_id: int | None = None,
        history: list[dict[str, str]] | None = None,
        lens: str | None = None,
        model: str | None = None,
        note_context: dict | None = None,
        is_disconnected: Callable[[], Any] | None = None,
        intent: str | None = None,
        intent_args: dict | None = None,
        max_iterations: int = 10,
    ) -> AsyncIterator[str]:
        """Stream SSE events for one agent turn.

        Calls OpenAI with function calling, dispatches tool calls,
        re-injects results, and streams tokens back as SSE events.
        """
        model_name = model or settings.llm_model or "gpt-4.1-mini"

        try:
            # Build conversation messages
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": _build_system_prompt(lens, note_context)},
            ]

            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant", "system"):
                        messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": message})

            # Tool loop: call OpenAI, dispatch tools, re-inject, repeat
            for _round in range(MAX_TOOL_ROUNDS):
                if is_disconnected and await is_disconnected():
                    return

                response_content, tool_calls, reasoning = await self._call_openai_streaming(
                    messages=messages,
                    model=model_name,
                    is_disconnected=is_disconnected,
                )

                # Yield reasoning if present (o3/o4 models)
                if reasoning:
                    yield _sse_event("reasoning", {"content": reasoning})

                # Yield accumulated content as a single token event
                if response_content:
                    yield _sse_event("token", {"content": response_content})

                # No tool calls means we're done
                if not tool_calls:
                    break

                # Process tool calls
                # Add assistant message with tool_calls to conversation
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": response_content or None,
                    "tool_calls": [
                        {
                            "id": tc["call_id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["args"]),
                            },
                        }
                        for tc in tool_calls
                    ],
                }
                messages.append(assistant_msg)

                for tc in tool_calls:
                    call_id = tc["call_id"]
                    tool_name = tc["name"]
                    tool_args = tc["args"]

                    yield _sse_event("tool_start", {
                        "call_id": call_id,
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    # Execute tool with timeout
                    timeout = _TOOL_TIMEOUTS.get(tool_name, 30)
                    try:
                        result = await asyncio.wait_for(
                            execute_tool(tool_name, tool_args, self.db),
                            timeout=timeout,
                        )
                    except asyncio.TimeoutError:
                        result = {"error": f"Tool {tool_name} timed out after {timeout}s"}
                    except Exception as exc:
                        result = {"error": f"Tool {tool_name} failed: {exc!s}"}

                    yield _sse_event("tool_result", {
                        "call_id": call_id,
                        "result": result,
                    })

                    # Emit artifact event for zettel CRUD results
                    if isinstance(result, dict) and result.get("action") in ("created", "found", "updated"):
                        yield _sse_event("artifact", {
                            "type": "zettel",
                            "action": result["action"],
                            "zettel": {
                                "id": result.get("zettel_id"),
                                "title": result.get("title", ""),
                                "summary": result.get("summary", ""),
                                "topic": result.get("topic", ""),
                                "tags": result.get("tags", []),
                            },
                        })

                    # Inject tool result back into conversation for next round
                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result),
                    })

        except Exception as exc:
            logger.exception("Agent stream_turn failed: %s", exc)
            yield _sse_event("error", {"message": f"Agent error: {exc!s}"})

        yield _sse_event("done", {"thread_id": str(thread_id or "")})

    async def _call_openai_streaming(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        is_disconnected: Callable[[], Any] | None = None,
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        """Call OpenAI with streaming and return (content, tool_calls, reasoning).

        Handles retry on timeout and rate limit. Collects streamed deltas
        into complete content and tool_call objects.
        """
        kwargs = self._build_api_kwargs(model, messages)

        for attempt in range(2):  # 1 retry
            try:
                return await self._stream_response(kwargs, model, is_disconnected)
            except APITimeoutError:
                if attempt == 0:
                    logger.warning("OpenAI timeout on attempt 1, retrying...")
                    continue
                raise
            except RateLimitError:
                if attempt == 0:
                    logger.warning("OpenAI rate limit hit, waiting 2s and retrying...")
                    await asyncio.sleep(2)
                    continue
                raise

        # Should not reach here, but satisfy type checker
        return "", [], None  # pragma: no cover

    def _build_api_kwargs(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Build the kwargs dict for the OpenAI chat completion call."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": TOOL_SCHEMAS,
            "stream": True,
            "timeout": 60,
        }

        # Token limit parameter depends on model
        if _uses_max_completion_tokens(model):
            kwargs["max_completion_tokens"] = 4096
        else:
            kwargs["max_tokens"] = 4096

        # Reasoning models don't support temperature
        if not _is_reasoning_model(model):
            kwargs["temperature"] = settings.llm_temperature

        return kwargs

    async def _stream_response(
        self,
        kwargs: dict[str, Any],
        model: str,
        is_disconnected: Callable[[], Any] | None = None,
    ) -> tuple[str, list[dict[str, Any]], str | None]:
        """Stream a single OpenAI response and collect results.

        Returns (content, tool_calls, reasoning).
        """
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        tool_calls_by_index: dict[int, dict[str, Any]] = {}

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if is_disconnected and await is_disconnected():
                break

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Collect reasoning content (o3/o4 models)
            # OpenAI returns reasoning in a `reasoning` field on the delta
            reasoning_content = getattr(delta, "reasoning", None) or getattr(delta, "reasoning_content", None)
            if reasoning_content:
                reasoning_parts.append(reasoning_content)

            # Collect regular content
            if delta.content:
                content_parts.append(delta.content)

            # Collect tool calls (streamed incrementally)
            if delta.tool_calls:
                for tc_delta in delta.tool_calls:
                    idx = tc_delta.index
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "call_id": tc_delta.id or f"call_{uuid.uuid4().hex[:8]}",
                            "name": "",
                            "args_json": "",
                        }
                    entry = tool_calls_by_index[idx]
                    if tc_delta.id:
                        entry["call_id"] = tc_delta.id
                    if tc_delta.function:
                        if tc_delta.function.name:
                            entry["name"] = tc_delta.function.name
                        if tc_delta.function.arguments:
                            entry["args_json"] += tc_delta.function.arguments

        # Parse collected tool calls
        tool_calls: list[dict[str, Any]] = []
        for idx in sorted(tool_calls_by_index.keys()):
            entry = tool_calls_by_index[idx]
            try:
                args = json.loads(entry["args_json"]) if entry["args_json"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({
                "call_id": entry["call_id"],
                "name": entry["name"],
                "args": args,
            })

        content = "".join(content_parts)
        reasoning = "".join(reasoning_parts) or None

        return content, tool_calls, reasoning
