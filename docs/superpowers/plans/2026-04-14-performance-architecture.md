# Performance Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Make Alfred feel instant across all pages and interactions — near-zero page transitions, fast API responses, small initial bundles.

**Architecture:** Four-layer approach: (1) frontend bundle surgery to cut JS payload, (2) React Query tuning + prefetching to eliminate loading delays, (3) backend query fixes + Redis caching to slash response times, (4) React memoization to reduce unnecessary re-renders.

**Tech Stack:** Next.js 16, React 19, TanStack React Query, FastAPI, SQLModel, Qdrant, Redis, Celery

**Spec:** docs/superpowers/specs/2026-04-14-performance-architecture-design.md

---

## File Structure

### New Files
| File | Responsibility |
|------|---------------|
| apps/alfred/core/cache.py | Reusable Redis cache utility (get/set/invalidate) |
| apps/alfred/tasks/canvas_tasks.py | Celery task for diagram generation |
| web/lib/prefetch.ts | Route-to-query prefetch mapping |
| web/app/(app)/knowledge/_components/knowledge-skeleton.tsx | Knowledge page skeleton |
| web/app/(app)/notes/_components/notes-skeleton.tsx | Notes page skeleton |
| web/app/(app)/documents/_components/documents-skeleton.tsx | Documents page skeleton |
| tests/alfred/core/test_cache.py | Tests for cache utility |
| tests/alfred/tasks/test_canvas_tasks.py | Tests for canvas Celery task |
| tests/alfred/services/test_zettel_qdrant_search.py | Tests for Qdrant search |
| tests/alfred/api/agent/test_thread_list_perf.py | Test for N+1 fix |

### Modified Files
| File | Change |
|------|--------|
| apps/alfred/services/zettelkasten_service.py:810-846 | Replace O(n) find_similar_cards with Qdrant |
| apps/alfred/core/dependencies.py | Add Qdrant client singleton |
| apps/alfred/api/agent/routes.py:297-322 | Fix N+1 with COUNT subquery |
| apps/alfred/api/canvas/routes.py:45-63 | Return task ID instead of blocking |
| apps/alfred/api/zettels/routes.py | Add Cache-Control headers |
| apps/alfred/api/documents/routes.py | Add Cache-Control headers |
| apps/alfred/tasks/__init__.py | Register canvas_tasks |
| web/features/zettels/queries.ts | Export queryOptions, add keepPreviousData |
| web/features/notes/queries.ts | Export queryOptions, tune staleTime |
| web/features/documents/queries.ts | Export queryOptions, tune staleTime |
| web/features/dictionary/queries.ts | Export queryOptions |
| web/features/research/queries.ts | Export queryOptions |
| web/features/canvas/queries.ts | Tune staleTime from 0s to 30s |
| web/features/tasks/queries.ts | Exponential backoff polling |
| web/app/(app)/_components/app-sidebar.tsx | Hover prefetch, fix over-subscription, memoize |
| web/app/(app)/knowledge/_components/zettel-graph.tsx | Wrap xyflow in dynamic |
| web/app/(app)/knowledge/_components/knowledge-hub.tsx | Add skeleton loading |

---

### Task 1: Backend — Create Reusable Redis Cache Utility

**Files:**
- Create: apps/alfred/core/cache.py
- Create: tests/alfred/core/test_cache.py

- [ ] **Step 1: Write the failing tests**

```python
# tests/alfred/core/test_cache.py
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from alfred.core.cache import cache_get, cache_set, cache_invalidate


class TestCacheGet:
    def test_returns_cached_value(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = json.dumps({"items": [1, 2, 3]})
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result == {"items": [1, 2, 3]}

    def test_returns_none_on_miss(self):
        mock_redis = MagicMock()
        mock_redis.get.return_value = None
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result is None

    def test_returns_none_when_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            result = cache_get("test:key")
        assert result is None

    def test_returns_none_on_redis_error(self):
        mock_redis = MagicMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            result = cache_get("test:key")
        assert result is None


class TestCacheSet:
    def test_stores_value_with_ttl(self):
        mock_redis = MagicMock()
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            cache_set("test:key", {"data": "value"}, ttl=60)
        mock_redis.set.assert_called_once_with(
            "test:key", json.dumps({"data": "value"}), ex=60
        )

    def test_silent_on_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            cache_set("test:key", {"data": "value"})


class TestCacheInvalidate:
    def test_deletes_matching_keys(self):
        mock_redis = MagicMock()
        mock_redis.scan_iter.return_value = ["prefix:a", "prefix:b"]
        with patch("alfred.core.cache.get_redis_client", return_value=mock_redis):
            cache_invalidate("prefix:")
        assert mock_redis.delete.call_count == 2

    def test_silent_on_redis_unavailable(self):
        with patch("alfred.core.cache.get_redis_client", return_value=None):
            cache_invalidate("prefix:")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/core/test_cache.py -v`
Expected: FAIL with ModuleNotFoundError for alfred.core.cache

- [ ] **Step 3: Implement the cache utility**

```python
# apps/alfred/core/cache.py
"""Reusable Redis cache utility.

Best-effort semantics: cache failures never raise, never block.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from alfred.core.redis_client import get_redis_client

_log = logging.getLogger(__name__)


def cache_get(key: str) -> Any | None:
    """Read a cached JSON value. Returns None on miss or error."""
    redis = get_redis_client()
    if not redis:
        return None
    try:
        raw = redis.get(key)
        return json.loads(raw) if raw else None
    except Exception:
        return None


def cache_set(key: str, value: Any, *, ttl: int = 60) -> None:
    """Best-effort write with TTL in seconds."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        redis.set(key, json.dumps(value), ex=ttl)
    except Exception:
        pass


def cache_invalidate(prefix: str) -> None:
    """Best-effort delete all keys matching prefix."""
    redis = get_redis_client()
    if not redis:
        return
    try:
        for key in redis.scan_iter(f"{prefix}*"):
            redis.delete(key)
    except Exception:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/core/test_cache.py -v`
Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/core/cache.py tests/alfred/core/test_cache.py
git commit -m "feat: add reusable Redis cache utility in core/cache.py"
```

---

### Task 2: Backend — Fix Agent Thread N+1 Query

**Files:**
- Modify: apps/alfred/api/agent/routes.py:297-322
- Create: tests/alfred/api/agent/test_thread_list_perf.py

- [ ] **Step 1: Write the test**

```python
# tests/alfred/api/agent/test_thread_list_perf.py
from __future__ import annotations

from fastapi.testclient import TestClient

from alfred.main import app


client = TestClient(app)


def test_list_threads_returns_200():
    """Verify thread listing endpoint works after refactor."""
    response = client.get("/api/agent/threads?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    for thread in data:
        assert "message_count" in thread
        assert isinstance(thread["message_count"], int)
```

- [ ] **Step 2: Run test to verify baseline**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/agent/test_thread_list_perf.py -v`
Expected: PASS (current code works, just slow)

- [ ] **Step 3: Replace N+1 with COUNT subquery**

In apps/alfred/api/agent/routes.py, replace the list_threads function (lines 297-322):

```python
@router.get("/threads")
def list_threads(
    status_filter: str = "active",
    note_id: str | None = None,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db_session),
) -> list[ThreadSummary]:
    from sqlalchemy import func as sa_func

    count_sub = (
        select(sa_func.count(AgentMessageRow.id))
        .where(AgentMessageRow.thread_id == ThinkingSessionRow.id)
        .correlate(ThinkingSessionRow)
        .scalar_subquery()
    )
    stmt = (
        select(ThinkingSessionRow, count_sub.label("message_count"))
        .where(ThinkingSessionRow.session_type == "agent")
        .where(ThinkingSessionRow.status == status_filter)
        .order_by(ThinkingSessionRow.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    if note_id is not None:
        stmt = stmt.where(ThinkingSessionRow.note_id == note_id)

    rows = db.exec(stmt).all()
    results = []
    for session_row, msg_count in rows:
        summary = _to_summary(session_row)
        summary.message_count = msg_count
        results.append(summary)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/agent/test_thread_list_perf.py -v`
Expected: PASS

- [ ] **Step 5: Run existing agent tests**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/agent/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/api/agent/routes.py tests/alfred/api/agent/test_thread_list_perf.py
git commit -m "perf: fix N+1 in agent thread listing with COUNT subquery"
```

---

### Task 3: Backend — Replace find_similar_cards O(n) with Qdrant

**Files:**
- Modify: apps/alfred/core/dependencies.py (add get_qdrant_client)
- Modify: apps/alfred/services/zettelkasten_service.py:810-846
- Create: tests/alfred/services/test_zettel_qdrant_search.py

- [ ] **Step 1: Write the failing tests**

```python
# tests/alfred/services/test_zettel_qdrant_search.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_find_similar_cards_uses_qdrant_when_available():
    """Qdrant primary path: query_points instead of full table scan."""
    from alfred.services.zettelkasten_service import ZettelkastenService

    session = MagicMock()
    svc = ZettelkastenService(session=session)

    mock_card = MagicMock()
    mock_card.id = 1
    mock_card.embedding = [0.1] * 1536
    mock_card.topics = []
    mock_card.tags = []

    mock_cand = MagicMock()
    mock_cand.id = 2
    mock_cand.embedding = [0.2] * 1536
    mock_cand.topics = []
    mock_cand.tags = []

    def side_get(model, pk):
        return {1: mock_card, 2: mock_cand}.get(pk)

    session.get.side_effect = side_get

    mock_qdrant = MagicMock()
    mock_hit = MagicMock()
    mock_hit.id = 2
    mock_hit.score = 0.85
    mock_qdrant.query_points.return_value.points = [mock_hit]

    with patch(
        "alfred.services.zettelkasten_service.get_qdrant_client",
        return_value=mock_qdrant,
    ):
        results = svc.find_similar_cards(1, threshold=0.5, limit=5)

    mock_qdrant.query_points.assert_called_once()
    session.exec.assert_not_called()


def test_find_similar_cards_falls_back_without_qdrant():
    """When Qdrant unavailable, use Python cosine similarity fallback."""
    from alfred.services.zettelkasten_service import ZettelkastenService

    session = MagicMock()
    svc = ZettelkastenService(session=session)

    mock_card = MagicMock()
    mock_card.id = 1
    mock_card.embedding = [0.1] * 1536
    mock_card.topics = []
    mock_card.tags = []
    session.get.return_value = mock_card
    session.exec.return_value = iter([])

    with patch(
        "alfred.services.zettelkasten_service.get_qdrant_client",
        return_value=None,
    ):
        results = svc.find_similar_cards(1, threshold=0.5, limit=5)

    session.exec.assert_called_once()
    assert results == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_qdrant_search.py -v`
Expected: FAIL — get_qdrant_client doesn't exist

- [ ] **Step 3: Add Qdrant client singleton**

In apps/alfred/core/dependencies.py, add after the existing singletons:

```python
@lru_cache(maxsize=1)
def get_qdrant_client():
    """Return a Qdrant client or None if unavailable."""
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        return None

    url = settings.qdrant_url
    if settings.qdrant_prefer_local and settings.qdrant_local_url:
        url = settings.qdrant_local_url
    if not url:
        return None

    try:
        api_key = settings.qdrant_api_key.get_secret_value() if settings.qdrant_api_key else None
        return QdrantClient(url=url, api_key=api_key)
    except Exception:
        return None
```

- [ ] **Step 4: Rewrite find_similar_cards**

In apps/alfred/services/zettelkasten_service.py, add import at top:

```python
from alfred.core.dependencies import get_qdrant_client
```

Replace find_similar_cards (starting around line 810) with three methods:

```python
    def find_similar_cards(
        self, card_id: int, *, threshold: float = 0.5, limit: int = 10
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        card = self.session.get(ZettelCard, card_id)
        if not card:
            raise ValueError("Card not found")

        card = self.ensure_embedding(card)
        base_embedding = card.embedding or []
        if not base_embedding:
            return []

        existing_links = self._existing_links(card_id)

        qdrant = get_qdrant_client()
        if qdrant is not None:
            return self._find_similar_via_qdrant(
                card, base_embedding, existing_links, qdrant,
                threshold=threshold, limit=limit,
            )
        return self._find_similar_via_scan(
            card, card_id, base_embedding, existing_links,
            threshold=threshold, limit=limit,
        )

    def _find_similar_via_qdrant(
        self,
        card: ZettelCard,
        base_embedding: list[float],
        existing_links: set,
        qdrant,
        *,
        threshold: float,
        limit: int,
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        from alfred.core.settings import settings

        try:
            results = qdrant.query_points(
                collection_name=settings.qdrant_zettels_collection,
                query=base_embedding,
                limit=limit * 3,
                score_threshold=threshold,
            )
        except Exception:
            return self._find_similar_via_scan(
                card, card.id, base_embedding, existing_links,
                threshold=threshold, limit=limit,
            )

        scored: list[tuple[ZettelCard, LinkQuality]] = []
        for hit in results.points:
            hit_id = int(hit.id) if not isinstance(hit.id, int) else hit.id
            if hit_id == card.id or (card.id, hit_id) in existing_links:
                continue
            cand = self.session.get(ZettelCard, hit_id)
            if not cand:
                continue
            quality = self._quality(card, cand, semantic_score=hit.score)
            scored.append((cand, quality))

        scored.sort(key=lambda item: item[1].composite_score, reverse=True)
        return scored[:limit]

    def _find_similar_via_scan(
        self,
        card: ZettelCard,
        card_id: int,
        base_embedding: list[float],
        existing_links: set,
        *,
        threshold: float,
        limit: int,
    ) -> list[tuple[ZettelCard, LinkQuality]]:
        """Original O(n) fallback when Qdrant is unavailable."""
        candidates = self.session.exec(select(ZettelCard).where(ZettelCard.id != card_id))
        scored: list[tuple[ZettelCard, LinkQuality]] = []
        for cand in candidates:
            if cand.embedding is None:
                try:
                    cand = self.ensure_embedding(cand)
                except Exception:
                    continue
            semantic = _cosine_similarity(base_embedding, cand.embedding or [])
            if semantic < threshold:
                continue
            quality = self._quality(card, cand, semantic_score=semantic)
            if (card.id, cand.id) in existing_links:
                continue
            scored.append((cand, quality))

        scored.sort(key=lambda item: item[1].composite_score, reverse=True)
        return scored[:limit]
```

- [ ] **Step 5: Run tests**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettel_qdrant_search.py -v`
Expected: Both tests PASS

- [ ] **Step 6: Run existing zettelkasten tests**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_zettelkasten_service.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add apps/alfred/core/dependencies.py apps/alfred/services/zettelkasten_service.py tests/alfred/services/test_zettel_qdrant_search.py
git commit -m "perf: replace O(n) find_similar_cards with Qdrant vector search"
```

---

### Task 4: Backend — Move Canvas Diagram Generation to Celery

**Files:**
- Create: apps/alfred/tasks/canvas_tasks.py
- Create: tests/alfred/tasks/test_canvas_tasks.py
- Modify: apps/alfred/api/canvas/routes.py:45-63
- Modify: apps/alfred/tasks/__init__.py

- [ ] **Step 1: Write the failing test**

```python
# tests/alfred/tasks/test_canvas_tasks.py
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_generate_diagram_task_returns_result():
    from alfred.tasks.canvas_tasks import generate_diagram_task

    mock_model = MagicMock()
    mock_model.invoke.return_value = MagicMock(content='{"elements":[],"description":"test"}')

    with (
        patch("alfred.tasks.canvas_tasks.get_chat_model", return_value=mock_model),
        patch("alfred.tasks.canvas_tasks.build_diagram_prompt", return_value="prompt"),
        patch(
            "alfred.tasks.canvas_tasks.parse_diagram_response",
            return_value={"elements": [], "description": "test"},
        ),
    ):
        result = generate_diagram_task(prompt="draw a box", canvas_context=None)

    assert result["elements"] == []
    assert result["description"] == "test"
    mock_model.invoke.assert_called_once_with("prompt")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/tasks/test_canvas_tasks.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create the Celery task**

```python
# apps/alfred/tasks/canvas_tasks.py
"""Canvas diagram generation offloaded to Celery."""
from __future__ import annotations

import logging

from alfred.core.celery_client import celery_app

_log = logging.getLogger(__name__)


@celery_app.task(name="canvas.generate_diagram", bind=True, max_retries=1)
def generate_diagram_task(self, *, prompt: str, canvas_context: str | None = None) -> dict:
    from alfred.core.llm_factory import get_chat_model
    from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response

    try:
        full_prompt = build_diagram_prompt(prompt, canvas_context)
        model = get_chat_model()
        response = model.invoke(full_prompt)
        content = response.content if hasattr(response, "content") else str(response)
        return parse_diagram_response(content)
    except Exception as exc:
        _log.warning("Diagram generation failed: %s", exc)
        return {"elements": [], "description": f"Failed: {exc}"}
```

- [ ] **Step 4: Register the task**

In apps/alfred/tasks/__init__.py, add at the end:

```python
from . import canvas_tasks as canvas_tasks
```

- [ ] **Step 5: Update the canvas route**

In apps/alfred/api/canvas/routes.py, replace generate_diagram (lines 45-63):

```python
@router.post("/generate-diagram")
def generate_diagram(payload: DiagramRequest) -> dict:
    """Dispatch diagram generation to Celery, return task ID."""
    from alfred.core.celery_client import BrokerUnavailableError, dispatch_task
    from alfred.core.exceptions import ServiceUnavailableError

    try:
        task_result = dispatch_task(
            "canvas.generate_diagram",
            kwargs={"prompt": payload.prompt, "canvas_context": payload.canvas_context},
        )
        return {"task_id": task_result.id, "status": "pending"}
    except BrokerUnavailableError as exc:
        raise ServiceUnavailableError("Background worker unavailable") from exc
```

- [ ] **Step 6: Run tests**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/tasks/test_canvas_tasks.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/alfred/tasks/canvas_tasks.py apps/alfred/tasks/__init__.py apps/alfred/api/canvas/routes.py tests/alfred/tasks/test_canvas_tasks.py
git commit -m "perf: move canvas diagram generation to Celery task"
```

---

### Task 5: Backend — Add Cache-Control Headers to List Endpoints

**Files:**
- Modify: apps/alfred/api/zettels/routes.py
- Modify: apps/alfred/api/documents/routes.py

- [ ] **Step 1: Add cache header helper to zettels routes**

In apps/alfred/api/zettels/routes.py, add import for Response (line 7, already has fastapi imports):

```python
from fastapi import Response  # add to existing import line
```

Add helper after the existing _cache helpers (around line 235):

```python
def _set_cache_headers(response: Response, max_age: int = 30) -> None:
    response.headers["Cache-Control"] = f"private, max-age={max_age}"
```

- [ ] **Step 2: Apply to cards list, topics, and tags endpoints**

Add `response: Response` parameter to the list_cards, get_topics, and get_tags endpoints. Call `_set_cache_headers(response)` at the start of each function body.

- [ ] **Step 3: Apply same pattern to documents routes**

In apps/alfred/api/documents/routes.py, add the same helper and apply to the explorer list endpoint.

- [ ] **Step 4: Commit**

```bash
git add apps/alfred/api/zettels/routes.py apps/alfred/api/documents/routes.py
git commit -m "perf: add Cache-Control headers to list endpoints"
```

---

### Task 6: Frontend — Tune staleTime Values

**Files:**
- Modify: web/features/canvas/queries.ts
- Modify: web/features/notes/queries.ts
- Modify: web/features/documents/queries.ts
- Modify: web/features/zettels/queries.ts

- [ ] **Step 1: Update canvas staleTime**

In web/features/canvas/queries.ts, find useCanvas hook, change staleTime from 0 to 30000:

```typescript
staleTime: 30_000, // was 0
```

- [ ] **Step 2: Update notes staleTime**

In web/features/notes/queries.ts, find useNote hook, change staleTime from 0 to 15000:

```typescript
staleTime: 15_000, // was 0
```

- [ ] **Step 3: Update documents staleTime**

In web/features/documents/queries.ts, find useExplorerDocuments and useRecentDocuments, change from 10000 to 30000:

```typescript
staleTime: 30_000, // was 10_000
```

- [ ] **Step 4: Update zettel search staleTime**

In web/features/zettels/queries.ts, find useCardSearch, change from 5000 to 30000:

```typescript
staleTime: 30_000, // was 5_000
```

- [ ] **Step 5: Verify dev server works**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npm run dev`
Navigate between pages. Verify no stale data issues.

- [ ] **Step 6: Commit**

```bash
git add web/features/canvas/queries.ts web/features/notes/queries.ts web/features/documents/queries.ts web/features/zettels/queries.ts
git commit -m "perf: tune staleTime values to reduce unnecessary refetches"
```

---

### Task 7: Frontend — Extract Query Options and Add keepPreviousData

**Files:**
- Modify: web/features/zettels/queries.ts
- Modify: web/features/notes/queries.ts
- Modify: web/features/documents/queries.ts
- Modify: web/features/dictionary/queries.ts
- Modify: web/features/research/queries.ts
- Modify: web/features/tasks/queries.ts

- [ ] **Step 1: Extract zettel cards query options**

In web/features/zettels/queries.ts, add imports and extract options:

```typescript
import { queryOptions, keepPreviousData, useQuery } from "@tanstack/react-query";

export function zettelCardsQueryOptions(
  filters?: ZettelFilterParams,
  pagination?: ZettelPaginationOptions,
) {
  const page = pagination?.page ?? 1;
  const pageSize = pagination?.pageSize ?? 50;
  return queryOptions({
    queryKey: ["zettels", "cards", filters || null, page, pageSize] as const,
    queryFn: () => apiListZettelCards(/* pass existing params */),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}

// Update the hook to use the options:
export function useZettelCards(filters?: ZettelFilterParams, pagination?: ZettelPaginationOptions) {
  return useQuery(zettelCardsQueryOptions(filters, pagination));
}
```

- [ ] **Step 2: Extract notes workspaces query options**

In web/features/notes/queries.ts:

```typescript
import { queryOptions, keepPreviousData } from "@tanstack/react-query";

export function workspacesQueryOptions(params: { userId?: number | null } = {}) {
  const { userId = null } = params;
  return queryOptions({
    queryKey: workspacesQueryKey(userId),
    queryFn: () => listWorkspaces({ userId }),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}
```

- [ ] **Step 3: Extract documents explorer query options**

In web/features/documents/queries.ts:

```typescript
export function explorerDocumentsQueryOptions(
  params: { limit?: number; filterTopic?: string; search?: string } = {},
) {
  const limit = params.limit ?? 20;
  const filterTopic = params.filterTopic ?? "";
  const search = params.search ?? "";
  return queryOptions({
    queryKey: explorerDocumentsQueryKey({ limit, filterTopic, search }),
    queryFn: () => listExplorerDocuments({ limit, filterTopic, search }),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}
```

- [ ] **Step 4: Extract dictionary and research query options**

Same pattern for useDictionaryEntries in web/features/dictionary/queries.ts and useResearchReports in web/features/research/queries.ts. Export the queryOptions function and add keepPreviousData.

- [ ] **Step 5: Replace task polling with exponential backoff**

In web/features/tasks/queries.ts, update useTaskStatus:

```typescript
export function useTaskStatus(taskId: string | null) {
  return useQuery({
    enabled: Boolean(taskId),
    queryKey: taskId ? taskStatusQueryKey(taskId) : ["tasks", "status", "disabled"],
    queryFn: () => getTaskStatus(taskId!),
    refetchInterval: (query) => {
      if (query.state.data?.ready) return false;
      const attempt = query.state.dataUpdateCount;
      return Math.min(1000 * Math.pow(2, attempt), 10_000);
    },
  });
}
```

- [ ] **Step 6: Verify TypeScript compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx tsc --noEmit`
Expected: No type errors

- [ ] **Step 7: Commit**

```bash
git add web/features/zettels/queries.ts web/features/notes/queries.ts web/features/documents/queries.ts web/features/dictionary/queries.ts web/features/research/queries.ts web/features/tasks/queries.ts
git commit -m "perf: extract queryOptions, add keepPreviousData, exponential backoff"
```

---

### Task 8: Frontend — Sidebar Hover Prefetch

**Files:**
- Create: web/lib/prefetch.ts
- Modify: web/app/(app)/_components/app-sidebar.tsx

- [ ] **Step 1: Create the prefetch utility**

```typescript
// web/lib/prefetch.ts
import type { QueryClient } from "@tanstack/react-query";

import { zettelCardsQueryOptions } from "@/features/zettels/queries";
import { workspacesQueryOptions } from "@/features/notes/queries";
import { explorerDocumentsQueryOptions } from "@/features/documents/queries";

type Prefetcher = (qc: QueryClient) => void;

const routePrefetchMap: Record<string, Prefetcher> = {
  "/knowledge": (qc) => qc.prefetchQuery(zettelCardsQueryOptions()),
  "/notes": (qc) => qc.prefetchQuery(workspacesQueryOptions()),
  "/documents": (qc) => qc.prefetchQuery(explorerDocumentsQueryOptions()),
};

export function prefetchRouteData(href: string, queryClient: QueryClient): void {
  const prefetcher = routePrefetchMap[href];
  if (prefetcher) {
    prefetcher(queryClient);
  }
}
```

- [ ] **Step 2: Wire up in sidebar**

In web/app/(app)/_components/app-sidebar.tsx, add imports:

```typescript
import { useQueryClient } from "@tanstack/react-query";
import { prefetchRouteData } from "@/lib/prefetch";
```

In AppSidebar, get the query client:

```typescript
export function AppSidebar() {
  const pathname = usePathname();
  const queryClient = useQueryClient();
  // ... existing code
```

Pass queryClient to SidebarNavItem. In the Link element, add onMouseEnter:

```typescript
<Link
  href={item.href}
  prefetch
  onMouseEnter={() => prefetchRouteData(item.href, queryClient)}
  className={classes}
>
```

- [ ] **Step 3: Verify prefetch works**

Open browser DevTools Network tab. Hover over "Knowledge" in sidebar. Verify a GET request fires. Click — page renders instantly from cache.

- [ ] **Step 4: Commit**

```bash
git add web/lib/prefetch.ts "web/app/(app)/_components/app-sidebar.tsx"
git commit -m "perf: add sidebar hover prefetch for top pages"
```

---

### Task 9: Frontend — Memoize Shell Components and Fix Over-Subscription

**Files:**
- Modify: web/app/(app)/_components/app-sidebar.tsx

- [ ] **Step 1: Add React import**

```typescript
import React from "react";
```

- [ ] **Step 2: Fix SidebarNavItem over-subscription and memoize**

Replace the SidebarNavItem function with a memoized version that accepts AI state as optional props instead of subscribing to the store:

```typescript
type NavItemProps = {
  item: NavItem;
  isActive: boolean;
  queryClient: QueryClient;
  aiPanelOpen?: boolean;
  chatMode?: string;
};

const SidebarNavItem = React.memo(function SidebarNavItem({
  item,
  isActive,
  queryClient,
  aiPanelOpen = false,
  chatMode,
}: NavItemProps) {
  const aiActive = item.action === "toggle-ai-panel" && aiPanelOpen;
  const aiExpanded = item.action === "toggle-ai-panel" && chatMode === "expanded";

  const classes = cn(
    "group flex items-center gap-2.5 border-l-2 px-5 py-1.5 text-xs tracking-wide transition-colors",
    aiActive
      ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
      : isActive
        ? "border-primary bg-[var(--alfred-accent-subtle)] text-primary"
        : "border-transparent text-muted-foreground hover:bg-[var(--alfred-accent-subtle)] hover:text-foreground",
  );

  const inner = (
    <>
      <item.icon className="size-4 shrink-0 opacity-50 group-hover:opacity-100" />
      <span>{item.label}</span>
      {aiExpanded && (
        <span className="text-primary ml-1 text-[9px] tracking-wider uppercase opacity-70">
          expanded
        </span>
      )}
      {item.shortcut && (
        <kbd className="ml-auto text-[10px] text-[var(--alfred-text-tertiary)] opacity-0 transition-opacity group-hover:opacity-100">
          {item.shortcut}
        </kbd>
      )}
    </>
  );

  if (item.action === "toggle-ai-panel") {
    return (
      <button
        type="button"
        onClick={() => useShellStore.getState().openAiPanel("expanded")}
        className={classes}
      >
        {inner}
      </button>
    );
  }

  return (
    <Link
      href={item.href}
      prefetch
      onMouseEnter={() => prefetchRouteData(item.href, queryClient)}
      className={classes}
    >
      {inner}
    </Link>
  );
});
```

- [ ] **Step 3: Update AppSidebar to pass AI state only to AI item**

In the render loop, only pass aiPanelOpen and chatMode to the AI item:

```typescript
{section.items.map((item) => {
  const isActive = pathname === item.href || pathname.startsWith(`${item.href}/`);
  return (
    <SidebarNavItem
      key={item.href}
      item={item}
      isActive={isActive}
      queryClient={queryClient}
      aiPanelOpen={item.action === "toggle-ai-panel" ? aiPanelOpen : undefined}
      chatMode={item.action === "toggle-ai-panel" ? chatMode : undefined}
    />
  );
})}
```

- [ ] **Step 4: Memoize TaskCenterButton**

```typescript
const TaskCenterButton = React.memo(function TaskCenterButton() {
  // existing implementation unchanged
});
```

- [ ] **Step 5: Verify everything works**

Open dev server. Click sidebar items, toggle AI panel. All navigation and AI panel toggle should work.

- [ ] **Step 6: Commit**

```bash
git add "web/app/(app)/_components/app-sidebar.tsx"
git commit -m "perf: memoize sidebar nav items, fix AI panel over-subscription"
```

---

### Task 10: Frontend — Dynamic-Import @xyflow in Zettel Graph

**Files:**
- Modify: the file that imports zettel-graph.tsx (likely knowledge-hub.tsx)

- [ ] **Step 1: Find where zettel-graph is imported**

Search for the import of ZettelGraph or zettel-graph in the knowledge components.

- [ ] **Step 2: Replace static import with dynamic**

```typescript
import dynamic from "next/dynamic";

const ZettelGraph = dynamic(
  () => import("./zettel-graph").then((m) => m.ZettelGraph),
  { ssr: false }
);
```

Remove any static import of ZettelGraph.

- [ ] **Step 3: Verify graph view still works**

Open /knowledge, switch to graph view. Verify the xyflow graph renders.

- [ ] **Step 4: Commit**

```bash
git add "web/app/(app)/knowledge/_components/"
git commit -m "perf: dynamic-import @xyflow/react in zettel graph view"
```

---

### Task 11: Frontend — Add Skeleton Loading States

**Files:**
- Create: web/app/(app)/knowledge/_components/knowledge-skeleton.tsx
- Create: web/app/(app)/notes/_components/notes-skeleton.tsx
- Create: web/app/(app)/documents/_components/documents-skeleton.tsx
- Modify: web/app/(app)/knowledge/_components/knowledge-hub.tsx

- [ ] **Step 1: Create knowledge skeleton**

```tsx
// web/app/(app)/knowledge/_components/knowledge-skeleton.tsx
export function KnowledgeSkeleton() {
  return (
    <div className="p-6">
      <div className="mb-6 flex gap-3">
        <div className="h-9 w-32 animate-pulse rounded-md bg-muted" />
        <div className="h-9 w-32 animate-pulse rounded-md bg-muted" />
        <div className="ml-auto h-9 w-48 animate-pulse rounded-md bg-muted" />
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {Array.from({ length: 9 }).map((_, i) => (
          <div key={i} className="h-36 animate-pulse rounded-lg bg-muted" />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create notes skeleton**

```tsx
// web/app/(app)/notes/_components/notes-skeleton.tsx
export function NotesSkeleton() {
  return (
    <div className="flex h-full">
      <div className="w-64 space-y-2 border-r p-4">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="h-10 animate-pulse rounded-md bg-muted" />
        ))}
      </div>
      <div className="flex-1 p-8">
        <div className="mb-4 h-8 w-64 animate-pulse rounded-md bg-muted" />
        <div className="space-y-3">
          {Array.from({ length: 12 }).map((_, i) => (
            <div
              key={i}
              className="h-4 animate-pulse rounded bg-muted"
              style={{ width: `${60 + Math.random() * 40}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create documents skeleton**

```tsx
// web/app/(app)/documents/_components/documents-skeleton.tsx
export function DocumentsSkeleton() {
  return (
    <div className="p-6">
      <div className="mb-6 flex gap-3">
        <div className="h-9 w-40 animate-pulse rounded-md bg-muted" />
        <div className="ml-auto h-9 w-48 animate-pulse rounded-md bg-muted" />
      </div>
      <div className="space-y-3">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <div className="h-12 w-12 animate-pulse rounded-md bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-2/3 animate-pulse rounded bg-muted" />
              <div className="h-3 w-1/3 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Integrate skeleton into knowledge hub**

In web/app/(app)/knowledge/_components/knowledge-hub.tsx, import and use:

```typescript
import { KnowledgeSkeleton } from "./knowledge-skeleton";

// Early return for loading state (before existing return):
if (isLoading) {
  return <KnowledgeSkeleton />;
}
```

Apply the same pattern to notes and documents pages.

- [ ] **Step 5: Verify skeletons render**

Open dev server with network throttled (Slow 3G in DevTools). Navigate to Knowledge. Verify skeleton shows immediately.

- [ ] **Step 6: Commit**

```bash
git add "web/app/(app)/knowledge/_components/knowledge-skeleton.tsx" "web/app/(app)/notes/_components/notes-skeleton.tsx" "web/app/(app)/documents/_components/documents-skeleton.tsx" "web/app/(app)/knowledge/_components/knowledge-hub.tsx"
git commit -m "feat: add skeleton loading states for knowledge, notes, documents"
```

---

## Execution Order

Tasks are independent and can run in parallel where noted:

```
Backend (can all run in parallel):
  Task 1 (cache utility) --> Task 5 (Cache-Control headers)
  Task 2 (N+1 fix)
  Task 3 (Qdrant search)
  Task 4 (Celery canvas)

Frontend (sequential dependency chain + parallel):
  Task 6 (staleTime) --> Task 7 (queryOptions) --> Task 8 (hover prefetch)
  Task 9 (memoize sidebar)     -- parallel with 6-8
  Task 10 (dynamic xyflow)     -- parallel with everything
  Task 11 (skeletons)          -- parallel with everything
```

Backend tasks (1-5) are fully independent of frontend tasks (6-11).
