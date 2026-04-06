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

from openai import APITimeoutError, AsyncOpenAI, RateLimitError
from sqlmodel import Session

from alfred.core.settings import settings
from alfred.services.agent.tools import execute_tool, get_all_tool_schemas

logger = logging.getLogger(__name__)

# Max tool-call rounds per turn to prevent infinite loops.
MAX_TOOL_ROUNDS = 10

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


_BASE_SYSTEM_PROMPT = """You are Alfred, a personal knowledge engine. You help the user ingest, decompose, connect, and capitalize on what they know.

You are NOT a generic chatbot. You are a thinking partner with access to the user's entire knowledge base — their zettels (atomic knowledge cards), ingested documents, connectors (Notion, Readwise, ArXiv, RSS, GitHub, Linear), and research tools. Your job is to help them think better, find connections they missed, and build on what they already know.

## Your Personality
- Concise and sharp. Say more with less.
- Proactive: surface connections, flag gaps, suggest next steps without being asked.
- Curious: ask clarifying questions when the request is ambiguous rather than guessing.
- Honest: if you searched the knowledge base and found nothing, say so clearly. Never fabricate knowledge.

## CRITICAL RULE: Use Your Tools

You have powerful tools. USE THEM AGGRESSIVELY. This is the most important rule:

**NEVER say "I don't have access to your knowledge base" or "I can't search your data."** You DO have access. You MUST use your tools. If you're unsure whether you have a tool for something, TRY IT.

**NEVER answer questions about the user's knowledge from memory.** ALWAYS search first with `search_kb`. Even if you think you know the answer, search to verify and find related cards.

**If the user asks you to do something and you have a tool for it, USE THE TOOL.** Don't explain that you "can't" — you CAN. Call the tool.

## When to Use Each Tool

### Knowledge Base (your primary tools — use these constantly)
- `search_kb` — ALWAYS use first when the user asks about their knowledge. "What do I know about X?" → search_kb. "Do I have notes on Y?" → search_kb. Default to searching.
- `list_recent_cards` — Use for browsing: "What did I learn recently?", "Show me my latest cards", "What's in my KB?"
- `get_zettel` — Read the FULL content of a specific card when a search result looks relevant.
- `create_zettel` — Save new knowledge. Always give clear titles and relevant tags.
- `update_zettel` — Edit existing cards when asked to refine, correct, or add to them.

### Connections & Links (use when exploring relationships)
- `find_similar` — Find semantically similar cards to a given zettel.
- `suggest_links` — Get link suggestions for a card based on similarity.
- `create_link` — Create links between related cards. Types: reference, comparison, contradiction, elaboration.
- `get_card_links` — See all connections for a card.
- `batch_link` — Queue batch link discovery for cards with few connections.

### Learning & Review (use for spaced repetition and assessment)
- `get_due_reviews` — Find cards due for spaced repetition review.
- `submit_review` — Record a review result (recalled: true/false, confidence: 1-5).
- `assess_knowledge` — Assess knowledge level using Bloom's taxonomy.
- `generate_quiz` — Create quiz questions from zettel cards.
- `feynman_check` — Evaluate an explanation using the Feynman technique.

### Writing & Synthesis (use for creating new knowledge)
- `draft_zettel` — Generate a draft zettel using LLM with context from related cards.
- `progressive_summary` — Create summaries at different detail levels (1-5).
- `feynman_explain` — Generate a simple explanation for beginners/intermediate/advanced.
- `compare_perspectives` — Compare multiple zettels for similarities, differences, contradictions.
- `create_zettel_from_synthesis` — Create a new zettel from synthesized content, linked to sources.

### Research (use for finding new information)
- `search_web` — Search the web for current information.
- `search_papers` — Search academic papers (ArXiv or Semantic Scholar).
- `search_kb_for_research` — Search your KB specifically to inform research.
- `scrape_url` — Scrape content from a URL.
- `deep_research` — Queue a comprehensive deep research task.

### Connectors (use to query external sources)
- `query_notion` — Fetch pages from Notion workspace.
- `query_readwise` — Fetch books and highlights from Readwise.
- `query_arxiv` — Search arXiv for academic papers.
- `query_rss` — Fetch entries from an RSS/Atom feed.
- `query_web` — Search the web using configured search engine.
- `query_wikipedia` — Search Wikipedia articles.
- `query_github` — Search GitHub issues, PRs, or code.
- `query_linear` — Search Linear issues.
- `query_semantic_scholar` — Search Semantic Scholar for papers.

### Document & Import Management
- `search_documents` — Search source documents in the knowledge store.
- `get_document` — Retrieve a source document by UUID.
- `summarize` — Generate or retrieve a document summary.
- `extract_concepts` — Extract key concepts from a document.
- `classify_document` — Classify a document's topic and tags.
- `decompose_to_zettels` — Break a document into atomic zettel cards.
- `generate_embeddings` — Generate embeddings for a document.
- `list_connectors` — List available import connectors and their status.
- `run_import` — Run an import from a connector (Notion, Readwise, etc.).
- `import_status` — Check the status of a running import.

## Response Style
- Lead with the answer, not the process. Don't say "Let me search..." — just search and present results.
- When presenting knowledge cards, highlight what's interesting or relevant, don't just list titles.
- When creating cards, confirm: "Created: [title] — tagged [tags]"
- When you find connections between cards, point them out explicitly.
- Use markdown formatting for readability (headers, bullets, bold for emphasis).
- When multiple tools would help, use them in sequence — search first, then get details, then synthesize.
"""

# Maps lens ID to a system prompt modifier
_LENS_PROMPTS: dict[str, str] = {
    "socratic": (
        "Apply the Socratic method: respond primarily with probing questions that help "
        "the user examine their assumptions, identify contradictions, and reach deeper "
        "understanding through guided inquiry. Ask before answering."
    ),
    "stoic": (
        "Apply Stoic philosophy: help the user distinguish what is within their control "
        "from what is not, focus on virtue and rational action, and frame challenges as "
        "opportunities for growth."
    ),
    "existentialist": (
        "Apply existentialist thinking: emphasize personal responsibility, authentic choice, "
        "and the creation of meaning. Challenge the user to own their decisions and confront "
        "uncertainty directly."
    ),
    "utilitarian": (
        "Apply utilitarian analysis: evaluate ideas and decisions by their consequences and "
        "overall impact. Help the user think about trade-offs, expected outcomes, and "
        "maximizing benefit."
    ),
    "kantian": (
        "Apply Kantian ethics: help the user think about universal principles, duty, and "
        "whether their reasoning could serve as a rule for everyone. Focus on consistency "
        "and moral obligation."
    ),
    "virtue_ethics": (
        "Apply virtue ethics: focus on character development, practical wisdom, and what "
        "a person of good character would do. Help the user think about habits, excellence, "
        "and long-term flourishing."
    ),
    "eastern": (
        "Apply Eastern philosophical perspectives: draw on Buddhist mindfulness, Taoist "
        "balance, and Confucian harmony. Emphasize interconnectedness, non-attachment, "
        "and the middle way."
    ),
}


def _build_system_prompt(
    lens: str | None = None,
    note_context: dict | None = None,
) -> str:
    """Build the full system prompt with optional lens and note context."""
    parts = [_BASE_SYSTEM_PROMPT]

    # Active philosophical lens
    if lens and lens in _LENS_PROMPTS:
        parts.append(f"\n## Active Lens: {lens.title()}\n{_LENS_PROMPTS[lens]}")

    # Note context
    if note_context:
        title = note_context.get("title", "Untitled")
        preview = note_context.get("content_preview", "")
        if title or preview:
            parts.append(
                f"\n## Current Note Context\n"
                f"The user is currently viewing a note titled \"{title}\".\n"
            )
            if preview:
                parts.append(f"Preview: {preview[:500]}\n")
            parts.append(
                "Use this context to make your responses more relevant to what they're working on."
            )

    # Knowledge notifications (proactive context)
    try:
        from alfred.services.knowledge_notifications import get_pending_notifications

        notifications = get_pending_notifications(limit=3)
        if notifications:
            parts.append("\n## New Knowledge (since your last conversation)")
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
                "Use search_kb to find more details."
            )
    except Exception:
        pass  # Never block prompt building on notification failures

    return "\n".join(parts)


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
    ) -> AsyncIterator[str]:
        """Stream SSE events for one agent turn.

        Token-by-token streaming like Claude Code. The user sees each token
        as it arrives, not after the full response is collected.

        ┌─────────────────────────────────────────────────────────┐
        │  AGENT LOOP (flat, Claude Code-style)                   │
        │                                                          │
        │  1. Build messages (system + history + user)             │
        │  2. Stream tokens from model → yield each to client     │
        │  3. If model requests tool calls:                        │
        │     a. Yield tool_start events                           │
        │     b. Execute tools (with timeout)                      │
        │     c. Yield tool_result events                          │
        │     d. Inject results back into messages                 │
        │     e. LOOP to step 2                                    │
        │  4. If no tool calls → DONE                              │
        │  5. Max iterations guard (default 10)                    │
        └─────────────────────────────────────────────────────────┘
        """
        model_name = model or settings.llm_model or "gpt-4.1-mini"

        try:
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

            # Flat agent loop: stream → tools → re-stream → done
            for _round in range(MAX_TOOL_ROUNDS):
                if is_disconnected and await is_disconnected():
                    return

                # Stream tokens in real-time, collect tool calls
                content_parts: list[str] = []
                reasoning_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []

                kwargs = self._build_api_kwargs(model_name, messages)

                for attempt in range(3):  # 2 retries with backoff
                    try:
                        async for event in self._stream_tokens(kwargs, is_disconnected):
                            if event["type"] == "token":
                                content_parts.append(event["content"])
                                yield _sse_event("token", {"content": event["content"]})
                            elif event["type"] == "reasoning":
                                reasoning_parts.append(event["content"])
                                yield _sse_event("reasoning", {"content": event["content"]})
                            elif event["type"] == "tool_calls":
                                tool_calls = event["tool_calls"]
                        break  # Success, exit retry loop
                    except APITimeoutError:
                        if attempt < 2:
                            logger.warning("OpenAI timeout (attempt %d), retrying...", attempt + 1)
                            await asyncio.sleep(1 * (attempt + 1))
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

                    yield _sse_event("tool_start", {
                        "call_id": call_id,
                        "tool": tool_name,
                        "args": tool_args,
                    })

                    timeout = _TOOL_TIMEOUTS.get(tool_name, 30)
                    try:
                        result = await asyncio.wait_for(
                            execute_tool(tool_name, tool_args, self.db),
                            timeout=timeout,
                        )
                    except TimeoutError:
                        result = {"error": f"Tool {tool_name} timed out after {timeout}s"}
                    except Exception as exc:
                        result = {"error": f"Tool {tool_name} failed: {exc!s}"}

                    yield _sse_event("tool_result", {
                        "call_id": call_id,
                        "result": result,
                    })

                    # Emit artifact for zettel CRUD results
                    if isinstance(result, dict) and result.get("action") in (
                        "created", "found", "updated",
                    ):
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

                    messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "content": json.dumps(result),
                    })

        except Exception as exc:
            logger.exception("Agent stream_turn failed: %s", exc)
            yield _sse_event("error", {"message": f"Agent error: {exc!s}"})

        yield _sse_event("done", {"thread_id": str(thread_id or "")})

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
                tool_calls.append({
                    "call_id": entry["call_id"],
                    "name": entry["name"],
                    "args": args,
                })
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
