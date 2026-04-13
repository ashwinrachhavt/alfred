"""Tests for ZettelCreationStream orchestrator."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.models.zettel import (  # noqa: F401 — ensure tables exist
    ZettelCard,
    ZettelLink,
    ZettelReview,
)
from alfred.schemas.zettel import LinkQuality, LinkSuggestion, ZettelCardCreate
from alfred.services.zettel_creation_stream import ZettelCreationStream, _sse
from alfred.services.zettelkasten_service import ZettelkastenService


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


@pytest.fixture()
def db_session() -> Session:
    # StaticPool reuses a single connection for all threads, which lets
    # asyncio.to_thread access the same in-memory SQLite database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.mark.asyncio
async def test_phase0_emits_card_saved(db_session):
    """Phase 0 should save the card and emit card_saved as the first event."""
    payload = ZettelCardCreate(title="Test Card", content="Some content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run_phase0():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) >= 1
    event_name, data = parsed[0]
    assert event_name == "card_saved"
    assert data["title"] == "Test Card"
    assert "id" in data
    assert stream.card_id is not None


@pytest.mark.asyncio
async def test_phase0_card_persisted_in_db(db_session):
    """The card should actually exist in the database after Phase 0."""
    payload = ZettelCardCreate(title="Persisted Card", content="Content here")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    card = db_session.get(ZettelCard, stream.card_id)
    assert card is not None
    assert card.title == "Persisted Card"
    assert card.content == "Content here"


@pytest.mark.asyncio
async def test_phase0_error_emits_error_event():
    """If card save fails, Phase 0 should emit error event, not crash."""
    payload = ZettelCardCreate(title="Error Card", content="Content")

    def bad_factory():
        raise RuntimeError("DB connection failed")

    stream = ZettelCreationStream(payload, db_session_factory=bad_factory)

    events = []
    async for sse in stream.run_phase0():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert "card_save" in data["step"]


@pytest.mark.asyncio
async def test_sse_format():
    """_sse helper should produce correct SSE format."""
    result = _sse("test_event", {"key": "value"})
    assert result == 'event: test_event\ndata: {"key": "value"}\n\n'


@pytest.mark.asyncio
async def test_full_run_emits_card_saved_then_done(db_session):
    """Full run() should emit card_saved first and done last."""
    payload = ZettelCardCreate(title="Full Run Test", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert event_names[0] == "card_saved"
    assert event_names[-1] == "done"


@pytest.mark.asyncio
async def test_full_run_done_contains_card_info(db_session):
    """The done event should include the card id and title."""
    payload = ZettelCardCreate(title="Info Card", content="Details")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    done_event = [e for e in parsed if e[0] == "done"]
    assert len(done_event) == 1
    done_data = done_event[0][1]
    assert done_data["card"]["id"] is not None
    assert done_data["card"]["title"] == "Info Card"


@pytest.mark.asyncio
async def test_full_run_on_phase0_failure_emits_done_with_error():
    """If Phase 0 fails, run() should emit error then done with null card."""
    payload = ZettelCardCreate(title="Fail Card", content="Content")

    def bad_factory():
        raise RuntimeError("DB down")

    stream = ZettelCreationStream(payload, db_session_factory=bad_factory)

    events = []
    async for sse in stream.run():
        events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "error" in event_names
    assert event_names[-1] == "done"
    done_data = parsed[-1][1]
    assert done_data["card"] is None
    assert done_data["stats"]["error"] == "card_save_failed"


# ---------------------------------------------------------------------------
# Track A tests
# ---------------------------------------------------------------------------


def _make_suggestion(
    to_card_id: int, title: str, composite_score: float, reason: str = "test"
) -> LinkSuggestion:
    """Helper to build a LinkSuggestion with a given composite score."""
    return LinkSuggestion(
        to_card_id=to_card_id,
        to_title=title,
        to_topic="test_topic",
        to_tags=["tag"],
        reason=reason,
        scores=LinkQuality(
            semantic_score=composite_score,
            tag_overlap=0.5,
            topic_match=True,
            citation_overlap=0,
            composite_score=composite_score,
            confidence="high" if composite_score >= 0.75 else "medium",
        ),
    )


def _make_link(
    link_id: int, from_card_id: int, to_card_id: int, link_type: str = "auto_stream"
) -> MagicMock:
    """Helper to build a mock ZettelLink."""
    link = MagicMock()
    link.id = link_id
    link.from_card_id = from_card_id
    link.to_card_id = to_card_id
    link.type = link_type
    return link


@pytest.mark.asyncio
async def test_track_a_emits_embedding_and_links(db_session):
    """Track A should emit embedding_done, tool_start, and links_found."""
    payload = ZettelCardCreate(title="Track A Card", content="Some content about AI")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # Phase 0: save the card first
    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    suggestion = _make_suggestion(to_card_id=999, title="Related Card", composite_score=0.91)

    with (
        patch.object(
            ZettelkastenService, "ensure_embedding", side_effect=lambda card: card
        ) as mock_embed,
        patch.object(
            ZettelkastenService, "suggest_links", return_value=[suggestion]
        ) as mock_suggest,
        patch.object(
            ZettelkastenService,
            "create_link",
            return_value=[_make_link(1, stream.card_id, 999)],
        ),
    ):
        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "embedding_done" in event_names
    assert "tool_start" in event_names
    assert "links_found" in event_names
    assert "links_created" in event_names

    # Verify embedding_done data
    embed_data = next(d for n, d in parsed if n == "embedding_done")
    assert embed_data["card_id"] == stream.card_id

    # Verify links_found has the suggestion
    links_data = next(d for n, d in parsed if n == "links_found")
    assert len(links_data["suggestions"]) == 1
    assert links_data["suggestions"][0]["score"] == 0.91

    mock_embed.assert_called_once()
    mock_suggest.assert_called_once()


@pytest.mark.asyncio
async def test_track_a_empty_suggestions(db_session):
    """Empty suggest_links result should yield links_found with empty list, no links_created."""
    payload = ZettelCardCreate(title="Lonely Card", content="Unique content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    with (
        patch.object(ZettelkastenService, "ensure_embedding", side_effect=lambda card: card),
        patch.object(ZettelkastenService, "suggest_links", return_value=[]),
    ):
        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "links_found" in event_names
    links_data = next(d for n, d in parsed if n == "links_found")
    assert links_data["suggestions"] == []

    assert "links_created" not in event_names


@pytest.mark.asyncio
async def test_track_a_threshold_boundary(db_session):
    """Score >= 0.75 should be auto-linked; score < 0.75 should not."""
    payload = ZettelCardCreate(title="Threshold Card", content="Boundary test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    at_threshold = _make_suggestion(to_card_id=100, title="At Threshold", composite_score=0.75)
    below_threshold = _make_suggestion(
        to_card_id=200, title="Below Threshold", composite_score=0.74
    )

    created_link = _make_link(10, stream.card_id, 100)

    with (
        patch.object(ZettelkastenService, "ensure_embedding", side_effect=lambda card: card),
        patch.object(
            ZettelkastenService, "suggest_links", return_value=[at_threshold, below_threshold]
        ),
        patch.object(
            ZettelkastenService,
            "create_link",
            return_value=[created_link],
        ) as mock_create_link,
    ):
        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    # links_found should list both suggestions
    links_data = next(d for n, d in parsed if n == "links_found")
    assert len(links_data["suggestions"]) == 2

    # Only the at-threshold card should be auto-linked
    assert "links_created" in event_names
    created_data = next(d for n, d in parsed if n == "links_created")
    target_ids = [link["target_id"] for link in created_data["links"]]
    assert 100 in target_ids

    # create_link should only have been called once (for score 0.75, not 0.74)
    mock_create_link.assert_called_once()
    call_kwargs = mock_create_link.call_args
    assert call_kwargs.kwargs["to_card_id"] == 100


@pytest.mark.asyncio
async def test_track_a_error_emits_error_event(db_session):
    """If ensure_embedding raises, Track A should emit an error event, not crash."""
    payload = ZettelCardCreate(title="Error Card", content="Will fail embedding")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    with patch.object(
        ZettelkastenService,
        "ensure_embedding",
        side_effect=RuntimeError("Qdrant unreachable"),
    ):
        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "error" in event_names
    error_data = next(d for n, d in parsed if n == "error")
    assert error_data["step"] == "track_a"
    assert "Qdrant unreachable" in error_data["message"]


@pytest.mark.asyncio
async def test_track_a_no_card_id():
    """Track A without Phase 0 should emit error about missing card_id."""
    payload = ZettelCardCreate(title="No Phase 0", content="Skipped save")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    # Do NOT run Phase 0 — card_id stays None
    assert stream.card_id is None

    events = []
    async for sse in stream.run_track_a():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert data["step"] == "track_a"
    assert "Phase 0" in data["message"]


# ---------------------------------------------------------------------------
# Track B tests
# ---------------------------------------------------------------------------

# Mock helpers for OpenAI streaming


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


VALID_ANALYSIS_JSON = json.dumps(
    {
        "enrichment": {
            "suggested_title": "Better Title",
            "summary": "A concise summary.",
            "suggested_tags": ["ai", "ml"],
            "suggested_topic": "AI Engineering",
        },
        "decomposition": {
            "is_atomic": True,
            "reason": "Single concept covered.",
            "suggested_cards": [],
        },
        "gaps": {
            "missing_topics": ["reinforcement learning"],
            "weak_areas": [{"topic": "NLP", "existing_count": 2, "note": "Could use more depth"}],
        },
    }
)


def _mock_openai_client(chunks):
    """Build a mock AsyncOpenAI client whose chat.completions.create returns a MockStream."""
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=MockStream(chunks))
    return mock_client


@pytest.mark.asyncio
async def test_track_b_emits_thinking_and_enrichment(db_session):
    """Track B should emit thinking, enrichment, decomposition, and gaps events."""
    payload = ZettelCardCreate(title="Track B Card", content="Deep learning fundamentals")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # Phase 0: save the card first
    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    # Build mock chunks: reasoning tokens then completion tokens
    chunks = [
        MockStreamChunk(reasoning="Let me analyze this card..."),
        MockStreamChunk(reasoning="Checking knowledge base context..."),
        MockStreamChunk(content=VALID_ANALYSIS_JSON[:50]),
        MockStreamChunk(content=VALID_ANALYSIS_JSON[50:]),
    ]
    mock_client = _mock_openai_client(chunks)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run_track_b():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "thinking" in event_names
    assert "enrichment" in event_names
    assert "decomposition" in event_names
    assert "gaps" in event_names

    # Verify thinking content
    thinking_events = [d for n, d in parsed if n == "thinking"]
    assert len(thinking_events) == 2
    assert "analyze" in thinking_events[0]["content"]

    # Verify enrichment data
    enrichment_data = next(d for n, d in parsed if n == "enrichment")
    assert enrichment_data["suggested_title"] == "Better Title"
    assert "ai" in enrichment_data["suggested_tags"]


@pytest.mark.asyncio
async def test_track_b_error_emits_error_event(db_session):
    """If the OpenAI client raises, Track B should emit an error event."""
    payload = ZettelCardCreate(title="Error Card B", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API key invalid"))

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        events = []
        async for sse in stream.run_track_b():
            events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert data["step"] == "track_b"
    assert "API key invalid" in data["message"]


@pytest.mark.asyncio
async def test_track_b_no_card_id():
    """Track B without Phase 0 should emit error about missing card_id."""
    payload = ZettelCardCreate(title="No Phase 0 B", content="Skipped save")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    assert stream.card_id is None

    events = []
    async for sse in stream.run_track_b():
        events.append(sse)

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert data["step"] == "track_b"
    assert "Phase 0" in data["message"]


def test_parse_analysis_response_valid_json():
    """_parse_analysis_response should return enrichment, decomposition, gaps events."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    events = stream._parse_analysis_response(VALID_ANALYSIS_JSON)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert len(parsed) == 3
    assert "enrichment" in event_names
    assert "decomposition" in event_names
    assert "gaps" in event_names


def test_parse_analysis_response_markdown_fences():
    """JSON wrapped in markdown fences should still parse."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    fenced = f"```json\n{VALID_ANALYSIS_JSON}\n```"
    events = stream._parse_analysis_response(fenced)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert len(parsed) == 3
    assert "enrichment" in event_names
    assert "decomposition" in event_names
    assert "gaps" in event_names


def test_parse_analysis_response_garbage():
    """Non-JSON input should return an error event."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    events = stream._parse_analysis_response("this is not json at all {{{")

    parsed = _parse_sse_events(events)
    assert len(parsed) == 1
    event_name, data = parsed[0]
    assert event_name == "error"
    assert data["step"] == "track_b_parse"
    assert "Failed to parse" in data["message"]


def test_parse_analysis_response_partial_keys():
    """JSON missing 'gaps' key should return events for present keys only."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    partial = json.dumps(
        {
            "enrichment": {
                "suggested_title": None,
                "summary": "A summary.",
                "suggested_tags": ["tag1"],
                "suggested_topic": None,
            },
            "decomposition": {
                "is_atomic": True,
                "reason": "Single idea.",
                "suggested_cards": [],
            },
            # Note: no "gaps" key
        }
    )
    events = stream._parse_analysis_response(partial)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert len(parsed) == 2
    assert "enrichment" in event_names
    assert "decomposition" in event_names
    assert "gaps" not in event_names


# ---------------------------------------------------------------------------
# Full pipeline tests (Phase 0 + concurrent Phase 1 + Phase 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_emits_card_saved_first_and_done_last(db_session):
    """Full pipeline: card_saved is first event, done is last, with enrichment in between."""
    payload = ZettelCardCreate(title="Pipeline Card", content="Full pipeline test content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # Mock Track A: embedding + empty suggestions
    mock_embed = patch.object(
        ZettelkastenService, "ensure_embedding", side_effect=lambda card: card
    )
    mock_suggest = patch.object(ZettelkastenService, "suggest_links", return_value=[])

    # Mock Track B: OpenAI streaming with valid JSON
    chunks = [
        MockStreamChunk(reasoning="Analyzing..."),
        MockStreamChunk(content=VALID_ANALYSIS_JSON),
    ]
    mock_client = _mock_openai_client(chunks)

    with (
        mock_embed,
        mock_suggest,
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
    event_names = [e[0] for e in parsed]

    # card_saved must be first
    assert event_names[0] == "card_saved"

    # done must be last
    assert event_names[-1] == "done"

    # done should contain final card info
    done_data = parsed[-1][1]
    assert done_data["card"]["id"] is not None
    assert done_data["card"]["title"] == "Pipeline Card"
    assert done_data["stats"]["card_id"] is not None

    # Phase 1 events should be present between card_saved and done
    assert "embedding_done" in event_names
    assert "links_found" in event_names
    assert "thinking" in event_names
    assert "enrichment" in event_names


@pytest.mark.asyncio
async def test_full_pipeline_both_tracks_error(db_session):
    """Both tracks erroring should still produce card_saved first and done last with card info."""
    payload = ZettelCardCreate(title="Error Pipeline Card", content="Both tracks fail")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # Mock Track A: ensure_embedding raises
    mock_embed = patch.object(
        ZettelkastenService,
        "ensure_embedding",
        side_effect=RuntimeError("Qdrant down"),
    )

    # Mock Track B: OpenAI client raises
    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("API quota exceeded"))

    with (
        mock_embed,
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
    event_names = [e[0] for e in parsed]

    # card_saved must still be first (Phase 0 succeeded)
    assert event_names[0] == "card_saved"

    # done must be last
    assert event_names[-1] == "done"

    # Two error events from the tracks
    error_events = [(n, d) for n, d in parsed if n == "error"]
    assert len(error_events) == 2
    error_steps = {d["step"] for _, d in error_events}
    assert "track_a" in error_steps
    assert "track_b" in error_steps

    # done event should still contain the card info
    done_data = parsed[-1][1]
    assert done_data["card"]["id"] is not None
    assert done_data["card"]["title"] == "Error Pipeline Card"
