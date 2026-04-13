# Streaming Zettel Creation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform zettel creation from a dead POST+spinner into a streaming SSE experience that shows AI reasoning, auto-generates embeddings, finds links, enriches content, detects decomposition opportunities, and surfaces knowledge gaps — all in real-time inside a modal.

**Architecture:** New SSE endpoint (`POST /api/zettels/cards/create-stream`) orchestrated by `ZettelCreationStream` service. Phase 0 saves the card immediately (~50ms). Phase 1 runs two concurrent async tracks: Track A (embed, Qdrant sync, vector search, auto-link) and Track B (o4-mini reasoning + enrichment/decomposition/gaps). Phase 2 finalizes with cache invalidation and a `done` event. Frontend modal consumes the SSE stream via the existing `streamSSE` utility.

**Tech Stack:** Python 3.12, FastAPI (async), `openai.AsyncOpenAI` for o4-mini streaming, SQLModel, Qdrant, React 19, Zustand, shadcn/ui, TanStack React Query.

**Spec:** `docs/superpowers/specs/2026-04-12-streaming-zettel-creation-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|----------------|
| `apps/alfred/utils/async_merge.py` | `merge_async_generators()` merges N async generators into one, yielding from whichever is ready first |
| `apps/alfred/services/zettel_creation_stream.py` | `ZettelCreationStream` orchestrator: Phase 0/1/2 pipeline, Track A linking chain, Track B AI analysis |
| `apps/alfred/api/zettels/stream_routes.py` | SSE endpoint `POST /cards/create-stream`, mounts on existing zettel router |
| `web/lib/stores/zettel-creation-store.ts` | Zustand store for streaming modal state: events, selections, thinking buffer |
| `web/app/(app)/knowledge/_components/streaming-creation-modal.tsx` | Streaming creation modal component: progress timeline, thinking block, enrichment suggestions |
| `tests/alfred/utils/test_async_merge.py` | Tests for merge utility |
| `tests/alfred/services/test_zettel_creation_stream.py` | Tests for orchestrator service |
| `tests/alfred/api/zettels/test_stream_routes.py` | Integration tests for SSE endpoint |

### Modified Files

| File | Change |
|------|--------|
| `apps/alfred/api/zettels/routes.py` | Import and include `stream_router` |
| `web/lib/api/routes.ts` | Add `createStream` to `zettels` routes |
| `web/lib/api/zettels.ts` | Add `createZettelStream()` SSE client function |
| `web/features/zettels/mutations.ts` | Add `useCreateZettelStream` hook |
| `web/app/(app)/knowledge/_components/create-zettel-dialog.tsx` | Wire streaming modal into existing create flow |

---

## Task 1: Async Merge Utility

**Files:**
- Create: `apps/alfred/utils/__init__.py`
- Create: `apps/alfred/utils/async_merge.py`
- Create: `tests/alfred/utils/__init__.py`
- Create: `tests/alfred/utils/test_async_merge.py`

- [ ] **Step 1: Write the test file**

```python
# tests/alfred/utils/__init__.py
# (empty)
```

```python
# tests/alfred/utils/test_async_merge.py
"""Tests for merge_async_generators utility."""

from __future__ import annotations

import asyncio

import pytest

from alfred.utils.async_merge import merge_async_generators


async def _gen_items(items: list[tuple[float, str]]):
    """Yield items with delays to simulate async work."""
    for delay, value in items:
        await asyncio.sleep(delay)
        yield value


@pytest.mark.asyncio
async def test_merge_single_generator():
    gen = _gen_items([(0, "a"), (0, "b"), (0, "c")])
    results = [item async for item in merge_async_generators(gen)]
    assert results == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_merge_two_generators_interleaved():
    """Two generators with different delays should interleave."""
    fast = _gen_items([(0.01, "fast1"), (0.01, "fast2"), (0.01, "fast3")])
    slow = _gen_items([(0.05, "slow1")])
    results = [item async for item in merge_async_generators(fast, slow)]
    # fast items arrive before slow
    assert results.index("fast1") < results.index("slow1")
    assert len(results) == 4


@pytest.mark.asyncio
async def test_merge_empty_generators():
    async def empty():
        return
        yield  # noqa: unreachable - makes it an async generator

    results = [item async for item in merge_async_generators(empty(), empty())]
    assert results == []


@pytest.mark.asyncio
async def test_merge_one_empty_one_full():
    async def empty():
        return
        yield

    full = _gen_items([(0, "a"), (0, "b")])
    results = [item async for item in merge_async_generators(empty(), full)]
    assert results == ["a", "b"]


@pytest.mark.asyncio
async def test_merge_generator_exception_propagates():
    async def failing():
        yield "ok"
        raise ValueError("boom")

    gen = _gen_items([(0, "a")])
    with pytest.raises(ValueError, match="boom"):
        _ = [item async for item in merge_async_generators(failing(), gen)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/utils/test_async_merge.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfred.utils'`

- [ ] **Step 3: Write the implementation**

```python
# apps/alfred/utils/__init__.py
# (empty)
```

```python
# apps/alfred/utils/async_merge.py
"""Merge multiple async generators into a single stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator


async def merge_async_generators(*gens: AsyncGenerator) -> AsyncGenerator:
    """Merge N async generators, yielding from whichever produces a value first.

    If any generator raises an exception, it propagates immediately and
    remaining generators are cancelled.
    """
    queue: asyncio.Queue[tuple[bool, object]] = asyncio.Queue()
    # (is_sentinel, value_or_exception)

    async def _feed(gen: AsyncGenerator) -> None:
        try:
            async for item in gen:
                await queue.put((False, item))
        except Exception as exc:
            await queue.put((False, exc))
            raise
        finally:
            await queue.put((True, None))  # sentinel

    tasks = [asyncio.create_task(_feed(g)) for g in gens]
    done_count = 0
    try:
        while done_count < len(gens):
            is_sentinel, value = await queue.get()
            if is_sentinel:
                done_count += 1
            elif isinstance(value, Exception):
                raise value
            else:
                yield value
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/utils/test_async_merge.py -v`
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/utils/__init__.py apps/alfred/utils/async_merge.py tests/alfred/utils/__init__.py tests/alfred/utils/test_async_merge.py
git commit -m "feat: add merge_async_generators utility for concurrent SSE streams"
```

---

## Task 2: ZettelCreationStream Service Phase 0 (Card Save)

**Files:**
- Create: `apps/alfred/services/zettel_creation_stream.py`
- Create: `tests/alfred/services/test_zettel_creation_stream.py`

- [ ] **Step 1: Write the test for Phase 0**

```python
# tests/alfred/services/test_zettel_creation_stream.py
"""Tests for ZettelCreationStream orchestrator."""

from __future__ import annotations

import asyncio
import json

import pytest

from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettel_creation_stream import ZettelCreationStream


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
    from alfred.models.zettel import ZettelCard

    payload = ZettelCardCreate(title="Persisted Card", content="Content here")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    card = db_session.get(ZettelCard, stream.card_id)
    assert card is not None
    assert card.title == "Persisted Card"
    assert card.content == "Content here"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py::test_phase0_emits_card_saved -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfred.services.zettel_creation_stream'`

- [ ] **Step 3: Write the Phase 0 implementation**

```python
# apps/alfred/services/zettel_creation_stream.py
"""Streaming zettel creation orchestrator.

Saves a card immediately, then runs two concurrent async tracks:
  Track A: embedding + Qdrant sync + vector search + auto-link
  Track B: o4-mini reasoning + enrichment + decomposition + gaps

Yields SSE-formatted strings for each event.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any, Callable

from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _sse(event: str, data: dict[str, Any]) -> str:
    """Format a single SSE event."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


class ZettelCreationStream:
    """Orchestrates streaming zettel creation with concurrent enrichment."""

    def __init__(
        self,
        payload: ZettelCardCreate,
        db_session_factory: Callable[[], Session] | None = None,
    ) -> None:
        self.payload = payload
        self._db_factory = db_session_factory or (lambda: next(get_db_session()))
        self.card_id: int | None = None
        self._card_title: str = ""

    def _save_card(self) -> dict[str, Any]:
        """Synchronous card save. Runs in executor."""
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            card = svc.create_card(**self.payload.model_dump())
            self.card_id = card.id
            self._card_title = card.title
            return {"id": card.id, "title": card.title, "status": card.status}
        finally:
            session.close()

    async def run_phase0(self) -> AsyncGenerator[str, None]:
        """Phase 0: save the card to DB and emit card_saved."""
        result = await asyncio.to_thread(self._save_card)
        yield _sse("card_saved", result)

    async def run(self) -> AsyncGenerator[str, None]:
        """Full pipeline: Phase 0 then Phase 1 (concurrent tracks) then Phase 2."""
        # Phase 0
        async for event in self.run_phase0():
            yield event

        # Phase 1 and 2 will be added in subsequent tasks
        yield _sse("done", {"card_id": self.card_id, "stats": {}})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/zettel_creation_stream.py tests/alfred/services/test_zettel_creation_stream.py
git commit -m "feat: add ZettelCreationStream Phase 0 with immediate card save and SSE"
```

---

## Task 3: ZettelCreationStream Track A (Linking Chain)

**Files:**
- Modify: `apps/alfred/services/zettel_creation_stream.py`
- Modify: `tests/alfred/services/test_zettel_creation_stream.py`

- [ ] **Step 1: Write the test for Track A**

Add to `tests/alfred/services/test_zettel_creation_stream.py`:

```python
from unittest.mock import MagicMock, patch


@pytest.mark.asyncio
async def test_track_a_emits_embedding_and_links(db_session):
    """Track A should embed, search, and emit link events."""
    payload = ZettelCardCreate(title="Consensus Algorithms", content="Raft and PBFT comparison")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    # Phase 0 first to get card_id
    async for _ in stream.run_phase0():
        pass

    mock_embedding = [0.1] * 1536

    with patch.object(ZettelkastenService, "embed_card", return_value=mock_embedding), \
         patch.object(ZettelkastenService, "_try_sync_card_to_vector_index"), \
         patch.object(ZettelkastenService, "suggest_links") as mock_suggest, \
         patch.object(ZettelkastenService, "create_link", return_value=[]):
        mock_link_suggestion = MagicMock()
        mock_link_suggestion.to_card_id = 99
        mock_link_suggestion.to_title = "Raft Leader Election"
        mock_link_suggestion.scores = MagicMock()
        mock_link_suggestion.scores.composite_score = 0.91
        mock_link_suggestion.reason = "91% semantic similarity"
        mock_suggest.return_value = [mock_link_suggestion]

        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "embedding_done" in event_names
    assert "tool_start" in event_names
    assert "links_found" in event_names


@pytest.mark.asyncio
async def test_track_a_error_emits_error_event(db_session):
    """If embedding fails, Track A should emit an error event, not crash."""
    payload = ZettelCardCreate(title="Error Test", content="Some content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    with patch.object(ZettelkastenService, "embed_card", side_effect=RuntimeError("Qdrant down")):
        events = []
        async for sse in stream.run_track_a():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]
    assert "error" in event_names
    error_data = next(d for n, d in parsed if n == "error")
    assert "step" in error_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py::test_track_a_emits_embedding_and_links -v`
Expected: FAIL with `AttributeError: 'ZettelCreationStream' object has no attribute 'run_track_a'`

- [ ] **Step 3: Implement Track A**

Add to `ZettelCreationStream` class in `apps/alfred/services/zettel_creation_stream.py`:

```python
    AUTO_LINK_THRESHOLD = 0.75

    async def run_track_a(self) -> AsyncGenerator[str, None]:
        """Track A: embed then sync Qdrant then search similar then auto-link."""
        if self.card_id is None:
            yield _sse("error", {"step": "track_a", "message": "No card_id. Phase 0 must run first"})
            return

        try:
            embedding, card = await asyncio.to_thread(self._embed_card)
            yield _sse("embedding_done", {"card_id": self.card_id})

            await asyncio.to_thread(self._sync_to_qdrant, card, embedding)

            yield _sse("tool_start", {"step": "searching_kb"})
            suggestions = await asyncio.to_thread(self._find_suggestions)

            suggestion_data = [
                {
                    "card_id": s.to_card_id,
                    "title": s.to_title,
                    "score": round(s.scores.composite_score, 2),
                    "reason": s.reason,
                }
                for s in suggestions
            ]
            yield _sse("links_found", {"suggestions": suggestion_data})

            auto_linked = await asyncio.to_thread(self._auto_create_links, suggestions)
            if auto_linked:
                yield _sse("links_created", {"links": auto_linked})

        except Exception as exc:
            logger.warning("Track A failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield _sse("error", {"step": "track_a", "message": str(exc)})

    def _embed_card(self) -> tuple[list[float], Any]:
        """Generate embedding and persist it. Returns (embedding, card)."""
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            from alfred.models.zettel import ZettelCard

            card = session.get(ZettelCard, self.card_id)
            if not card:
                raise ValueError(f"Card {self.card_id} not found")
            embedding = svc.embed_card(card)
            card.embedding = embedding
            session.add(card)
            session.commit()
            session.refresh(card)
            return embedding, card
        finally:
            session.close()

    def _sync_to_qdrant(self, card: Any, embedding: list[float]) -> None:
        """Sync card to Qdrant vector index."""
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            from alfred.models.zettel import ZettelCard

            fresh_card = session.get(ZettelCard, self.card_id)
            if fresh_card:
                svc._try_sync_card_to_vector_index(fresh_card, embedding=embedding)
        finally:
            session.close()

    def _find_suggestions(self) -> list:
        """Find similar cards via vector search."""
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            return svc.suggest_links(self.card_id, min_confidence=0.6, limit=10)
        finally:
            session.close()

    def _auto_create_links(self, suggestions: list) -> list[dict]:
        """Auto-create links for suggestions above threshold."""
        session = self._db_factory()
        try:
            svc = ZettelkastenService(session)
            created = []
            for s in suggestions:
                if s.scores.composite_score >= self.AUTO_LINK_THRESHOLD:
                    links = svc.create_link(
                        from_card_id=self.card_id,
                        to_card_id=s.to_card_id,
                        type="auto_stream",
                        context=s.reason,
                        bidirectional=True,
                    )
                    for link in links:
                        created.append({
                            "id": link.id,
                            "source_id": link.from_card_id,
                            "target_id": link.to_card_id,
                            "type": link.type,
                        })
            return created
        finally:
            session.close()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/zettel_creation_stream.py tests/alfred/services/test_zettel_creation_stream.py
git commit -m "feat: add Track A embedding, Qdrant sync, link suggestion, auto-link"
```

---

## Task 4: ZettelCreationStream Track B (AI Analysis)

**Files:**
- Modify: `apps/alfred/services/zettel_creation_stream.py`
- Modify: `tests/alfred/services/test_zettel_creation_stream.py`

- [ ] **Step 1: Write the test for Track B**

Add to `tests/alfred/services/test_zettel_creation_stream.py`:

```python
@pytest.mark.asyncio
async def test_track_b_emits_thinking_and_enrichment(db_session):
    """Track B should stream thinking tokens and emit enrichment/gaps events."""
    payload = ZettelCardCreate(title="PBFT Consensus", content="Byzantine fault tolerance overview")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    mock_response_json = json.dumps({
        "enrichment": {
            "suggested_title": "PBFT: Byzantine Fault Tolerance Consensus",
            "summary": "Overview of practical Byzantine fault tolerance",
            "suggested_tags": ["consensus", "bft"],
            "suggested_topic": "distributed-systems",
        },
        "decomposition": {
            "is_atomic": True,
            "reason": "Content covers a single concept",
            "suggested_cards": [],
        },
        "gaps": {
            "missing_topics": ["raft", "paxos"],
            "weak_areas": [{"topic": "consensus", "existing_count": 1, "note": "Only 1 card"}],
        },
    })

    async def mock_stream_create(*args, **kwargs):
        class MockChunk:
            def __init__(self, content=None, reasoning=None, finish_reason=None):
                self.choices = [MagicMock()]
                self.choices[0].delta = MagicMock()
                self.choices[0].delta.content = content
                self.choices[0].delta.reasoning_content = reasoning
                self.choices[0].finish_reason = finish_reason

        class MockStream:
            def __init__(self):
                self.chunks = [
                    MockChunk(reasoning="Analyzing the card about PBFT..."),
                    MockChunk(reasoning=" The user has few cards on consensus."),
                    MockChunk(content=mock_response_json),
                    MockChunk(finish_reason="stop"),
                ]
                self._index = 0

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._index >= len(self.chunks):
                    raise StopAsyncIteration
                chunk = self.chunks[self._index]
                self._index += 1
                return chunk

        return MockStream()

    with patch("alfred.services.zettel_creation_stream._make_client") as mock_make:
        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_stream_create
        mock_make.return_value = mock_client

        with patch.object(stream, "_fetch_kb_context", return_value={"total_cards": 5, "topics": [{"topic": "cs", "count": 3}]}):
            events = []
            async for sse in stream.run_track_b():
                events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert "thinking" in event_names
    assert "enrichment" in event_names
    assert "gaps" in event_names


@pytest.mark.asyncio
async def test_track_b_error_emits_error_event(db_session):
    """If the LLM call fails, Track B should emit an error event, not crash."""
    payload = ZettelCardCreate(title="Error Test B", content="Content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    async for _ in stream.run_phase0():
        pass

    with patch("alfred.services.zettel_creation_stream._make_client", side_effect=RuntimeError("API key invalid")):
        with patch.object(stream, "_fetch_kb_context", return_value={"total_cards": 0, "topics": []}):
            events = []
            async for sse in stream.run_track_b():
                events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]
    assert "error" in event_names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py::test_track_b_emits_thinking_and_enrichment -v`
Expected: FAIL with `AttributeError: 'ZettelCreationStream' object has no attribute 'run_track_b'`

- [ ] **Step 3: Implement Track B**

Add these imports to the top of `apps/alfred/services/zettel_creation_stream.py`:

```python
from openai import AsyncOpenAI
from alfred.core.settings import settings
```

Add `_make_client` as a module-level function after the imports:

```python
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


ANALYSIS_MODEL = "o4-mini"
```

Add to the `ZettelCreationStream` class:

```python
    async def run_track_b(self) -> AsyncGenerator[str, None]:
        """Track B: o4-mini reasoning + enrichment + decomposition + gaps."""
        if self.card_id is None:
            yield _sse("error", {"step": "track_b", "message": "No card_id. Phase 0 must run first"})
            return

        try:
            context = await asyncio.to_thread(self._fetch_kb_context)
            messages = self._build_analysis_prompt(context)

            client = _make_client()
            completion_buffer = ""
            async with await client.chat.completions.create(
                model=ANALYSIS_MODEL,
                messages=messages,
                stream=True,
                max_completion_tokens=4096,
            ) as stream_response:
                async for chunk in stream_response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue

                    reasoning = getattr(delta, "reasoning_content", None)
                    if reasoning:
                        yield _sse("thinking", {"content": reasoning})

                    if delta.content:
                        completion_buffer += delta.content

                    if chunk.choices[0].finish_reason:
                        break

            if completion_buffer:
                for event in self._parse_analysis_response(completion_buffer):
                    yield event

        except Exception as exc:
            logger.warning("Track B failed for card %s: %s", self.card_id, exc, exc_info=True)
            yield _sse("error", {"step": "track_b", "message": str(exc)})

    def _fetch_kb_context(self) -> dict[str, Any]:
        """Fetch lightweight KB context for the AI prompt."""
        session = self._db_factory()
        try:
            from sqlalchemy import func as sa_func
            from sqlmodel import select
            from alfred.models.zettel import ZettelCard

            total = session.exec(
                select(sa_func.count()).select_from(ZettelCard).where(ZettelCard.status != "archived")
            ).one()

            topics_rows = session.exec(
                select(ZettelCard.topic, sa_func.count())
                .where(ZettelCard.topic.isnot(None), ZettelCard.status != "archived")
                .group_by(ZettelCard.topic)
                .order_by(sa_func.count().desc())
                .limit(30)
            ).all()

            return {
                "total_cards": total,
                "topics": [{"topic": t, "count": c} for t, c in topics_rows],
            }
        finally:
            session.close()

    def _build_analysis_prompt(self, context: dict[str, Any]) -> list[dict[str, str]]:
        """Build the o4-mini prompt for enrichment + decomposition + gaps."""
        topics_str = ", ".join(
            f"{t['topic']} ({t['count']})" for t in context.get("topics", [])
        ) or "none yet"

        system = (
            "You are a knowledge analyst for a Zettelkasten system. "
            "The user is creating a new knowledge card. Analyze it and provide "
            "enrichment, decomposition assessment, and knowledge gap analysis.\n\n"
            f"Knowledge base context:\n"
            f"- Total cards: {context.get('total_cards', 0)}\n"
            f"- Topics (with card counts): {topics_str}\n\n"
            "Respond ONLY with valid JSON (no markdown fences, no commentary):\n"
            '{\n'
            '  "enrichment": {\n'
            '    "suggested_title": "..." or null (only if meaningfully better),\n'
            '    "summary": "one-sentence distillation",\n'
            '    "suggested_tags": ["tag1", "tag2"],\n'
            '    "suggested_topic": "..." or null\n'
            '  },\n'
            '  "decomposition": {\n'
            '    "is_atomic": true/false,\n'
            '    "reason": "why or why not",\n'
            '    "suggested_cards": [{"title": "...", "content": "..."}]\n'
            '  },\n'
            '  "gaps": {\n'
            '    "missing_topics": ["topic1"],\n'
            '    "weak_areas": [{"topic": "...", "existing_count": N, "note": "..."}]\n'
            '  }\n'
            '}'
        )

        content_str = self.payload.content or ""
        tags_str = ", ".join(self.payload.tags or [])
        user = (
            f"New card being created:\n"
            f"Title: {self.payload.title}\n"
            f"Content: {content_str}\n"
            f"Tags: {tags_str}\n"
            f"Topic: {self.payload.topic or 'not set'}"
        )

        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _parse_analysis_response(self, raw: str) -> list[str]:
        """Parse the JSON response from o4-mini into SSE events."""
        events: list[str] = []
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[1:])
            if cleaned.endswith("```"):
                cleaned = "\n".join(cleaned.split("\n")[:-1])

            data = json.loads(cleaned)

            if "enrichment" in data:
                events.append(_sse("enrichment", data["enrichment"]))
            if "decomposition" in data:
                events.append(_sse("decomposition", data["decomposition"]))
            if "gaps" in data:
                events.append(_sse("gaps", data["gaps"]))

        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Failed to parse Track B response: %s", exc)
            events.append(_sse("error", {"step": "track_b_parse", "message": f"Failed to parse AI response: {exc}"}))

        return events
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py -v`
Expected: 6 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/zettel_creation_stream.py tests/alfred/services/test_zettel_creation_stream.py
git commit -m "feat: add Track B o4-mini reasoning, enrichment, decomposition, gap detection"
```

---

## Task 5: ZettelCreationStream Full Pipeline (Phase 1 + 2)

**Files:**
- Modify: `apps/alfred/services/zettel_creation_stream.py`
- Modify: `tests/alfred/services/test_zettel_creation_stream.py`

- [ ] **Step 1: Write the test for full pipeline**

Add to `tests/alfred/services/test_zettel_creation_stream.py`:

```python
@pytest.mark.asyncio
async def test_full_pipeline_emits_card_saved_first_and_done_last(db_session):
    """Full run() should emit card_saved first, done last, with events between."""
    payload = ZettelCardCreate(title="Full Pipeline Test", content="Test content")
    stream = ZettelCreationStream(payload, db_session_factory=lambda: db_session)

    mock_embedding = [0.1] * 1536

    with patch.object(ZettelkastenService, "embed_card", return_value=mock_embedding), \
         patch.object(ZettelkastenService, "_try_sync_card_to_vector_index"), \
         patch.object(ZettelkastenService, "suggest_links", return_value=[]), \
         patch("alfred.services.zettel_creation_stream._make_client") as mock_make:

        mock_response_json = '{"enrichment":{"suggested_title":null,"summary":"Test","suggested_tags":[],"suggested_topic":null},"decomposition":{"is_atomic":true,"reason":"ok","suggested_cards":[]},"gaps":{"missing_topics":[],"weak_areas":[]}}'

        async def mock_stream_create(*args, **kwargs):
            class MockChunk:
                def __init__(self, content=None, finish_reason=None):
                    self.choices = [MagicMock()]
                    self.choices[0].delta = MagicMock()
                    self.choices[0].delta.content = content
                    self.choices[0].delta.reasoning_content = None
                    self.choices[0].finish_reason = finish_reason

            class MockStream:
                async def __aenter__(self):
                    return self
                async def __aexit__(self, *args):
                    pass
                def __aiter__(self):
                    return self
                async def __anext__(self):
                    if not hasattr(self, "_sent"):
                        self._sent = True
                        return MockChunk(content=mock_response_json)
                    if not hasattr(self, "_done"):
                        self._done = True
                        return MockChunk(finish_reason="stop")
                    raise StopAsyncIteration

            return MockStream()

        mock_client = MagicMock()
        mock_client.chat.completions.create = mock_stream_create
        mock_make.return_value = mock_client

        events = []
        async for sse in stream.run():
            events.append(sse)

    parsed = _parse_sse_events(events)
    event_names = [e[0] for e in parsed]

    assert event_names[0] == "card_saved"
    assert event_names[-1] == "done"
    assert len(event_names) >= 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py::test_full_pipeline_emits_card_saved_first_and_done_last -v`
Expected: FAIL because `run()` only emits `card_saved` and `done` without running tracks

- [ ] **Step 3: Update the `run()` method**

Replace the `run()` method in `apps/alfred/services/zettel_creation_stream.py`:

```python
    async def run(self) -> AsyncGenerator[str, None]:
        """Full pipeline: Phase 0 then Phase 1 (concurrent tracks) then Phase 2."""
        from alfred.utils.async_merge import merge_async_generators

        # Phase 0: save card
        async for event in self.run_phase0():
            yield event

        # Phase 1: run Track A and Track B concurrently, merge their events
        async for event in merge_async_generators(self.run_track_a(), self.run_track_b()):
            yield event

        # Phase 2: finalize
        await asyncio.to_thread(self._invalidate_caches)
        final_card = await asyncio.to_thread(self._fetch_final_card)
        yield _sse("done", {"card": final_card, "stats": {"card_id": self.card_id}})

    def _invalidate_caches(self) -> None:
        """Invalidate topic/tag/graph caches after creation."""
        try:
            from alfred.core.dependencies import get_redis

            redis = get_redis()
            if redis:
                for prefix in ("zettel:topics:", "zettel:tags:", "zettel:graph:"):
                    for key in redis.scan_iter(f"{prefix}*"):
                        redis.delete(key)
        except Exception:
            logger.debug("Cache invalidation failed (non-fatal)", exc_info=True)

    def _fetch_final_card(self) -> dict[str, Any]:
        """Fetch the final card state for the done event."""
        session = self._db_factory()
        try:
            from alfred.models.zettel import ZettelCard

            card = session.get(ZettelCard, self.card_id)
            if not card:
                return {"id": self.card_id}
            return {
                "id": card.id,
                "title": card.title,
                "content": card.content,
                "summary": card.summary,
                "tags": card.tags,
                "topic": card.topic,
                "status": card.status,
                "importance": card.importance,
                "confidence": card.confidence,
                "created_at": card.created_at.isoformat() if card.created_at else None,
                "updated_at": card.updated_at.isoformat() if card.updated_at else None,
            }
        finally:
            session.close()
```

- [ ] **Step 4: Run tests to verify all pass**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_creation_stream.py -v`
Expected: 7 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/zettel_creation_stream.py tests/alfred/services/test_zettel_creation_stream.py
git commit -m "feat: wire full streaming pipeline Phase 0 + concurrent tracks + finalize"
```

---

## Task 6: SSE Streaming Route

**Files:**
- Create: `apps/alfred/api/zettels/stream_routes.py`
- Modify: `apps/alfred/api/zettels/routes.py`
- Create: `tests/alfred/api/zettels/test_stream_routes.py`

- [ ] **Step 1: Write the test**

```python
# tests/alfred/api/zettels/test_stream_routes.py
"""Integration tests for the streaming zettel creation endpoint."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_stream_returns_sse(async_client: AsyncClient):
    """POST /api/zettels/cards/create-stream should return an SSE event stream."""

    async def mock_run(self):
        yield 'event: card_saved\ndata: {"id": 1, "title": "Test", "status": "active"}\n\n'
        yield 'event: done\ndata: {"card": {"id": 1}, "stats": {}}\n\n'

    with patch("alfred.api.zettels.stream_routes.ZettelCreationStream") as MockStream:
        instance = MockStream.return_value
        instance.run = lambda: mock_run(instance)

        response = await async_client.post(
            "/api/zettels/cards/create-stream",
            json={"title": "Test Card", "content": "Some content"},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]

    body = response.text
    assert "event: card_saved" in body
    assert "event: done" in body


@pytest.mark.asyncio
async def test_create_stream_rejects_empty_title(async_client: AsyncClient):
    """Should return 422 for missing/empty title."""
    response = await async_client.post(
        "/api/zettels/cards/create-stream",
        json={"content": "No title provided"},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/zettels/test_stream_routes.py -v`
Expected: FAIL with 404 (route not registered)

- [ ] **Step 3: Write the route and register it**

```python
# apps/alfred/api/zettels/stream_routes.py
"""SSE streaming endpoint for zettel creation with live enrichment."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.zettel import ZettelCardCreate
from alfred.services.zettel_creation_stream import ZettelCreationStream

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/cards/create-stream")
async def create_card_stream(
    payload: ZettelCardCreate,
    session: Session = Depends(get_db_session),
) -> StreamingResponse:
    """Create a zettel with streaming enrichment via SSE."""
    stream = ZettelCreationStream(payload)
    return StreamingResponse(
        stream.run(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )
```

In `apps/alfred/api/zettels/routes.py`, add after line 38 (`router = APIRouter(...)`):

```python
from alfred.api.zettels.stream_routes import router as stream_router
router.include_router(stream_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/zettels/test_stream_routes.py -v`
Expected: 2 PASSED

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/api/zettels/stream_routes.py apps/alfred/api/zettels/routes.py tests/alfred/api/zettels/test_stream_routes.py
git commit -m "feat: add SSE endpoint POST /api/zettels/cards/create-stream"
```

---

## Task 7: Frontend API Route + SSE Client

**Files:**
- Modify: `web/lib/api/routes.ts`
- Modify: `web/lib/api/zettels.ts`

- [ ] **Step 1: Add the route to `web/lib/api/routes.ts`**

Add after line 58 (the `generate` line) inside the `zettels` block:

```typescript
    createStream: "/api/zettels/cards/create-stream",
```

- [ ] **Step 2: Add SSE client function to `web/lib/api/zettels.ts`**

Add at the end of the file:

```typescript
import { streamSSE } from "@/lib/api/sse";

/**
 * Streaming zettel creation. Connects to the SSE endpoint and
 * calls onEvent for each event (card_saved, thinking, enrichment, etc.).
 */
export async function createZettelStream(
  payload: ZettelCardCreatePayload,
  onEvent: (event: string, data: Record<string, unknown>) => void,
  signal?: AbortSignal,
): Promise<void> {
  return streamSSE(apiRoutes.zettels.createStream, payload, onEvent, signal);
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors related to the new code

- [ ] **Step 4: Commit**

```bash
git add web/lib/api/routes.ts web/lib/api/zettels.ts
git commit -m "feat: add createZettelStream SSE client function"
```

---

## Task 8: Frontend Zustand Store

**Files:**
- Create: `web/lib/stores/zettel-creation-store.ts`

- [ ] **Step 1: Create the store**

```typescript
// web/lib/stores/zettel-creation-store.ts
import { create } from "zustand";

// --- Types ---

type StreamPhase = "idle" | "streaming" | "complete" | "error";

type LinkSuggestion = {
  card_id: number;
  title: string;
  score: number;
  reason: string;
};

type CreatedLink = {
  id: number;
  source_id: number;
  target_id: number;
  type: string;
};

type Enrichment = {
  suggested_title: string | null;
  summary: string | null;
  suggested_tags: string[];
  suggested_topic: string | null;
};

type Decomposition = {
  is_atomic: boolean;
  reason: string;
  suggested_cards: { title: string; content: string }[];
};

type Gaps = {
  missing_topics: string[];
  weak_areas: { topic: string; existing_count: number; note: string }[];
};

type CompletedSteps = {
  card_saved: boolean;
  embedding_done: boolean;
  links_searched: boolean;
  ai_complete: boolean;
};

// --- State ---

type ZettelCreationState = {
  phase: StreamPhase;
  cardId: number | null;
  cardTitle: string;

  thinkingBuffer: string;
  steps: CompletedSteps;

  enrichment: Enrichment | null;
  linkSuggestions: LinkSuggestion[];
  createdLinks: CreatedLink[];
  decomposition: Decomposition | null;
  gaps: Gaps | null;
  finalCard: Record<string, unknown> | null;

  acceptedEnrichments: Set<string>;
  rejectedLinkIds: Set<number>;
  errors: { step: string; message: string }[];
};

type ZettelCreationActions = {
  startStream: () => void;
  handleEvent: (event: string, data: Record<string, unknown>) => void;
  toggleEnrichment: (key: string) => void;
  toggleLink: (linkId: number) => void;
  reset: () => void;
};

// --- Initial State ---

const initialState: ZettelCreationState = {
  phase: "idle",
  cardId: null,
  cardTitle: "",
  thinkingBuffer: "",
  steps: {
    card_saved: false,
    embedding_done: false,
    links_searched: false,
    ai_complete: false,
  },
  enrichment: null,
  linkSuggestions: [],
  createdLinks: [],
  decomposition: null,
  gaps: null,
  finalCard: null,
  acceptedEnrichments: new Set(["title", "summary", "tags", "topic"]),
  rejectedLinkIds: new Set(),
  errors: [],
};

// --- Token Buffer ---
// Buffer thinking tokens for 80ms to reduce re-renders.

let thinkingFlushTimer: ReturnType<typeof setTimeout> | null = null;
let pendingThinking = "";

function flushThinking(
  set: (fn: (s: ZettelCreationState) => Partial<ZettelCreationState>) => void,
) {
  if (!pendingThinking) return;
  const chunk = pendingThinking;
  pendingThinking = "";
  set((s) => ({ thinkingBuffer: s.thinkingBuffer + chunk }));
}

// --- Store ---

export const useZettelCreationStore = create<
  ZettelCreationState & ZettelCreationActions
>((set) => ({
  ...initialState,

  startStream: () => {
    set({ ...initialState, phase: "streaming" });
  },

  handleEvent: (event, data) => {
    switch (event) {
      case "card_saved":
        set({
          cardId: data.id as number,
          cardTitle: data.title as string,
          steps: { ...initialState.steps, card_saved: true },
        });
        break;

      case "thinking":
        pendingThinking += (data.content as string) || "";
        if (!thinkingFlushTimer) {
          thinkingFlushTimer = setTimeout(() => {
            thinkingFlushTimer = null;
            flushThinking(set);
          }, 80);
        }
        break;

      case "embedding_done":
        set((s) => ({ steps: { ...s.steps, embedding_done: true } }));
        break;

      case "tool_start":
        break;

      case "links_found":
        set((s) => ({
          linkSuggestions: data.suggestions as LinkSuggestion[],
          steps: { ...s.steps, links_searched: true },
        }));
        break;

      case "links_created":
        set({ createdLinks: data.links as CreatedLink[] });
        break;

      case "enrichment":
        set((s) => ({
          enrichment: data as unknown as Enrichment,
          steps: { ...s.steps, ai_complete: true },
        }));
        break;

      case "decomposition":
        set({ decomposition: data as unknown as Decomposition });
        break;

      case "gaps":
        set({ gaps: data as unknown as Gaps });
        break;

      case "done":
        if (pendingThinking) flushThinking(set);
        set({
          phase: "complete",
          finalCard: data.card as Record<string, unknown>,
        });
        break;

      case "error":
        set((s) => ({
          errors: [
            ...s.errors,
            {
              step: data.step as string,
              message: data.message as string,
            },
          ],
        }));
        break;
    }
  },

  toggleEnrichment: (key) => {
    set((s) => {
      const next = new Set(s.acceptedEnrichments);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return { acceptedEnrichments: next };
    });
  },

  toggleLink: (linkId) => {
    set((s) => {
      const next = new Set(s.rejectedLinkIds);
      if (next.has(linkId)) next.delete(linkId);
      else next.add(linkId);
      return { rejectedLinkIds: next };
    });
  },

  reset: () => {
    pendingThinking = "";
    if (thinkingFlushTimer) {
      clearTimeout(thinkingFlushTimer);
      thinkingFlushTimer = null;
    }
    set(initialState);
  },
}));
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit --pretty 2>&1 | head -20`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add web/lib/stores/zettel-creation-store.ts
git commit -m "feat: add Zustand store for streaming zettel creation state"
```

---

## Task 9: Frontend Streaming Modal Component

**Files:**
- Create: `web/app/(app)/knowledge/_components/streaming-creation-modal.tsx`

- [ ] **Step 1: Create the streaming modal**

```tsx
// web/app/(app)/knowledge/_components/streaming-creation-modal.tsx
"use client";

import { useCallback, useEffect, useRef } from "react";

import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { VisuallyHidden } from "@radix-ui/react-visually-hidden";
import { useZettelCreationStore } from "@/lib/stores/zettel-creation-store";
import {
  Check,
  Loader2,
  X,
  Link2,
  Brain,
  Sparkles,
  AlertTriangle,
} from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { apiPatchJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function StepIndicator({
  done,
  active,
  label,
}: {
  done: boolean;
  active?: boolean;
  label: string;
}) {
  return (
    <div className="flex items-center gap-2 text-sm">
      {done ? (
        <Check className="size-3.5 text-green-500" />
      ) : active ? (
        <Loader2 className="size-3.5 animate-spin text-muted-foreground" />
      ) : (
        <div className="size-3.5 rounded-full border border-muted-foreground/30" />
      )}
      <span className={done ? "text-foreground" : "text-muted-foreground"}>
        {label}
      </span>
    </div>
  );
}

function EnrichmentRow({
  label,
  value,
  accepted,
  onToggle,
}: {
  label: string;
  value: string;
  accepted: boolean;
  onToggle: () => void;
}) {
  return (
    <div className="flex items-start justify-between gap-3 text-sm">
      <div className="flex-1 min-w-0">
        <span className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </span>
        <p className="text-foreground truncate">{value}</p>
      </div>
      <button
        onClick={onToggle}
        className={`mt-1 size-5 rounded flex items-center justify-center border transition-colors shrink-0 ${
          accepted
            ? "border-green-500 bg-green-500/10 text-green-500"
            : "border-muted-foreground/30 text-muted-foreground"
        }`}
      >
        {accepted && <Check className="size-3" />}
      </button>
    </div>
  );
}

export function StreamingCreationModal({ open, onOpenChange }: Props) {
  const store = useZettelCreationStore();
  const queryClient = useQueryClient();
  const thinkingRef = useRef<HTMLDivElement>(null);

  // Auto-scroll thinking block
  useEffect(() => {
    if (thinkingRef.current) {
      thinkingRef.current.scrollTop = thinkingRef.current.scrollHeight;
    }
  }, [store.thinkingBuffer]);

  const handleApplyAndClose = useCallback(async () => {
    if (!store.cardId) {
      onOpenChange(false);
      store.reset();
      return;
    }

    const patch: Record<string, unknown> = {};
    if (store.enrichment) {
      if (
        store.acceptedEnrichments.has("title") &&
        store.enrichment.suggested_title
      ) {
        patch.title = store.enrichment.suggested_title;
      }
      if (
        store.acceptedEnrichments.has("summary") &&
        store.enrichment.summary
      ) {
        patch.summary = store.enrichment.summary;
      }
      if (
        store.acceptedEnrichments.has("tags") &&
        store.enrichment.suggested_tags.length > 0
      ) {
        patch.tags = store.enrichment.suggested_tags;
      }
      if (
        store.acceptedEnrichments.has("topic") &&
        store.enrichment.suggested_topic
      ) {
        patch.topic = store.enrichment.suggested_topic;
      }
    }

    if (Object.keys(patch).length > 0) {
      try {
        await apiPatchJson(apiRoutes.zettels.cardById(store.cardId), patch);
      } catch {
        // Non-critical
      }
    }

    for (const linkId of store.rejectedLinkIds) {
      try {
        await fetch(apiRoutes.zettels.deleteLink(linkId), {
          method: "DELETE",
        });
      } catch {
        // Non-critical
      }
    }

    queryClient.invalidateQueries({ queryKey: ["zettels"] });
    onOpenChange(false);
    store.reset();
  }, [store, onOpenChange, queryClient]);

  const handleClose = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["zettels"] });
    onOpenChange(false);
    store.reset();
  }, [onOpenChange, store, queryClient]);

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-[600px] p-0 gap-0 overflow-hidden max-h-[80vh] flex flex-col">
        <VisuallyHidden>
          <DialogTitle>Creating Zettel</DialogTitle>
        </VisuallyHidden>

        {/* Header */}
        <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b">
          <span className="text-sm font-medium text-foreground">
            {store.phase === "complete"
              ? "Zettel Created"
              : "Creating Zettel..."}
          </span>
          <button
            onClick={handleClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {/* Progress Steps */}
          <div className="space-y-2">
            <StepIndicator
              done={store.steps.card_saved}
              active={
                store.phase === "streaming" && !store.steps.card_saved
              }
              label="Card saved"
            />
            <StepIndicator
              done={store.steps.embedding_done}
              active={
                store.steps.card_saved && !store.steps.embedding_done
              }
              label="Embedding generated"
            />
            <StepIndicator
              done={store.steps.links_searched}
              active={
                store.steps.embedding_done && !store.steps.links_searched
              }
              label="Knowledge base searched"
            />
            <StepIndicator
              done={store.steps.ai_complete}
              active={
                store.steps.card_saved && !store.steps.ai_complete
              }
              label="AI analysis complete"
            />
          </div>

          {/* Thinking Block */}
          {store.thinkingBuffer && (
            <details className="group">
              <summary className="flex items-center gap-2 cursor-pointer text-xs text-[var(--alfred-text-tertiary)] hover:text-muted-foreground transition-colors">
                <Brain className="size-3" />
                AI Thinking
              </summary>
              <div
                ref={thinkingRef}
                className="mt-2 p-3 rounded-md border border-[var(--alfred-ruled-line)] bg-card max-h-[200px] overflow-y-auto"
              >
                <pre className="font-mono text-xs text-[var(--alfred-text-tertiary)] whitespace-pre-wrap break-words leading-relaxed">
                  {store.thinkingBuffer}
                  {store.phase === "streaming" && (
                    <span className="animate-pulse">|</span>
                  )}
                </pre>
              </div>
            </details>
          )}

          {/* Enrichment Suggestions */}
          {store.enrichment && (
            <div className="rounded-md border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Sparkles className="size-3.5 text-[#E8590C]" />
                Enrichment
              </div>
              {store.enrichment.suggested_title && (
                <EnrichmentRow
                  label="Title"
                  value={store.enrichment.suggested_title}
                  accepted={store.acceptedEnrichments.has("title")}
                  onToggle={() => store.toggleEnrichment("title")}
                />
              )}
              {store.enrichment.summary && (
                <EnrichmentRow
                  label="Summary"
                  value={store.enrichment.summary}
                  accepted={store.acceptedEnrichments.has("summary")}
                  onToggle={() => store.toggleEnrichment("summary")}
                />
              )}
              {store.enrichment.suggested_tags.length > 0 && (
                <EnrichmentRow
                  label="Tags"
                  value={store.enrichment.suggested_tags.join(", ")}
                  accepted={store.acceptedEnrichments.has("tags")}
                  onToggle={() => store.toggleEnrichment("tags")}
                />
              )}
              {store.enrichment.suggested_topic && (
                <EnrichmentRow
                  label="Topic"
                  value={store.enrichment.suggested_topic}
                  accepted={store.acceptedEnrichments.has("topic")}
                  onToggle={() => store.toggleEnrichment("topic")}
                />
              )}
            </div>
          )}

          {/* Link Suggestions */}
          {store.linkSuggestions.length > 0 && (
            <div className="rounded-md border bg-card p-4 space-y-3">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Link2 className="size-3.5 text-[#E8590C]" />
                {store.linkSuggestions.length} Links Found
              </div>
              {store.linkSuggestions.map((link) => {
                const autoLink = store.createdLinks.find(
                  (l) =>
                    l.target_id === link.card_id ||
                    l.source_id === link.card_id,
                );
                const isRejected = autoLink
                  ? store.rejectedLinkIds.has(autoLink.id)
                  : false;

                return (
                  <div
                    key={link.card_id}
                    className="flex items-center justify-between text-sm"
                  >
                    <div className="flex-1 min-w-0">
                      <span className="truncate block">{link.title}</span>
                      <span className="text-xs text-muted-foreground">
                        {link.reason}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 ml-3">
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {(link.score * 100).toFixed(0)}%
                      </span>
                      {autoLink && (
                        <button
                          onClick={() => store.toggleLink(autoLink.id)}
                          className={`size-5 rounded flex items-center justify-center border transition-colors ${
                            isRejected
                              ? "border-muted-foreground/30 text-muted-foreground"
                              : "border-green-500 bg-green-500/10 text-green-500"
                          }`}
                        >
                          {!isRejected && <Check className="size-3" />}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Decomposition */}
          {store.decomposition && !store.decomposition.is_atomic && (
            <div className="rounded-md border border-amber-500/30 bg-amber-500/5 p-4 space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium text-amber-500">
                <AlertTriangle className="size-3.5" />
                Decomposition Suggested
              </div>
              <p className="text-xs text-muted-foreground">
                {store.decomposition.reason}
              </p>
              {store.decomposition.suggested_cards.map((card, i) => (
                <div
                  key={i}
                  className="text-xs pl-3 border-l-2 border-amber-500/30"
                >
                  <span className="font-medium">{card.title}</span>
                </div>
              ))}
            </div>
          )}

          {/* Knowledge Gaps */}
          {store.gaps &&
            (store.gaps.missing_topics.length > 0 ||
              store.gaps.weak_areas.length > 0) && (
              <div className="rounded-md border bg-card p-4 space-y-2">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Brain className="size-3.5 text-muted-foreground" />
                  Knowledge Gaps
                </div>
                {store.gaps.missing_topics.length > 0 && (
                  <p className="text-xs text-muted-foreground">
                    No cards on: {store.gaps.missing_topics.join(", ")}
                  </p>
                )}
                {store.gaps.weak_areas.map((area, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    {area.topic}: {area.note} ({area.existing_count} cards)
                  </p>
                ))}
              </div>
            )}

          {/* Errors (non-fatal) */}
          {store.errors.length > 0 && (
            <div className="text-xs text-muted-foreground space-y-1">
              {store.errors.map((err, i) => (
                <p key={i} className="text-amber-500">
                  {err.step}: {err.message}
                </p>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        {store.phase === "complete" && (
          <div className="border-t px-5 py-3 flex justify-end">
            <button
              onClick={handleApplyAndClose}
              className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors"
            >
              Apply & Close
            </button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add "web/app/(app)/knowledge/_components/streaming-creation-modal.tsx"
git commit -m "feat: add streaming zettel creation modal with thinking, enrichment, links, gaps"
```

---

## Task 10: Wire Streaming Modal Into Create Dialog

**Files:**
- Modify: `web/features/zettels/mutations.ts`
- Modify: `web/app/(app)/knowledge/_components/create-zettel-dialog.tsx`

- [ ] **Step 1: Add `useCreateZettelStream` hook to `web/features/zettels/mutations.ts`**

Add these imports at the top of the file:

```typescript
import { useCallback } from "react";
import { createZettelStream, ZettelCardCreatePayload } from "@/lib/api/zettels";
import { useZettelCreationStore } from "@/lib/stores/zettel-creation-store";
```

Add the hook at the end of the file:

```typescript
/**
 * Start a streaming zettel creation. Connects SSE and
 * feeds events to the Zustand store.
 */
export function useCreateZettelStream() {
  const store = useZettelCreationStore();

  const startStream = useCallback(
    async (payload: ZettelCardCreatePayload, signal?: AbortSignal) => {
      store.startStream();
      try {
        await createZettelStream(payload, store.handleEvent, signal);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          store.handleEvent("error", {
            step: "connection",
            message: (err as Error).message,
          });
        }
      }
    },
    [store],
  );

  return { startStream };
}
```

- [ ] **Step 2: Modify `create-zettel-dialog.tsx`**

Add imports at the top of `web/app/(app)/knowledge/_components/create-zettel-dialog.tsx`:

```typescript
import { StreamingCreationModal } from "./streaming-creation-modal";
import { useCreateZettelStream } from "@/features/zettels/mutations";
```

Add state and hook inside the component, after `const createMutation = useCreateZettel();` (line 47):

```typescript
  const [showStreamingModal, setShowStreamingModal] = useState(false);
  const { startStream } = useCreateZettelStream();
  const abortRef = useRef<AbortController | null>(null);
```

Replace the `handleCreate` callback (lines 91-120) with:

```typescript
  const handleCreate = useCallback(() => {
    const text = content.trim();
    if (!text) return;

    const finalTitle = title.trim() || extractTitle(text) || "Untitled";
    const tagList = tags
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);

    const payload = {
      title: finalTitle,
      content: text,
      summary: summary.trim() || undefined,
      tags: tagList.length > 0 ? tagList : undefined,
      topic: topic.trim() || undefined,
      importance: 5,
      confidence: 0.5,
    };

    setShowStreamingModal(true);
    onOpenChange(false);

    const abort = new AbortController();
    abortRef.current = abort;
    startStream(payload, abort.signal);
  }, [title, content, summary, tags, topic, startStream, onOpenChange, extractTitle]);
```

Wrap the return in a fragment and add the streaming modal after the existing Dialog:

```tsx
  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        {/* ...existing DialogContent unchanged... */}
      </Dialog>
      <StreamingCreationModal
        open={showStreamingModal}
        onOpenChange={(nextOpen) => {
          setShowStreamingModal(nextOpen);
          if (!nextOpen) {
            abortRef.current?.abort();
            reset();
          }
        }}
      />
    </>
  );
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit --pretty 2>&1 | head -30`
Expected: No errors

- [ ] **Step 4: Test in browser**

1. Open `http://localhost:3000/knowledge`
2. Click to create a new zettel
3. Enter title + content, press Cmd+Enter
4. Verify the form dialog closes and streaming modal opens
5. Verify "Card saved" checkmark appears quickly
6. Verify thinking tokens stream in the collapsible block
7. Verify enrichment suggestions appear with accept/reject toggles
8. Verify link suggestions appear with scores
9. Verify "Apply & Close" applies enrichments and the card appears in the list

- [ ] **Step 5: Commit**

```bash
git add "web/app/(app)/knowledge/_components/create-zettel-dialog.tsx" web/features/zettels/mutations.ts
git commit -m "feat: wire streaming modal into zettel creation flow"
```

---

## Task 11: Final Integration Test + Cleanup

**Files:**
- Review: all new and modified files

- [ ] **Step 1: Run full backend test suite**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/utils/ tests/alfred/services/test_zettel_creation_stream.py tests/alfred/api/zettels/test_stream_routes.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run linting**

Run: `cd /Users/ashwinrachha/coding/alfred && make lint`
Expected: No errors (or fix any that appear)

- [ ] **Step 3: Run frontend type check**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit`
Expected: No errors

- [ ] **Step 4: End-to-end browser test**

1. Navigate to `http://localhost:3000/knowledge`
2. Create a zettel with substantial content (2-3 paragraphs on a topic you have other cards about)
3. Verify the full streaming experience:
   - Card saved checkmark appears immediately
   - Thinking tokens stream in real-time
   - Embedding generated checkmark
   - Link suggestions appear with scores
   - Auto-links are created (checked by default)
   - Enrichment suggestions (title, summary, tags, topic)
   - Knowledge gaps section appears
   - "Apply & Close" applies accepted enrichments
4. Verify the card appears in the list with applied enrichments
5. Verify the card shows links on its detail panel
6. Test edge cases:
   - Close modal early (card should still exist)
   - Create zettel with minimal content (just a title + one sentence)
   - Create zettel when no other cards exist (links/gaps handle gracefully)

- [ ] **Step 5: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address integration test findings for streaming zettel creation"
```

---

## Eng Review Changes (apply during implementation)

These changes were agreed during `/plan-eng-review` and override the task code above:

### Scope Reduction
- **Drop `apps/alfred/api/zettels/stream_routes.py`** — inline the route into existing `routes.py`
- **Drop `apps/alfred/utils/__init__.py`** — move `async_merge.py` into `apps/alfred/core/`
- **Extract shared utils:** `_make_client()` → `get_async_openai_client()` with `@lru_cache` in `core/llm_factory.py`. `_sse()` → shared SSE helper. Update `agent/service.py` to import from shared location.

### Architecture Fixes
- **Client caching:** `get_async_openai_client()` in `core/llm_factory.py` with `@lru_cache`. Not per-call creation.
- **Model config:** Add `zettel_analysis_model: str = Field(default="o4-mini")` to `core/settings.py`. Use `settings.zettel_analysis_model` instead of hardcoded constant.
- **Cross-track sync:** Dropped for v1. Topic/tag distribution sufficient for gap detection.
- **Cache invalidation timing:** Move to Phase 0 (immediately after card save), not Phase 2. Ensures card visible in UI even if stream dies.
- **OpenAI streaming pattern:** Use `stream = await client.chat.completions.create(...); async for chunk in stream` — NOT `async with await`. Match `agent/service.py` pattern.

### Code Quality Fixes
- **One session per track:** Track A creates one DB session for all 4 steps. Track B gets one session for context fetch. Not session-per-method.
- **Simplify Track A:** Use `ensure_embedding()` → emit `embedding_done` → `suggest_links()` → emit events → `create_link()`. Remove `_embed_card()` and `_sync_to_qdrant()` wrappers.

### Performance Fix
- **Redis cache for context:** `_fetch_kb_context()` reads topic/tag distribution from existing Redis cache, falls back to DB on cache miss.

### SSE Parser Fix (prerequisite)
- **Fix `web/lib/api/sse.ts`** chunk-split bug: accumulate complete events (event + data + blank line) before parsing. Affects both agent chat and this new feature.

### Additional Tests (add to Tasks 3-5)
- `_parse_analysis_response`: valid JSON, markdown fences wrapping, partial keys, garbage string
- Track A: empty suggestions list, threshold boundary (score exactly 0.75)
- Track B: malformed JSON from LLM
- Full pipeline: both tracks error, card still returned in done event
- Phase 0: DB connection failure emits error event (add try/except to `run_phase0`)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 2 | ISSUES | 10 findings, 3 accepted |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 2 | CLEAR | 6 issues, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | OPEN | score: 3/10 → 7/10, 11 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**CODEX:** 10 findings. Accepted: cache timing fix, SSE parser fix, OpenAI API pattern fix. Rejected: architecture size (intentional), kitchen sink (by design), parallelism order (acceptable tradeoff).
**CROSS-MODEL:** Both agree on cache timing, SSE parser, API pattern. Disagree on architecture size (review says acceptable after scope reduction, Codex wants thinner).
**UNRESOLVED:** 0
**VERDICT:** ENG CLEARED — ready to implement. Design review has 6 unresolved items from prior session.
