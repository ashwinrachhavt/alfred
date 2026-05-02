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
    ZettelSession,
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


def test_parse_structured_json_valid_json():
    """Base-class _parse_structured_json returns a dict for valid JSON."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    data = stream._parse_structured_json(VALID_ANALYSIS_JSON)
    assert data is not None
    assert "enrichment" in data
    assert "decomposition" in data
    assert "gaps" in data


def test_parse_structured_json_markdown_fences():
    """JSON wrapped in markdown fences should still parse via the base class."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    fenced = f"```json\n{VALID_ANALYSIS_JSON}\n```"
    data = stream._parse_structured_json(fenced)
    assert data is not None
    assert "enrichment" in data
    assert "decomposition" in data
    assert "gaps" in data


def test_parse_structured_json_garbage_returns_none():
    """Non-JSON input should return None; track_b will emit an error event."""
    payload = ZettelCardCreate(title="Test", content="Test")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: MagicMock())

    data = stream._parse_structured_json("this is not json at all {{{")
    assert data is None


def test_parse_structured_json_partial_keys():
    """JSON missing a key is still valid; track_b emits only present events."""
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
    data = stream._parse_structured_json(partial)
    assert data is not None
    assert "enrichment" in data
    assert "decomposition" in data
    assert "gaps" not in data


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


# ---------------------------------------------------------------------------
# T4 additions: Bloom inference + session-context + _sse re-export
# ---------------------------------------------------------------------------


VALID_ANALYSIS_JSON_WITH_BLOOM = json.dumps(
    {
        "enrichment": {
            "suggested_title": None,
            "summary": "A concise summary.",
            "suggested_tags": ["ai"],
            "suggested_topic": None,
        },
        "decomposition": {
            "is_atomic": True,
            "reason": "Single concept.",
            "suggested_cards": [],
        },
        "gaps": {"missing_topics": [], "weak_areas": []},
        "bloom_assessment": {
            "inferred_level": 4,
            "rationale": "The card compares and decomposes ideas into parts.",
            "evidence_phrases": ["parts", "compare"],
        },
    }
)


@pytest.mark.asyncio
async def test_track_b_emits_bloom_inferred_event(db_session):
    """Track B should emit a bloom_inferred event when bloom_assessment is present."""
    payload = ZettelCardCreate(title="Bloom Card", content="Comparing ideas into parts")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    chunks = [
        MockStreamChunk(reasoning="Thinking about Bloom..."),
        MockStreamChunk(content=VALID_ANALYSIS_JSON_WITH_BLOOM),
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

    assert "bloom_inferred" in event_names
    bloom_event = next(d for n, d in parsed if n == "bloom_inferred")
    assert bloom_event["level"] == 4
    assert bloom_event["source"] == "ai_inferred"
    assert bloom_event["card_id"] == stream.card_id
    assert "parts" in bloom_event["evidence_phrases"]


@pytest.mark.asyncio
async def test_bloom_inference_does_not_mutate_updated_at(db_session):
    """Iron-rule regression: persisting Bloom must NOT bump updated_at."""
    payload = ZettelCardCreate(title="Update At Card", content="Initial content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    # Capture the original updated_at *before* any Bloom write.
    original = db_session.get(ZettelCard, stream.card_id)
    assert original is not None
    original_ts = original.updated_at
    assert original_ts is not None

    chunks = [
        MockStreamChunk(content=VALID_ANALYSIS_JSON_WITH_BLOOM),
    ]
    mock_client = _mock_openai_client(chunks)

    with (
        patch("alfred.core.redis_client.get_redis_client", return_value=None),
        patch(
            "alfred.core.llm_factory.get_async_openai_client",
            return_value=mock_client,
        ),
    ):
        async for _ in stream.run_track_b():
            pass

    # Force a read straight from the DB (not the cached identity-map object).
    db_session.expire_all()
    refetched = db_session.get(ZettelCard, stream.card_id)
    assert refetched is not None
    assert refetched.bloom_level == 4
    assert refetched.bloom_source == "ai_inferred"
    # The iron rule: updated_at is unchanged.
    assert refetched.updated_at == original_ts
    # And the history got the new entry.
    assert refetched.bloom_history is not None
    assert any(entry.get("level") == 4 for entry in refetched.bloom_history)


@pytest.mark.asyncio
async def test_track_b_parses_without_bloom_assessment_gracefully(db_session):
    """No bloom_assessment in the response must NOT crash, and must NOT emit bloom_inferred."""
    payload = ZettelCardCreate(title="No Bloom Card", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    # Use the existing VALID_ANALYSIS_JSON which has no bloom_assessment.
    chunks = [MockStreamChunk(content=VALID_ANALYSIS_JSON)]
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

    assert "enrichment" in event_names
    assert "decomposition" in event_names
    assert "gaps" in event_names
    assert "bloom_inferred" not in event_names


@pytest.mark.asyncio
async def test_track_b_parse_error_emits_error_event(db_session):
    """Garbage OpenAI output should emit an error SSE event with step=track_b_parse."""
    payload = ZettelCardCreate(title="Garbage Card", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass
    assert stream.card_id is not None

    chunks = [MockStreamChunk(content="this is not json at all {{{")]
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
    error_events = [(n, d) for n, d in parsed if n == "error"]
    assert len(error_events) == 1
    _, err = error_events[0]
    assert err["step"] == "track_b_parse"


@pytest.mark.asyncio
async def test_session_context_injection_when_session_id_present(db_session):
    """If payload has session_id, sibling titles appear in the Track B prompt."""
    # Seed two pre-existing cards in session 7 via the ORM (bypass the service
    # to avoid embedding sync noise in tests).
    sess = ZettelSession(title="Working Session")
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)

    for title in ("Sibling One", "Sibling Two"):
        db_session.add(ZettelCard(title=title, session_id=sess.id))
    db_session.commit()

    payload = ZettelCardCreate(
        title="New Card With Session",
        content="Content",
        session_id=sess.id,
    )
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # _fetch_session_sibling_titles reads from the DB directly.
    titles = stream._fetch_session_sibling_titles()
    assert set(titles) == {"Sibling One", "Sibling Two"}

    # Build the prompt with those siblings — user message must mention them.
    messages = stream._build_analysis_prompt({"total_cards": 0, "topics": []}, titles)
    user_msg = messages[1]["content"]
    assert "sibling cards" in user_msg
    assert "Sibling One" in user_msg
    assert "Sibling Two" in user_msg


def test_session_context_omitted_when_session_id_none(db_session):
    """Without a session_id the prompt gets no sibling-card hint."""
    payload = ZettelCardCreate(title="Solo Card", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    assert stream._fetch_session_sibling_titles() == []

    messages = stream._build_analysis_prompt({"total_cards": 0, "topics": []}, [])
    user_msg = messages[1]["content"]
    assert "sibling cards" not in user_msg
    assert "alongside" not in user_msg


def test_sse_function_reexport_preserved():
    """`from alfred.services.zettel_creation_stream import _sse` must still work."""
    # _sse was imported at the top of the file; re-invoke to confirm behavior.
    result = _sse("my_event", {"a": 1})
    assert result == 'event: my_event\ndata: {"a": 1}\n\n'


@pytest.mark.asyncio
async def test_zettel_creation_stream_touches_session_on_card_save(db_session):
    """Phase 0 must bump ZettelSession.updated_at when payload.session_id is set.

    Without this, the T8 abandon-stale-sessions beat would mark newly
    created sessions as abandoned 24h after creation even if the user
    is actively writing cards into them.
    """
    from datetime import timedelta

    from alfred.core.utils import utcnow_naive

    sess = ZettelSession(title="Live session")
    db_session.add(sess)
    db_session.commit()
    db_session.refresh(sess)
    assert sess.id is not None

    # Backdate updated_at so the touch is detectable at coarse timestamp
    # resolutions (e.g., SQLite's second precision under certain adapters).
    backdated = utcnow_naive() - timedelta(minutes=5)
    sess.updated_at = backdated
    db_session.add(sess)
    db_session.commit()

    payload = ZettelCardCreate(
        title="Touch me",
        content="content",
        session_id=sess.id,
    )
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    events = []
    async for sse in stream.run_phase0():
        events.append(sse)

    db_session.expire_all()
    refetched = db_session.get(ZettelSession, sess.id)
    assert refetched is not None
    assert refetched.updated_at is not None
    assert refetched.updated_at > backdated
