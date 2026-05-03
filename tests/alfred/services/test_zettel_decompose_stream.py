"""Tests for ZettelDecomposeStream orchestrator (T5)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alfred.schemas.zettel import ZettelDecomposeRequest
from alfred.services.zettel_decompose_stream import ZettelDecomposeStream

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _parse_sse_events(raw_events: list[str]) -> list[tuple[str, dict]]:
    """Parse SSE strings into (event_name, data) tuples."""
    results = []
    for raw in raw_events:
        lines = raw.strip().split("\n")
        event_name = ""
        data = {}
        for line in lines:
            if line.startswith("event: "):
                event_name = line[7:]
            elif line.startswith("data: "):
                data = json.loads(line[6:])
        if event_name:
            results.append((event_name, data))
    return results


class MockStreamChunk:
    def __init__(self, content=None, reasoning=None):
        self.choices = [MagicMock()]
        self.choices[0].delta = MagicMock()
        self.choices[0].delta.content = content
        self.choices[0].delta.reasoning = reasoning
        self.choices[0].delta.reasoning_content = reasoning


class MockStream:
    def __init__(self, chunks):
        self._chunks = iter(chunks)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._chunks)
        except StopIteration:
            raise StopAsyncIteration from None


def _mock_openai_client(chunks):
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=MockStream(chunks))
    return mock_client


def _make_candidates_json(candidates: list[dict]) -> str:
    return json.dumps({"candidates": candidates})


def _long_content(marker: str, length: int = 180) -> str:
    """Produce a body at least as long as MIN_CONTENT_LEN including `marker`."""
    filler = " padding text to exceed the minimum block-sized body length"
    base = f"{marker}.{filler}"
    if len(base) < length:
        base = base + filler * 3
    return base[:length]


def test_decompose_prompt_prefers_block_sized_cards_over_sentence_atoms():
    payload = ZettelDecomposeRequest(
        raw_text="First block.\n\nSecond block.",
        shared_topic="learning",
    )
    stream = ZettelDecomposeStream(payload)

    messages = stream._build_decompose_prompt()
    system = messages[0]["content"]

    assert "coherent block-sized cards" in system
    assert "3-6 sentences" in system
    assert "Do NOT split sentence-by-sentence" in system
    assert "less than 120 characters" in system


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_happy_path_three_candidates():
    """Three well-formed candidates → 1 started, 3 candidate_ready, 1 complete."""
    candidates = [
        {
            "title": f"Title {i}",
            "content": _long_content(f"Candidate {i}"),
            "bloom_level": 2,
            "bloom_rationale": "explains concept",
            "tags": ["alpha"],
            "links_to_siblings": [],
        }
        for i in range(3)
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="Some paragraph worth decomposing.")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    names = [e[0] for e in parsed]

    assert names.count("decompose_started") == 1
    assert names.count("candidate_ready") == 3
    assert names.count("decompose_complete") == 1

    ready = [d for n, d in parsed if n == "candidate_ready"]
    assert [c["index"] for c in ready] == [0, 1, 2]

    complete = next(d for n, d in parsed if n == "decompose_complete")
    assert complete["total_candidates"] == 3


# ---------------------------------------------------------------------------
# 2. Cap at 15
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_caps_at_15_candidates():
    """If the LLM returns 20, emit exactly 15 candidate_ready events."""
    candidates = [
        {
            "title": f"Title {i}",
            "content": _long_content(f"Candidate {i}"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        }
        for i in range(20)
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="Long paragraph.")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    ready = [d for n, d in parsed if n == "candidate_ready"]
    assert len(ready) == 15
    complete = next(d for n, d in parsed if n == "decompose_complete")
    assert complete["total_candidates"] == 15


# ---------------------------------------------------------------------------
# 3. Under-length candidates dropped
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_rejects_candidates_under_minimum_block_size():
    """A candidate with 30-char content should be dropped."""
    short = "x" * 30  # below MIN_CONTENT_LEN
    candidates = [
        {
            "title": "Keep A",
            "content": _long_content("Keep A"),
            "bloom_level": 2,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        },
        {
            "title": "Drop Me",
            "content": short,
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        },
        {
            "title": "Keep B",
            "content": _long_content("Keep B"),
            "bloom_level": 3,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        },
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="Paragraph.")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    ready = [d for n, d in parsed if n == "candidate_ready"]
    assert len(ready) == 2
    titles = [c["title"] for c in ready]
    assert "Keep A" in titles
    assert "Keep B" in titles
    assert "Drop Me" not in titles


# ---------------------------------------------------------------------------
# 4. Empty input
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_handles_empty_input():
    """Whitespace-only raw_text should yield only a decompose_input error."""
    # Pydantic requires min_length=1 on raw_text, so use a single whitespace
    # character that satisfies the schema but is empty after .strip().
    payload = ZettelDecomposeRequest(raw_text="   ")
    stream = ZettelDecomposeStream(payload)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    name, data = parsed[0]
    assert name == "error"
    assert data["step"] == "decompose_input"


# ---------------------------------------------------------------------------
# 5. OpenAI error
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_handles_openai_error():
    """An OpenAI client exception should surface as an error event."""
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API down"))

    payload = ZettelDecomposeRequest(raw_text="Some content worth decomposing.")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    errors = [(n, d) for n, d in parsed if n == "error"]
    assert len(errors) == 1
    _, err = errors[0]
    assert err["step"] == "decompose_llm"
    assert "API down" in err["message"]


# ---------------------------------------------------------------------------
# 6. Malformed JSON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_handles_malformed_json():
    """Gibberish LLM output should produce a decompose_parse error."""
    chunks = [MockStreamChunk(content="this is not JSON {{{")]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="Paragraph.")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    errors = [(n, d) for n, d in parsed if n == "error"]
    assert len(errors) == 1
    _, err = errors[0]
    assert err["step"] == "decompose_parse"


# ---------------------------------------------------------------------------
# 7. Input truncation at 16K
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_truncates_input_to_16k_chars():
    """An oversized raw_text should be truncated to 16_000 chars in the prompt."""
    big = "A" * 20_000
    candidates = [
        {
            "title": "ok",
            "content": _long_content("ok"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        }
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text=big)
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    # Inspect the messages passed to chat.completions.create.
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    messages = call_kwargs["messages"]
    user_content = messages[1]["content"]
    # The user message inlines the raw text — it should contain exactly
    # 16_000 'A's and not a single character more.
    assert user_content.count("A") == 16_000
    assert "A" * 16_001 not in user_content

    # The started event should also report the truncated length.
    parsed = _parse_sse_events(events)
    started = next(d for n, d in parsed if n == "decompose_started")
    assert started["raw_char_count"] == 16_000


# ---------------------------------------------------------------------------
# 8. Sibling-link sanitisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_sanitizes_sibling_links():
    """Out-of-range / negative / self indexes in links_to_siblings are dropped."""
    candidates = [
        {
            "title": "A",
            "content": _long_content("A"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [99, 0, -1, 1],
        },
        {
            "title": "B",
            "content": _long_content("B"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [0, 1, 2, -1],
        },
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="paragraph")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    ready = [d for n, d in parsed if n == "candidate_ready"]
    assert len(ready) == 2

    # Candidate 0 had [99, 0, -1, 1] — only 1 is in-range-and-not-self.
    assert ready[0]["links_to_siblings"] == [1]
    # Candidate 1 had [0, 1, 2, -1] — only 0 survives.
    assert ready[1]["links_to_siblings"] == [0]


# ---------------------------------------------------------------------------
# 9. Tag normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_normalizes_tags_lowercase_and_dedup():
    """Tags are lowercased + deduped in insertion order."""
    candidates = [
        {
            "title": "A",
            "content": _long_content("A"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": ["Alpha", "alpha", "BETA"],
            "links_to_siblings": [],
        }
    ]
    chunks = [MockStreamChunk(content=_make_candidates_json(candidates))]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="paragraph")
    stream = ZettelDecomposeStream(payload)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    ready = next(d for n, d in parsed if n == "candidate_ready")
    assert ready["tags"] == ["alpha", "beta"]


# ---------------------------------------------------------------------------
# 10. Idempotency — stale hash aborts mid-stream
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decompose_idempotency_stale_hash_aborts_mid_stream():
    """Mid-stream, if another request rewrites the Redis hash, the stream aborts."""
    # Build a fake Redis that returns hash "B" on every .get(), i.e. a newer
    # request has already superseded this one. The .set() at stream start
    # writes "A", but .get() later returns "B", so is_stale fires.
    fake_redis = MagicMock()
    state = {"value": None}

    def _set(key, value, ex=None):
        state["value"] = value

    def _get(key):
        # First call (inside _make_stale_checker) writes 'A' via .set, but
        # immediately after we overwrite state["value"] to 'B' to simulate a
        # concurrent newer request. We do this by having .get return 'B'
        # regardless of what was set — the write happened, so we're past the
        # set-check moment.
        return "B"

    fake_redis.set.side_effect = _set
    fake_redis.get.side_effect = _get

    candidates = [
        {
            "title": f"T{i}",
            "content": _long_content(f"Candidate {i}"),
            "bloom_level": 1,
            "bloom_rationale": "",
            "tags": [],
            "links_to_siblings": [],
        }
        for i in range(3)
    ]
    # Two chunks: one reasoning token (so the is_stale check inside the
    # openai-stream loop gets hit), then the JSON.
    chunks = [
        MockStreamChunk(reasoning="thinking..."),
        MockStreamChunk(content=_make_candidates_json(candidates)),
    ]
    mock_client = _mock_openai_client(chunks)

    payload = ZettelDecomposeRequest(raw_text="Something interesting.", session_id=42)
    stream = ZettelDecomposeStream(payload)

    with (
        patch(
            "alfred.core.redis_client.get_redis_client",
            return_value=fake_redis,
        ),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    names = [e[0] for e in parsed]
    # The stream should have emitted decompose_started (before the stale
    # check ever runs) but MUST NOT emit decompose_complete.
    assert "decompose_started" in names
    assert "decompose_complete" not in names
    # No candidates should have been emitted either, because the openai
    # loop exits on the very first chunk.
    assert "candidate_ready" not in names
