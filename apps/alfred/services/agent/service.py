"""Agent service — OpenAI-powered streaming agent with tool calls.

Flat tool-calling loop modeled after Claude Code's architecture:
the LLM sees all available tools and decides what to call.

Yields structured tuples so the caller (routes.py) can both
forward SSE to the client AND collect data for DB persistence.

┌─────────────────────────────────────────────────────────┐
│  AGENT LOOP (flat, Claude Code-style)                   │
│                                                          │
│  1. Build messages (system + history + user)             │
│  2. Stream tokens from model → yield each to caller     │
│  3. If model requests tool calls:                        │
│     a. Yield tool_start events                           │
│     b. Execute tools (with timeout + sanitization)       │
│     c. Yield tool_result events                          │
│     d. Inject results back into messages                 │
│     e. LOOP to step 2                                    │
│  4. If no tool calls → DONE                              │
│  5. Max iterations guard                                 │
└─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

from openai import APIError, APITimeoutError, AsyncOpenAI, BadRequestError, RateLimitError
from sqlmodel import Session

from alfred.core.settings import settings
from alfred.services.agent.prompts import SystemPromptBuilder
from alfred.services.agent.tools import execute_tool, get_all_tool_schemas

logger = logging.getLogger(__name__)

# Max tool-call rounds per turn to prevent infinite loops.
MAX_TOOL_ROUNDS = 10

# Default timeout per tool (seconds).
DEFAULT_TOOL_TIMEOUT = 30

# Timeouts (seconds) per tool type.
_TOOL_TIMEOUTS: dict[str, int] = {
    "search_kb": 30,
    "get_zettel": 30,
    "create_zettel": 60,
    "update_zettel": 60,
    "deep_research": 120,
    "firecrawl_scrape": 30,
}

# Models that use reasoning (o-series).
_REASONING_MODELS = {"o3", "o3-mini", "o4-mini"}

# Models that require max_completion_tokens instead of max_tokens.
_MAX_COMPLETION_TOKEN_PREFIXES = ("gpt-5",)

# Regex for stripping HTML tags from tool results (prompt injection mitigation).
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _sse_event(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _sanitize_tool_result(text: str) -> str:
    """Strip HTML tags from tool results to mitigate prompt injection."""
    return _HTML_TAG_RE.sub("", text)


# Singleton prompt builder
_prompt_builder = SystemPromptBuilder()


def _is_reasoning_model(model: str) -> bool:
    """Check if a model is an o-series reasoning model."""
    return any(model.startswith(p) for p in _REASONING_MODELS)


def _uses_max_completion_tokens(model: str) -> bool:
    """Check if a model requires max_completion_tokens parameter."""
    return any(model.startswith(p) for p in _MAX_COMPLETION_TOKEN_PREFIXES) or _is_reasoning_model(
        model
    )


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
    ) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        """Stream events for one agent turn as structured tuples.

        Yields (event_name, data_dict, sse_string) so the caller can:
        - Forward sse_string to the client
        - Inspect data_dict to collect content for DB persistence
        """
        model_name = model or settings.llm_model or "gpt-5.4"
        effective_max = max_iterations if max_iterations else MAX_TOOL_ROUNDS

        try:
            messages: list[dict[str, Any]] = [
                {
                    "role": "system",
                    "content": _prompt_builder.build(
                        lens=lens, note_context=note_context
                    ),
                },
            ]

            if history:
                for msg in history:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role in ("user", "assistant", "system"):
                        messages.append({"role": role, "content": content})

            messages.append({"role": "user", "content": message})

            # Flat agent loop: stream → tools → re-stream → done
            all_tool_calls: list[dict[str, Any]] = []
            all_artifacts: list[dict[str, Any]] = []
            all_reasoning: list[str] = []

            for _round in range(effective_max):
                if is_disconnected and await is_disconnected():
                    return

                # Stream tokens in real-time, collect tool calls
                content_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []

                kwargs = self._build_api_kwargs(model_name, messages)

                for attempt in range(3):  # 2 retries with backoff
                    try:
                        async for event in self._stream_tokens(kwargs, is_disconnected):
                            if event["type"] == "token":
                                content_parts.append(event["content"])
                                data = {"content": event["content"]}
                                yield ("token", data, _sse_event("token", data))
                            elif event["type"] == "reasoning":
                                all_reasoning.append(event["content"])
                                data = {"content": event["content"]}
                                yield ("reasoning", data, _sse_event("reasoning", data))
                            elif event["type"] == "tool_calls":
                                tool_calls = event["tool_calls"]
                        break  # Success, exit retry loop
                    except (APITimeoutError, APIError) as exc:
                        if attempt < 2 and not isinstance(exc, BadRequestError):
                            wait = (2 if isinstance(exc, RateLimitError) else 1) * (attempt + 1)
                            logger.warning("%s (attempt %d), retrying in %ds...", type(exc).__name__, attempt + 1, wait)
                            await asyncio.sleep(wait)
                            continue
                        raise
                    except RateLimitError:
                        if attempt < 2:
                            logger.warning("Rate limit (attempt %d), backing off...", attempt + 1)
                            await asyncio.sleep(2 * (attempt + 1))
                            continue
                        raise

                response_content = "".join(content_parts)

                # No tool calls → done
                if not tool_calls:
                    break

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

                # Execute tool calls and inject results
                for tc in tool_calls:
                    call_id = tc["call_id"]
                    tool_name = tc["name"]
                    tool_args = tc["args"]

                    ts_data = {"call_id": call_id, "tool": tool_name, "args": tool_args}
                    yield ("tool_start", ts_data, _sse_event("tool_start", ts_data))

                    timeout = _TOOL_TIMEOUTS.get(tool_name, DEFAULT_TOOL_TIMEOUT)
                    try:
                        result = await asyncio.wait_for(
                            execute_tool(tool_name, tool_args, self.db),
                            timeout=timeout,
                        )
                    except TimeoutError:
                        result = {"error": f"Tool {tool_name} timed out after {timeout}s"}
                    except Exception as exc:
                        result = {"error": f"Tool {tool_name} failed: {exc!s}"}

                    tr_data = {"call_id": call_id, "result": result}
                    all_tool_calls.append({"tool": tool_name, "args": tool_args, **tr_data})
                    yield ("tool_result", tr_data, _sse_event("tool_result", tr_data))

                    # Emit artifact for zettel CRUD results
                    if isinstance(result, dict) and result.get("action") in (
                        "created",
                        "found",
                        "updated",
                    ):
                        artifact_data = {
                            "type": "zettel",
                            "action": result["action"],
                            "zettel": {
                                "id": result.get("zettel_id"),
                                "title": result.get("title", ""),
                                "summary": result.get("summary", ""),
                                "topic": result.get("topic", ""),
                                "tags": result.get("tags", []),
                            },
                        }
                        all_artifacts.append(artifact_data)
                        yield ("artifact", artifact_data, _sse_event("artifact", artifact_data))

                    # Sanitize tool result before injecting back into messages
                    result_str = json.dumps(result)
                    result_str = _sanitize_tool_result(result_str)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": result_str,
                        }
                    )

        except BadRequestError as exc:
            logger.error("Bad request to OpenAI: %s", exc)
            err_data = {"message": f"Invalid request: {exc!s}"}
            yield ("error", err_data, _sse_event("error", err_data))
        except Exception as exc:
            logger.exception("Agent stream_turn failed: %s", exc)
            err_data = {"message": f"Agent error: {exc!s}"}
            yield ("error", err_data, _sse_event("error", err_data))

        done_data = {
            "thread_id": str(thread_id or ""),
            "reasoning": "".join(all_reasoning) if all_reasoning else None,
            "tool_calls": all_tool_calls or None,
            "artifacts": all_artifacts or None,
        }
        yield ("done", done_data, _sse_event("done", {"thread_id": str(thread_id or "")}))

    async def _stream_tokens(
        self,
        kwargs: dict[str, Any],
        is_disconnected: Callable[[], Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream individual tokens and tool calls from OpenAI.

        Yields events as they arrive:
        - {"type": "token", "content": "..."} for each text chunk
        - {"type": "reasoning", "content": "..."} for reasoning traces
        - {"type": "tool_calls", "tool_calls": [...]} at the end if tools were requested
        """
        tool_calls_by_index: dict[int, dict[str, Any]] = {}

        stream = await self.client.chat.completions.create(**kwargs)

        async for chunk in stream:
            if is_disconnected and await is_disconnected():
                break

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            # Stream reasoning tokens (o3/o4 models)
            reasoning_content = getattr(delta, "reasoning", None) or getattr(
                delta, "reasoning_content", None
            )
            if reasoning_content:
                yield {"type": "reasoning", "content": reasoning_content}

            # Stream content tokens in real-time
            if delta.content:
                yield {"type": "token", "content": delta.content}

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

        # Parse and yield collected tool calls at the end
        if tool_calls_by_index:
            tool_calls: list[dict[str, Any]] = []
            for idx in sorted(tool_calls_by_index.keys()):
                entry = tool_calls_by_index[idx]
                try:
                    args = json.loads(entry["args_json"]) if entry["args_json"] else {}
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    {
                        "call_id": entry["call_id"],
                        "name": entry["name"],
                        "args": args,
                    }
                )
            yield {"type": "tool_calls", "tool_calls": tool_calls}

    def _build_api_kwargs(self, model: str, messages: list[dict[str, Any]]) -> dict[str, Any]:
        """Build the kwargs dict for the OpenAI chat completion call."""
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "tools": get_all_tool_schemas(),
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

    # _stream_tokens replaces the old _stream_response — tokens yield in real-time
    # instead of being collected then returned as a batch.
