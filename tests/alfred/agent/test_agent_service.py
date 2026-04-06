"""Tests for AgentService — OpenAI streaming agent with tool calls."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alfred.services.agent.service import AgentService, _build_system_prompt, _sse_event

# ---------------------------------------------------------------------------
# Helpers: mock OpenAI streaming responses
# ---------------------------------------------------------------------------


def _make_delta(
    content: str | None = None,
    tool_calls: list | None = None,
    reasoning: str | None = None,
):
    """Create a mock delta object."""
    delta = MagicMock()
    delta.content = content
    delta.tool_calls = tool_calls
    if reasoning is not None:
        delta.reasoning = reasoning
    else:
        delta.reasoning = None
    delta.reasoning_content = None
    return delta


def _make_chunk(delta, index: int = 0):
    """Create a mock streaming chunk."""
    choice = MagicMock()
    choice.delta = delta
    choice.index = index
    chunk = MagicMock()
    chunk.choices = [choice]
    return chunk


def _make_tool_call_delta(index: int, call_id: str | None, name: str | None, arguments: str | None):
    """Create a mock tool_call delta for incremental streaming."""
    tc = MagicMock()
    tc.index = index
    tc.id = call_id
    tc.function = MagicMock()
    tc.function.name = name
    tc.function.arguments = arguments
    return tc


class MockAsyncStream:
    """Async iterator that yields mock chunks."""

    def __init__(self, chunks: list):
        self._chunks = chunks
        self._index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._index >= len(self._chunks):
            raise StopAsyncIteration
        chunk = self._chunks[self._index]
        self._index += 1
        return chunk


def _simple_text_stream(text: str) -> MockAsyncStream:
    """Create a stream that yields text content in chunks."""
    chunks = []
    for char in text:
        chunks.append(_make_chunk(_make_delta(content=char)))
    # Final chunk with empty delta
    chunks.append(_make_chunk(_make_delta()))
    return MockAsyncStream(chunks)


def _tool_call_stream(
    call_id: str, tool_name: str, args: dict,
) -> MockAsyncStream:
    """Create a stream that yields a tool call."""
    args_json = json.dumps(args)
    chunks = [
        _make_chunk(_make_delta(
            tool_calls=[_make_tool_call_delta(0, call_id, tool_name, None)],
        )),
        _make_chunk(_make_delta(
            tool_calls=[_make_tool_call_delta(0, None, None, args_json)],
        )),
        _make_chunk(_make_delta()),
    ]
    return MockAsyncStream(chunks)


def _parse_events(raw_events: list[str]) -> list[tuple[str, dict]]:
    """Parse SSE strings into (event_type, data) tuples."""
    parsed = []
    for event_str in raw_events:
        lines = event_str.strip().split("\n")
        evt_type = ""
        evt_data = {}
        for line in lines:
            if line.startswith("event: "):
                evt_type = line[7:]
            elif line.startswith("data: "):
                evt_data = json.loads(line[6:])
        if evt_type:
            parsed.append((evt_type, evt_data))
    return parsed


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_notifications():
    """Prevent Redis calls from _build_system_prompt notifications check."""
    with patch(
        "alfred.services.knowledge_notifications.get_pending_notifications",
        return_value=[],
    ):
        yield


@pytest.fixture()
def db_session():
    """Minimal mock DB session."""
    return MagicMock()


@pytest.fixture()
def service(db_session):
    """AgentService with a mock DB session."""
    svc = AgentService(db_session)
    svc._client = MagicMock(spec=True)
    return svc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_happy_path_text_response(service):
    """Simple text response yields token events and done."""
    stream = _simple_text_stream("Hello!")

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(return_value=stream)

    events = []
    async for event in service.stream_turn(message="Hi"):
        events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    assert "token" in event_types
    assert event_types[-1] == "done"

    # Verify the content was streamed token-by-token (real streaming)
    token_events = [e for e in parsed if e[0] == "token"]
    assert len(token_events) >= 1
    full_content = "".join(e[1]["content"] for e in token_events)
    assert full_content == "Hello!"


@pytest.mark.asyncio
async def test_tool_call_flow(service):
    """Tool call yields tool_start, tool_result, then final text after re-injection."""
    # First call: model returns a tool call
    tool_stream = _tool_call_stream(
        call_id="call_abc123",
        tool_name="search_kb",
        args={"query": "philosophy"},
    )
    # Second call: model returns text after tool result is injected
    text_stream = _simple_text_stream("Found 3 results.")

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_stream
        return text_stream

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    tool_result = {"results": [{"title": "Epistemology"}], "count": 1}

    events = []
    with patch("alfred.services.agent.service.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = tool_result
        async for event in service.stream_turn(message="Search philosophy"):
            events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert "token" in event_types
    assert event_types[-1] == "done"

    # Verify tool_start has correct data
    tool_starts = [e for e in parsed if e[0] == "tool_start"]
    assert tool_starts[0][1]["tool"] == "search_kb"
    assert tool_starts[0][1]["call_id"] == "call_abc123"

    # Verify tool_result has correct data
    tool_results = [e for e in parsed if e[0] == "tool_result"]
    assert tool_results[0][1]["call_id"] == "call_abc123"
    assert tool_results[0][1]["result"]["count"] == 1


@pytest.mark.asyncio
async def test_multi_round_tool_then_text(service):
    """Model calls a tool, gets result, then responds with text."""
    # Round 1: tool call
    tool_stream = _tool_call_stream("call_1", "get_zettel", {"zettel_id": 42})
    # Round 2: text response
    text_stream = _simple_text_stream("Here is the zettel.")

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_stream
        return text_stream

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    zettel_result = {
        "action": "found",
        "zettel_id": 42,
        "title": "Epistemology 101",
        "content": "Knowledge is justified true belief.",
        "summary": "Knowledge is justified true belief.",
        "topic": "philosophy",
        "tags": ["epistemology"],
    }

    events = []
    with patch("alfred.services.agent.service.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = zettel_result
        async for event in service.stream_turn(message="Show zettel 42"):
            events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    # Verify the full flow
    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert "artifact" in event_types  # found zettel emits artifact
    assert "token" in event_types
    assert event_types[-1] == "done"

    # Verify artifact has zettel data
    artifacts = [e for e in parsed if e[0] == "artifact"]
    assert artifacts[0][1]["action"] == "found"
    assert artifacts[0][1]["zettel"]["id"] == 42

    # Verify OpenAI was called twice (tool call + after injection)
    assert call_count == 2


@pytest.mark.asyncio
async def test_timeout_yields_error(service):
    """OpenAI timeout yields an error event and still emits done."""
    from openai import APITimeoutError

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(
        side_effect=APITimeoutError(request=MagicMock()),
    )

    events = []
    async for event in service.stream_turn(message="Hello"):
        events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    assert "error" in event_types
    assert event_types[-1] == "done"


@pytest.mark.asyncio
async def test_rate_limit_retry(service):
    """Rate limit error retries once after 2s delay."""
    from openai import RateLimitError

    text_stream = _simple_text_stream("OK")

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            resp = MagicMock()
            resp.status_code = 429
            resp.headers = {}
            raise RateLimitError(
                message="Rate limit exceeded",
                response=resp,
                body=None,
            )
        return text_stream

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    events = []
    with patch("alfred.services.agent.service.asyncio.sleep", new_callable=AsyncMock):
        async for event in service.stream_turn(message="Hello"):
            events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    assert "token" in event_types
    assert event_types[-1] == "done"
    assert call_count == 2  # First call failed, second succeeded


@pytest.mark.asyncio
async def test_tool_timeout_yields_error_result(service):
    """Tool that times out yields a tool_result with error, then continues."""
    tool_stream = _tool_call_stream("call_slow", "search_kb", {"query": "test"})
    text_stream = _simple_text_stream("Sorry, search timed out.")

    call_count = 0

    async def mock_create(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_stream
        return text_stream

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(side_effect=mock_create)

    events = []
    with patch("alfred.services.agent.service.execute_tool", new_callable=AsyncMock) as mock_exec:
        mock_exec.side_effect = TimeoutError()
        async for event in service.stream_turn(message="Search"):
            events.append(event)

    parsed = _parse_events(events)

    # Find tool_result event
    tool_results = [e for e in parsed if e[0] == "tool_result"]
    assert len(tool_results) == 1
    assert "error" in tool_results[0][1]["result"]
    assert "timed out" in tool_results[0][1]["result"]["error"]


@pytest.mark.asyncio
async def test_reasoning_extraction(service):
    """o3/o4 reasoning content is yielded as reasoning events."""
    chunks = [
        _make_chunk(_make_delta(reasoning="Let me think...")),
        _make_chunk(_make_delta(reasoning=" Step 1: analyze.")),
        _make_chunk(_make_delta(content="Here is my answer.")),
        _make_chunk(_make_delta()),
    ]
    stream = MockAsyncStream(chunks)

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(return_value=stream)

    events = []
    async for event in service.stream_turn(message="Think about this", model="o3"):
        events.append(event)

    parsed = _parse_events(events)
    event_types = [e[0] for e in parsed]

    assert "reasoning" in event_types
    assert "token" in event_types

    reasoning_events = [e for e in parsed if e[0] == "reasoning"]
    full_reasoning = "".join(e[1]["content"] for e in reasoning_events)
    assert full_reasoning == "Let me think... Step 1: analyze."


@pytest.mark.asyncio
async def test_disconnected_client_stops_early(service):
    """When is_disconnected returns True, streaming stops."""
    # Create a long stream
    chunks = [_make_chunk(_make_delta(content=f"word{i} ")) for i in range(100)]
    stream = MockAsyncStream(chunks)

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(return_value=stream)

    call_count = 0

    async def is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count > 2  # Disconnect after 2 checks

    events = []
    async for event in service.stream_turn(
        message="Hello",
        is_disconnected=is_disconnected,
    ):
        events.append(event)

    # Should have stopped early — fewer events than the full stream
    parsed = _parse_events(events)
    assert len(parsed) <= 3  # At most a couple events before disconnect


@pytest.mark.asyncio
async def test_gpt5_uses_max_completion_tokens(service):
    """GPT-5.x models use max_completion_tokens instead of max_tokens."""
    stream = _simple_text_stream("OK")

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(return_value=stream)

    events = []
    async for event in service.stream_turn(message="Hi", model="gpt-5.4-mini"):
        events.append(event)

    # Verify the API was called with correct params
    call_kwargs = service.client.chat.completions.create.call_args
    assert "max_completion_tokens" in call_kwargs.kwargs
    assert "max_tokens" not in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_gpt4o_uses_max_tokens(service):
    """GPT-4o models use max_tokens (legacy)."""
    stream = _simple_text_stream("OK")

    service.client.chat = MagicMock()
    service.client.chat.completions = MagicMock()
    service.client.chat.completions.create = AsyncMock(return_value=stream)

    events = []
    async for event in service.stream_turn(message="Hi", model="gpt-4o"):
        events.append(event)

    call_kwargs = service.client.chat.completions.create.call_args
    assert "max_tokens" in call_kwargs.kwargs
    assert "max_completion_tokens" not in call_kwargs.kwargs


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_build_system_prompt_basic(_mock_notif):
    """System prompt includes Alfred identity and tool usage instructions."""
    prompt = _build_system_prompt()
    assert "Alfred" in prompt
    assert "knowledge" in prompt.lower()
    assert "search_kb" in prompt  # Tool usage instructions present
    assert "NEVER say" in prompt  # Critical rule present


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_build_system_prompt_with_lens(_mock_notif):
    """System prompt includes lens when provided."""
    prompt = _build_system_prompt(lens="socratic")
    assert "Socratic" in prompt
    assert "probing questions" in prompt.lower()


@patch("alfred.services.knowledge_notifications.get_pending_notifications", return_value=[])
def test_build_system_prompt_with_note_context(_mock_notif):
    """System prompt includes note context when provided."""
    prompt = _build_system_prompt(note_context={"title": "My Note", "content_preview": "Some content"})
    assert "My Note" in prompt
    assert "Some content" in prompt


def test_sse_event_format():
    """SSE event format is correct."""
    event = _sse_event("token", {"content": "hello"})
    assert event == 'event: token\ndata: {"content": "hello"}\n\n'


def test_done_event_always_emitted():
    """Verify done event format."""
    event = _sse_event("done", {"thread_id": "123"})
    assert "event: done" in event
    assert '"thread_id": "123"' in event
