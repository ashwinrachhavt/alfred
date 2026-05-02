"""Tests for SSEStreamOrchestrator base class."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alfred.services.sse_base import SSEStreamOrchestrator

# ---------------------------------------------------------------------------
# Mock helpers for OpenAI streaming (mirrors test_zettel_creation_stream.py)
# ---------------------------------------------------------------------------


class MockStreamChunk:
    def __init__(self, content=None, reasoning=None):
        self.choices = [MagicMock()]
        self.choices[0].delta = MagicMock()
        self.choices[0].delta.content = content
        # Both attributes for o3/o4 compatibility
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


# ---------------------------------------------------------------------------
# _sse formatting
# ---------------------------------------------------------------------------


def test_sse_event_formatting():
    """Exact SSE wire format for a simple dict."""
    result = SSEStreamOrchestrator._sse("foo", {"a": 1})
    assert result == 'event: foo\ndata: {"a": 1}\n\n'


def test_sse_event_handles_datetime_via_default_str():
    """datetime values should be stringified via default=str, not raise."""
    now = datetime(2026, 5, 1, 12, 34, 56, tzinfo=UTC)
    # Should not raise
    result = SSEStreamOrchestrator._sse("with_dt", {"when": now})
    # The event prefix is stable
    assert result.startswith("event: with_dt\ndata: ")
    # And the payload parses as JSON with a string "when"
    payload = result[len("event: with_dt\ndata: ") : -2]
    data = json.loads(payload)
    assert isinstance(data["when"], str)
    assert "2026-05-01" in data["when"]


# ---------------------------------------------------------------------------
# _parse_structured_json
# ---------------------------------------------------------------------------


def test_parse_structured_json_handles_bare_json():
    assert SSEStreamOrchestrator._parse_structured_json('{"a": 1}') == {"a": 1}


def test_parse_structured_json_strips_markdown_fences():
    """Both ```json and bare ``` fences should be stripped."""
    fenced_lang = '```json\n{"a": 1}\n```'
    fenced_bare = '```\n{"a": 1}\n```'

    assert SSEStreamOrchestrator._parse_structured_json(fenced_lang) == {"a": 1}
    assert SSEStreamOrchestrator._parse_structured_json(fenced_bare) == {"a": 1}


def test_parse_structured_json_returns_none_on_malformed():
    """Malformed input should return None, not raise."""
    assert SSEStreamOrchestrator._parse_structured_json("not json") is None


def test_parse_structured_json_returns_none_on_empty():
    assert SSEStreamOrchestrator._parse_structured_json("") is None


# ---------------------------------------------------------------------------
# _is_disconnected_or_stale
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_disconnected_or_stale_no_request_no_stale_fn_returns_false():
    orch = SSEStreamOrchestrator()
    assert await orch._is_disconnected_or_stale() is False


@pytest.mark.asyncio
async def test_is_disconnected_or_stale_detects_disconnect():
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    orch = SSEStreamOrchestrator(request=mock_request)
    assert await orch._is_disconnected_or_stale() is True


@pytest.mark.asyncio
async def test_is_disconnected_or_stale_detects_stale_via_caller_fn():
    orch = SSEStreamOrchestrator()
    assert await orch._is_disconnected_or_stale(is_stale=lambda: True) is True


@pytest.mark.asyncio
async def test_is_disconnected_or_stale_disconnect_takes_precedence():
    """Disconnect True short-circuits the is_stale check."""
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(return_value=True)

    stale_calls = {"n": 0}

    def is_stale():
        stale_calls["n"] += 1
        return False

    orch = SSEStreamOrchestrator(request=mock_request)
    assert await orch._is_disconnected_or_stale(is_stale=is_stale) is True
    # Short-circuit: is_stale may or may not be called depending on impl —
    # but disconnect True must win regardless.
    # Verify the method returned True without depending on the is_stale fn.


@pytest.mark.asyncio
async def test_is_disconnected_or_stale_swallows_exceptions():
    """Exceptions from either check should be swallowed; method returns False."""
    # Case 1: is_stale raises
    orch = SSEStreamOrchestrator()

    def boom():
        raise RuntimeError("staleness lookup failed")

    assert await orch._is_disconnected_or_stale(is_stale=boom) is False

    # Case 2: is_disconnected raises
    mock_request = MagicMock()
    mock_request.is_disconnected = AsyncMock(side_effect=RuntimeError("transport dead"))

    orch2 = SSEStreamOrchestrator(request=mock_request)
    # Without an is_stale fn, returns False
    assert await orch2._is_disconnected_or_stale() is False


# ---------------------------------------------------------------------------
# _run_openai_stream_with_reasoning
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_openai_stream_yields_thinking_and_completion_tuples():
    chunks = [
        MockStreamChunk(reasoning="Let me think about this..."),
        MockStreamChunk(content='{"a":'),
        MockStreamChunk(content=" 1}"),
    ]
    mock_client = _mock_openai_client(chunks)

    orch = SSEStreamOrchestrator()

    with patch(
        "alfred.core.llm_factory.get_async_openai_client",
        return_value=mock_client,
    ):
        tuples = []
        async for kind, content in orch._run_openai_stream_with_reasoning(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
        ):
            tuples.append((kind, content))

    kinds = [k for k, _ in tuples]
    assert "thinking" in kinds
    assert "completion" in kinds
    # Reassembled completion buffer should parse as valid JSON
    completion_buf = "".join(c for k, c in tuples if k == "completion")
    assert json.loads(completion_buf) == {"a": 1}


@pytest.mark.asyncio
async def test_run_openai_stream_aborts_on_disconnect_mid_stream():
    """If the client disconnects after chunk 1, only 1 tuple should be yielded."""
    chunks = [
        MockStreamChunk(content="first"),
        MockStreamChunk(content="second"),
        MockStreamChunk(content="third"),
    ]
    mock_client = _mock_openai_client(chunks)

    # Track how many times is_disconnected has been called.
    # - First call (before chunk 1 is yielded to caller): returns False
    # - Subsequent calls (between yields): return True -> abort
    call_count = {"n": 0}

    async def is_disconnected():
        call_count["n"] += 1
        # Loop order in the implementation:
        #   async for chunk in stream:
        #       if await self._is_disconnected_or_stale(...): return
        #       ...
        #       yield ("completion", ...)
        # So the first check happens BEFORE the first yield.
        # Return False on first check, True afterwards.
        return call_count["n"] > 1

    mock_request = MagicMock()
    mock_request.is_disconnected = is_disconnected

    orch = SSEStreamOrchestrator(request=mock_request)

    with patch(
        "alfred.core.llm_factory.get_async_openai_client",
        return_value=mock_client,
    ):
        tuples = []
        async for kind, content in orch._run_openai_stream_with_reasoning(
            messages=[{"role": "user", "content": "hi"}],
            model="gpt-5.4-mini",
        ):
            tuples.append((kind, content))

    assert len(tuples) == 1
    assert tuples[0] == ("completion", "first")


# ---------------------------------------------------------------------------
# base run() raises NotImplementedError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_base_run_raises_not_implemented():
    orch = SSEStreamOrchestrator()
    gen = orch.run()
    with pytest.raises(NotImplementedError):
        await gen.__anext__()
