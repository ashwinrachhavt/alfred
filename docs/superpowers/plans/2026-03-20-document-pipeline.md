# Document Ingestion Pipeline — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Build a LangGraph-based document processing pipeline that automatically runs chunk, extract, classify, embed, persist on every ingested document, with PostgreSQL checkpointing for replay and recovery.

**Architecture:** Single LangGraph StateGraph with one node per processing stage. Each document gets a thread_id keyed to its doc_id. PostgresCheckpointSaver (already in codebase) persists state after every node. A Celery task wraps graph.invoke() for async triggering. A pipeline_stage_cache table prevents redundant LLM calls on replay.

**Tech Stack:** LangGraph 0.4.10, PostgreSQL (SQLModel/Alembic), Celery + Redis, Qdrant, OpenAI (via ExtractionService)

**Design Spec:** ~/.gstack/projects/ashwinrachhavt-alfred/ashwinrachha-alfred-revamp-design-20260320-153719.md

---

## File Structure

```
apps/alfred/
  pipeline/
    __init__.py              # Package init + build_pipeline_graph() factory
    state.py                 # DocumentPipelineState TypedDict
    cache.py                 # PipelineStageCache: PG-backed LLM result cache
    router.py                # replay_from routing logic + prerequisite validation
    nodes/
      __init__.py            # Re-export all node functions
      load_document.py       # Fetch DocumentRow from PG -> populate state
      chunk.py               # ChunkingService.chunk() wrapper
      extract.py             # ExtractionService.extract_all() + extract_graph() wrapper
      classify.py            # ExtractionService.classify_taxonomy() wrapper
      embed.py               # KnowledgeService.index_documents() wrapper
      persist.py             # Write enrichment/chunks/classification back to DocumentRow
    graph.py                 # StateGraph definition, node wiring, checkpointer setup
  tasks/
    document_pipeline.py     # Celery task: run_document_pipeline(doc_id, user_id, ...)
  api/
    pipeline/
      __init__.py            # Router export
      routes.py              # /api/pipeline/ status, replay, batch-replay endpoints
  migrations/versions/
    a1b2c3d4e5f6_add_pipeline_stage_cache.py  # Alembic migration

tests/alfred/pipeline/
  test_state.py              # State schema validation
  test_cache.py              # Cache hit/miss/force-replay
  test_nodes.py              # Each node in isolation with mocked services
  test_router.py             # replay_from routing + prerequisite guard
  test_graph.py              # End-to-end graph with in-memory checkpointer
  test_pipeline_api.py       # API endpoint tests
```

---

### Task 1: Pipeline State Schema

**Files:**
- Create: `apps/alfred/pipeline/__init__.py`
- Create: `apps/alfred/pipeline/state.py`
- Test: `tests/alfred/pipeline/test_state.py`

- [ ] **Step 1: Create test file for state schema**

```python
# tests/alfred/pipeline/test_state.py
from __future__ import annotations

from alfred.pipeline.state import DocumentPipelineState, STAGE_ORDER


def test_state_has_required_keys():
    """State TypedDict has all expected keys."""
    keys = DocumentPipelineState.__annotations__
    assert "doc_id" in keys
    assert "cleaned_text" in keys
    assert "chunks" in keys
    assert "enrichment" in keys
    assert "errors" in keys
    assert "stage" in keys


def test_stage_order_is_complete():
    """STAGE_ORDER lists all backbone stages."""
    assert STAGE_ORDER == [
        "load_document",
        "chunk",
        "extract",
        "classify",
        "embed",
        "persist",
    ]


def test_stage_prerequisites():
    """Each stage's prerequisite output fields are defined."""
    from alfred.pipeline.state import STAGE_PREREQUISITES

    # extract needs chunks to exist (from chunk stage)
    assert "chunks" not in STAGE_PREREQUISITES["chunk"]
    assert "cleaned_text" in STAGE_PREREQUISITES["extract"]
    assert "chunks" in STAGE_PREREQUISITES["embed"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_state.py -v`
Expected: FAIL with ModuleNotFoundError: No module named 'alfred.pipeline'

- [ ] **Step 3: Create pipeline package, test package init, and state module**

```python
# tests/alfred/pipeline/__init__.py
# (empty file to make this a test package)
```

```python
# apps/alfred/pipeline/__init__.py
"""Document ingestion pipeline -- LangGraph state machine."""
```

```python
# apps/alfred/pipeline/state.py
"""Pipeline state schema and stage metadata."""

from __future__ import annotations

from typing import Any, TypedDict


class DocumentPipelineState(TypedDict, total=False):
    # Identity
    doc_id: str
    user_id: str

    # Content (loaded from DB, flows through all stages)
    title: str
    cleaned_text: str
    raw_markdown: str
    content_hash: str  # mapped from DocumentRow.hash

    # Stage outputs (accumulated as pipeline progresses)
    chunks: list[dict[str, Any]]       # DocumentIngestChunk.model_dump() per chunk
    enrichment: dict[str, Any]         # from extract node
    classification: dict[str, Any]     # from classify node
    embedding_indexed: bool            # from embed node

    # Pipeline metadata
    stage: str                         # current stage name
    errors: list[dict[str, Any]]       # [{stage, error, timestamp}]
    cache_hits: list[str]              # stages that returned cached results
    force_replay: bool                 # bypass cache for all stages
    replay_from: str | None            # skip stages before this one


# Ordered list of backbone pipeline stages
STAGE_ORDER: list[str] = [
    "load_document",
    "chunk",
    "extract",
    "classify",
    "embed",
    "persist",
]

# For each stage, the state fields that must be non-empty for it to run.
# Used by the replay router to validate replay_from targets.
STAGE_PREREQUISITES: dict[str, list[str]] = {
    "load_document": [],
    "chunk": ["cleaned_text"],
    "extract": ["cleaned_text"],
    "classify": ["cleaned_text"],
    "embed": ["chunks"],
    "persist": ["chunks", "enrichment"],
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_state.py -v`
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/pipeline/__init__.py apps/alfred/pipeline/state.py tests/alfred/pipeline/__init__.py tests/alfred/pipeline/test_state.py
git commit -m "feat(pipeline): add state schema and stage metadata"
```

---

### Task 2: Pipeline Stage Cache

**Files:**
- Create: `apps/alfred/pipeline/cache.py`
- Create: `apps/alfred/migrations/versions/a1b2c3d4e5f6_add_pipeline_stage_cache.py`
- Test: `tests/alfred/pipeline/test_cache.py`

- [ ] **Step 1: Write cache tests**

```python
# tests/alfred/pipeline/test_cache.py
from __future__ import annotations

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine

from alfred.pipeline.cache import PipelineStageCache, PipelineStageCacheRow


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_cache_miss(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    result = cache.get("extract", "abc123")
    assert result is None


def test_cache_set_and_hit(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    data = {"summary": {"short": "test"}, "topics": {}}
    cache.set("extract", "abc123", data)
    result = cache.get("extract", "abc123")
    assert result == data


def test_cache_overwrite(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    cache.set("extract", "abc123", {"v": 1})
    cache.set("extract", "abc123", {"v": 2})
    assert cache.get("extract", "abc123") == {"v": 2}


def test_cache_different_stages(db_session: Session):
    cache = PipelineStageCache(session=db_session)
    cache.set("extract", "abc123", {"stage": "extract"})
    cache.set("classify", "abc123", {"stage": "classify"})
    assert cache.get("extract", "abc123")["stage"] == "extract"
    assert cache.get("classify", "abc123")["stage"] == "classify"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_cache.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement cache module**

```python
# apps/alfred/pipeline/cache.py
"""PostgreSQL-backed stage result cache for LLM-calling pipeline nodes."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlmodel import Field, Session, SQLModel, select

logger = logging.getLogger(__name__)


class PipelineStageCacheRow(SQLModel, table=True):
    __tablename__ = "pipeline_stage_cache"
    __table_args__ = (
        sa.UniqueConstraint("stage", "content_hash", name="uq_stage_content_hash"),
    )

    id: int | None = Field(default=None, primary_key=True)
    stage: str = Field(index=True)
    content_hash: str = Field(index=True)
    result_json: str  # JSON-serialized result
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )


class PipelineStageCache:
    """Simple cache: (stage, content_hash) -> result dict."""

    def __init__(self, *, session: Session) -> None:
        self._session = session

    def get(self, stage: str, content_hash: str) -> dict[str, Any] | None:
        stmt = select(PipelineStageCacheRow).where(
            PipelineStageCacheRow.stage == stage,
            PipelineStageCacheRow.content_hash == content_hash,
        )
        row = self._session.exec(stmt).first()
        if row is None:
            return None
        return json.loads(row.result_json)

    def set(self, stage: str, content_hash: str, result: dict[str, Any]) -> None:
        stmt = select(PipelineStageCacheRow).where(
            PipelineStageCacheRow.stage == stage,
            PipelineStageCacheRow.content_hash == content_hash,
        )
        row = self._session.exec(stmt).first()
        serialized = json.dumps(result, default=str)
        if row is not None:
            row.result_json = serialized
            row.created_at = datetime.now(timezone.utc)
        else:
            row = PipelineStageCacheRow(
                stage=stage,
                content_hash=content_hash,
                result_json=serialized,
            )
            self._session.add(row)
        self._session.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_cache.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Create Alembic migration**

Note: Before writing this migration, verify the current head revision:
`cd /Users/ashwinrachha/coding/alfred && uv run alembic -c apps/alfred/alembic.ini heads`
If the head is not `0e3c8f9a1b2d`, update `down_revision` accordingly.

```python
# apps/alfred/migrations/versions/a1b2c3d4e5f6_add_pipeline_stage_cache.py
"""add pipeline_stage_cache table

Revision ID: a1b2c3d4e5f6
Revises: 0e3c8f9a1b2d
Create Date: 2026-03-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "0e3c8f9a1b2d"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipeline_stage_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("stage", sa.String(), nullable=False, index=True),
        sa.Column("content_hash", sa.String(), nullable=False, index=True),
        sa.Column("result_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("stage", "content_hash", name="uq_stage_content_hash"),
    )


def downgrade() -> None:
    op.drop_table("pipeline_stage_cache")
```

- [ ] **Step 6: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/pipeline/cache.py apps/alfred/migrations/versions/a1b2c3d4e5f6_add_pipeline_stage_cache.py tests/alfred/pipeline/test_cache.py
git commit -m "feat(pipeline): add stage result cache with Alembic migration"
```

---

### Task 3: Pipeline Router (replay_from logic)

**Files:**
- Create: `apps/alfred/pipeline/router.py`
- Test: `tests/alfred/pipeline/test_router.py`

- [ ] **Step 1: Write router tests**

```python
# tests/alfred/pipeline/test_router.py
from __future__ import annotations

from alfred.pipeline.router import resolve_next_stage
from alfred.pipeline.state import DocumentPipelineState


def test_no_replay_starts_at_chunk():
    """Normal flow: after load_document, go to chunk."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "replay_from": None,
    }
    assert resolve_next_stage(state) == "chunk"


def test_replay_from_extract_with_prerequisites():
    """replay_from=extract works when chunks exist."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "chunks": [{"idx": 0, "text": "hello"}],
        "replay_from": "extract",
    }
    assert resolve_next_stage(state) == "extract"


def test_replay_from_invalid_falls_back():
    """replay_from=embed without chunks falls back to chunk."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "chunks": [],
        "replay_from": "embed",
    }
    # embed needs chunks, chunks is empty -> fall back to earliest incomplete
    assert resolve_next_stage(state) == "chunk"


def test_replay_from_classify():
    """replay_from=classify works when cleaned_text exists."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "replay_from": "classify",
    }
    assert resolve_next_stage(state) == "classify"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_router.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement router**

```python
# apps/alfred/pipeline/router.py
"""Conditional routing for replay_from and stage skipping."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import STAGE_ORDER, STAGE_PREREQUISITES, DocumentPipelineState

logger = logging.getLogger(__name__)

# Stages after load_document that the router can target
_ROUTABLE_STAGES = STAGE_ORDER[1:]  # ["chunk", "extract", "classify", "embed", "persist"]


def _prerequisites_met(state: dict[str, Any], stage: str) -> bool:
    """Check if all prerequisite fields for a stage are non-empty in state."""
    for field in STAGE_PREREQUISITES.get(stage, []):
        value = state.get(field)
        if not value:  # None, empty list, empty string, empty dict
            return False
    return True


def _earliest_incomplete_stage(state: dict[str, Any]) -> str:
    """Find the first stage whose prerequisites aren't met, or default to chunk."""
    for stage in _ROUTABLE_STAGES:
        if not _prerequisites_met(state, stage):
            return stage
    return "persist"


def resolve_next_stage(state: DocumentPipelineState) -> str:
    """Determine which stage to route to after load_document.

    If replay_from is set and its prerequisites are met, jump there.
    Otherwise, fall back to the earliest incomplete stage.
    """
    target = state.get("replay_from")

    if target and target in _ROUTABLE_STAGES:
        if _prerequisites_met(state, target):
            logger.info("Routing to replay target: %s", target)
            return target
        logger.warning(
            "replay_from=%s but prerequisites not met; falling back",
            target,
        )

    return _earliest_incomplete_stage(state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_router.py -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/pipeline/router.py tests/alfred/pipeline/test_router.py
git commit -m "feat(pipeline): add replay router with prerequisite validation"
```

---

### Task 4: Pipeline Nodes

**Files:**
- Create: `apps/alfred/pipeline/nodes/__init__.py`
- Create: `apps/alfred/pipeline/nodes/load_document.py`
- Create: `apps/alfred/pipeline/nodes/chunk.py`
- Create: `apps/alfred/pipeline/nodes/extract.py`
- Create: `apps/alfred/pipeline/nodes/classify.py`
- Create: `apps/alfred/pipeline/nodes/embed.py`
- Create: `apps/alfred/pipeline/nodes/persist.py`
- Test: `tests/alfred/pipeline/test_nodes.py`

- [ ] **Step 1: Write node tests**

```python
# tests/alfred/pipeline/test_nodes.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alfred.pipeline.state import DocumentPipelineState


# -- load_document --


def test_load_document_populates_state():
    from alfred.pipeline.nodes.load_document import load_document

    mock_svc = MagicMock()
    mock_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test Doc",
        "cleaned_text": "Hello world",
        "raw_markdown": "# Hello world",
    }

    state: DocumentPipelineState = {"doc_id": "d1", "errors": []}

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=mock_svc,
    ):
        result = load_document(state)

    assert result["title"] == "Test Doc"
    assert result["cleaned_text"] == "Hello world"
    # content_hash is computed from cleaned_text via sha256
    import hashlib
    expected_hash = hashlib.sha256(b"Hello world").hexdigest()
    assert result["content_hash"] == expected_hash
    assert result["stage"] == "load_document"


@patch("alfred.pipeline.nodes.load_document.time")
def test_load_document_not_found_retries_then_raises(mock_time):
    from alfred.pipeline.nodes.load_document import load_document

    mock_svc = MagicMock()
    mock_svc.get_document_details.return_value = None

    state: DocumentPipelineState = {"doc_id": "missing", "errors": []}

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=mock_svc,
    ):
        with pytest.raises(ValueError, match="not found after retry"):
            load_document(state)

    # Verify it retried once with 2s sleep
    mock_time.sleep.assert_called_once_with(2)
    assert mock_svc.get_document_details.call_count == 2


# -- chunk --


def test_chunk_node():
    from alfred.pipeline.nodes.chunk import chunk

    mock_svc = MagicMock()
    mock_svc.chunk.return_value = [
        MagicMock(
            **{"model_dump.return_value": {"idx": 0, "text": "Hello", "tokens": 1}}
        )
    ]

    state: DocumentPipelineState = {"cleaned_text": "Hello world", "errors": []}

    with patch(
        "alfred.pipeline.nodes.chunk._get_chunking_service",
        return_value=mock_svc,
    ):
        result = chunk(state)

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["idx"] == 0
    assert result["stage"] == "chunk"


# -- extract --


def test_extract_node_merges_graph():
    from alfred.pipeline.nodes.extract import extract

    mock_svc = MagicMock()
    mock_svc.extract_all.return_value = {
        "summary": {"short": "test"},
        "topics": {},
        "tags": ["ai"],
        "entities": [],
        "embedding": [0.1],
        "lang": "en",
    }
    mock_svc.extract_graph.return_value = {
        "entities": [{"name": "AI", "type": "concept"}],
        "relations": [{"from": "AI", "to": "ML", "type": "related"}],
        "topics": ["machine learning"],
    }

    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    state: DocumentPipelineState = {
        "cleaned_text": "AI and ML",
        "content_hash": "abc",
        "force_replay": False,
        "cache_hits": [],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.extract._get_extraction_service",
        return_value=mock_svc,
    ), patch(
        "alfred.pipeline.nodes.extract._get_cache",
        return_value=mock_cache,
    ):
        result = extract(state)

    assert "relations" in result["enrichment"]
    assert result["enrichment"]["relations"][0]["from"] == "AI"
    assert result["stage"] == "extract"


# -- classify --


def test_classify_node():
    from alfred.pipeline.nodes.classify import classify

    mock_svc = MagicMock()
    mock_svc.classify_taxonomy.return_value = {
        "domain": "Technology",
        "subdomain": "AI",
        "microtopics": ["NLP"],
        "topic": {"title": "NLP", "confidence": 0.9},
    }

    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    state: DocumentPipelineState = {
        "cleaned_text": "NLP text",
        "content_hash": "abc",
        "force_replay": False,
        "cache_hits": [],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.classify._get_extraction_service",
        return_value=mock_svc,
    ), patch(
        "alfred.pipeline.nodes.classify._get_cache",
        return_value=mock_cache,
    ):
        result = classify(state)

    assert result["classification"]["domain"] == "Technology"
    assert result["stage"] == "classify"


# -- embed --


def test_embed_node():
    from alfred.pipeline.nodes.embed import embed

    mock_svc = MagicMock()
    mock_svc.index_documents.return_value = ["d1:0", "d1:1"]

    state: DocumentPipelineState = {
        "doc_id": "d1",
        "chunks": [
            {"idx": 0, "text": "chunk 0", "section": None, "char_start": 0, "char_end": 7},
            {"idx": 1, "text": "chunk 1", "section": None, "char_start": 8, "char_end": 15},
        ],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.embed._get_knowledge_service",
        return_value=mock_svc,
    ):
        result = embed(state)

    assert result["embedding_indexed"] is True
    assert result["stage"] == "embed"
    call_args = mock_svc.index_documents.call_args[0][0]
    assert call_args[0]["id"] == "d1:0"
    assert call_args[0]["text"] == "chunk 0"


# -- persist --


def test_persist_node():
    from alfred.pipeline.nodes.persist import persist

    mock_svc = MagicMock()

    state: DocumentPipelineState = {
        "doc_id": "d1",
        "chunks": [{"idx": 0, "text": "test"}],
        "enrichment": {"summary": {"short": "test"}, "topics": {}, "tags": []},
        "classification": {"domain": "Tech"},
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.persist._get_doc_storage",
        return_value=mock_svc,
    ):
        result = persist(state)

    assert result["stage"] == "persist"
    mock_svc.update_document_enrichment.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_nodes.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create nodes package init**

```python
# apps/alfred/pipeline/nodes/__init__.py
"""Pipeline node functions -- one per processing stage."""

from alfred.pipeline.nodes.chunk import chunk
from alfred.pipeline.nodes.classify import classify
from alfred.pipeline.nodes.embed import embed
from alfred.pipeline.nodes.extract import extract
from alfred.pipeline.nodes.load_document import load_document
from alfred.pipeline.nodes.persist import persist

__all__ = ["chunk", "classify", "embed", "extract", "load_document", "persist"]
```

- [ ] **Step 4: Implement load_document node**

Note: `get_document_details()` does NOT return `hash` in its dict. We use
`get_document_text()` to get cleaned_text, then compute the hash ourselves
using the same utility the ingestion mixin uses. We also retry once with 2s
backoff if the doc is not found (race condition with ingestion).

```python
# apps/alfred/pipeline/nodes/load_document.py
"""Load a document from PostgreSQL into pipeline state."""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_doc_storage():
    from alfred.core.dependencies import get_doc_storage_service

    return get_doc_storage_service()


def load_document(state: DocumentPipelineState) -> dict[str, Any]:
    """Fetch DocumentRow and populate content fields in state.

    Retries once with 2s backoff if doc not found (ingestion race condition).
    """
    doc_id = state["doc_id"]
    svc = _get_doc_storage()

    doc = svc.get_document_details(doc_id)
    if doc is None:
        logger.warning("Document %s not found, retrying in 2s...", doc_id)
        time.sleep(2)
        doc = svc.get_document_details(doc_id)
    if doc is None:
        raise ValueError(f"Document {doc_id} not found after retry")

    cleaned_text = doc.get("cleaned_text") or ""
    content_hash = hashlib.sha256(cleaned_text.encode()).hexdigest()

    logger.info("Loaded document %s: %s", doc_id, doc.get("title", "untitled"))

    return {
        "title": doc.get("title") or "untitled",
        "cleaned_text": cleaned_text,
        "raw_markdown": doc.get("raw_markdown") or "",
        "content_hash": content_hash,
        "stage": "load_document",
    }
```

- [ ] **Step 5: Implement chunk node**

```python
# apps/alfred/pipeline/nodes/chunk.py
"""Split document text into retrieval-ready chunks."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_chunking_service():
    from alfred.services.chunking import ChunkingService

    return ChunkingService()


def chunk(state: DocumentPipelineState) -> dict[str, Any]:
    """Chunk cleaned_text using ChunkingService."""
    svc = _get_chunking_service()
    raw_chunks = svc.chunk(state["cleaned_text"])
    chunks = [c.model_dump() for c in raw_chunks]

    logger.info("Chunked document into %d pieces", len(chunks))

    return {
        "chunks": chunks,
        "stage": "chunk",
    }
```

- [ ] **Step 6: Implement extract node**

Note: `get_extraction_service()` may return `None` if extraction is disabled
in settings. We guard against this. Also, we use a standalone DB session via
`_get_session()` (not the FastAPI request-scoped `get_db_session`). We pass
`raw_markdown` to `extract_all()` for richer extraction.

```python
# apps/alfred/pipeline/nodes/extract.py
"""Extract summaries, topics, entities, and relations from document text."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_extraction_service():
    from alfred.core.dependencies import get_extraction_service

    svc = get_extraction_service()
    if svc is None:
        raise RuntimeError(
            "ExtractionService is not available. Check extraction settings."
        )
    return svc


def _get_cache():
    from alfred.core.dependencies import get_doc_storage_service
    from alfred.pipeline.cache import PipelineStageCache

    # Reuse the doc storage service's session factory for a standalone session
    svc = get_doc_storage_service()
    session = svc._get_session()
    return PipelineStageCache(session=session)


def extract(state: DocumentPipelineState) -> dict[str, Any]:
    """Run extract_all + extract_graph and merge into enrichment dict."""
    content_hash = state.get("content_hash", "")
    force = state.get("force_replay", False)
    cache_hits = list(state.get("cache_hits", []))

    # Check cache
    if not force:
        cache = _get_cache()
        cached = cache.get("extract", content_hash)
        if cached is not None:
            logger.info("Cache hit for extract:%s", content_hash)
            cache_hits.append("extract")
            return {
                "enrichment": cached,
                "cache_hits": cache_hits,
                "stage": "extract",
            }

    svc = _get_extraction_service()

    # Run both extraction methods, passing raw_markdown for richer results
    enrichment = svc.extract_all(
        cleaned_text=state["cleaned_text"],
        raw_markdown=state.get("raw_markdown"),
    )
    graph_data = svc.extract_graph(text=state["cleaned_text"])

    # Merge graph relations into enrichment
    enrichment["relations"] = graph_data.get("relations", [])
    # Prefer graph entities if richer
    if graph_data.get("entities"):
        enrichment["entities"] = graph_data["entities"]

    # Cache result
    if not force:
        cache = _get_cache()
        cache.set("extract", content_hash, enrichment)

    logger.info(
        "Extracted: %d entities, %d relations",
        len(enrichment.get("entities") or []),
        len(enrichment.get("relations") or []),
    )

    return {"enrichment": enrichment, "cache_hits": cache_hits, "stage": "extract"}
```

- [ ] **Step 7: Implement classify node**

```python
# apps/alfred/pipeline/nodes/classify.py
"""Classify document into domain/subdomain taxonomy."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_extraction_service():
    from alfred.core.dependencies import get_extraction_service

    svc = get_extraction_service()
    if svc is None:
        raise RuntimeError(
            "ExtractionService is not available. Check extraction settings."
        )
    return svc


def _get_cache():
    from alfred.core.dependencies import get_doc_storage_service
    from alfred.pipeline.cache import PipelineStageCache

    svc = get_doc_storage_service()
    session = svc._get_session()
    return PipelineStageCache(session=session)


def classify(state: DocumentPipelineState) -> dict[str, Any]:
    """Run taxonomy classification on document text."""
    content_hash = state.get("content_hash", "")
    force = state.get("force_replay", False)
    cache_hits = list(state.get("cache_hits", []))

    if not force:
        cache = _get_cache()
        cached = cache.get("classify", content_hash)
        if cached is not None:
            logger.info("Cache hit for classify:%s", content_hash)
            cache_hits.append("classify")
            return {
                "classification": cached,
                "cache_hits": cache_hits,
                "stage": "classify",
            }

    svc = _get_extraction_service()
    classification = svc.classify_taxonomy(text=state["cleaned_text"])

    if not force:
        cache = _get_cache()
        cache.set("classify", content_hash, classification)

    logger.info("Classified: domain=%s", classification.get("domain"))

    return {
        "classification": classification,
        "cache_hits": cache_hits,
        "stage": "classify",
    }
```

- [ ] **Step 8: Implement embed node**

```python
# apps/alfred/pipeline/nodes/embed.py
"""Index document chunks into Qdrant vector store."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_knowledge_service():
    from alfred.services.knowledge import KnowledgeService

    return KnowledgeService()


def embed(state: DocumentPipelineState) -> dict[str, Any]:
    """Transform chunks to Qdrant format and index."""
    doc_id = state["doc_id"]
    chunks = state.get("chunks", [])

    if not chunks:
        logger.warning("No chunks to embed for %s", doc_id)
        return {"embedding_indexed": False, "stage": "embed"}

    svc = _get_knowledge_service()

    # Transform chunks to KnowledgeService format
    index_docs = [
        {
            "id": f"{doc_id}:{chunk['idx']}",
            "text": chunk["text"],
            "meta": {
                "doc_id": doc_id,
                "section": chunk.get("section"),
                "char_start": chunk.get("char_start"),
                "char_end": chunk.get("char_end"),
            },
        }
        for chunk in chunks
    ]

    ids = svc.index_documents(index_docs)
    logger.info("Indexed %d chunks for %s", len(ids), doc_id)

    return {"embedding_indexed": True, "stage": "embed"}
```

- [ ] **Step 9: Implement persist node**

```python
# apps/alfred/pipeline/nodes/persist.py
"""Write pipeline results back to the DocumentRow in PostgreSQL."""

from __future__ import annotations

import logging
from typing import Any

from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _get_doc_storage():
    from alfred.core.dependencies import get_doc_storage_service

    return get_doc_storage_service()


def persist(state: DocumentPipelineState) -> dict[str, Any]:
    """Write enrichment, classification, and chunks back to DocumentRow."""
    doc_id = state["doc_id"]
    svc = _get_doc_storage()

    enrichment = state.get("enrichment", {})
    classification = state.get("classification", {})

    update_data = {
        "enrichment": enrichment,
        "summary": enrichment.get("summary"),
        "topics": enrichment.get("topics") or classification.get("topic"),
        "tags": enrichment.get("tags", []),
        "entities": enrichment.get("entities"),
        "embedding": enrichment.get("embedding"),
        "concepts": {
            "entities": enrichment.get("entities", []),
            "relations": enrichment.get("relations", []),
            "topics": classification.get("microtopics", []),
            "domain": classification.get("domain"),
            "subdomain": classification.get("subdomain"),
        },
    }

    svc.update_document_enrichment(doc_id, update_data)
    logger.info("Persisted pipeline results for %s", doc_id)

    return {"stage": "persist"}
```

- [ ] **Step 10: Run all node tests**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_nodes.py -v`
Expected: 7 PASSED

- [ ] **Step 11: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/pipeline/nodes/ tests/alfred/pipeline/test_nodes.py
git commit -m "feat(pipeline): add all backbone pipeline nodes"
```

---

### Task 5: LangGraph Graph Definition

**Files:**
- Modify: `apps/alfred/pipeline/__init__.py`
- Create: `apps/alfred/pipeline/graph.py`
- Test: `tests/alfred/pipeline/test_graph.py`

- [ ] **Step 1: Write graph integration test**

```python
# tests/alfred/pipeline/test_graph.py
"""End-to-end pipeline graph test with mocked services."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from alfred.pipeline.graph import build_pipeline_graph
from alfred.pipeline.state import DocumentPipelineState


def _mock_all_services():
    """Return a dict of patch targets to mock objects."""
    doc_svc = MagicMock()
    doc_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test",
        "cleaned_text": "Hello world content",
        "raw_markdown": "# Hello",
        "hash": "testhash123",
    }
    doc_svc.update_document_enrichment.return_value = None

    chunk_svc = MagicMock()
    chunk_svc.chunk.return_value = [
        MagicMock(
            **{
                "model_dump.return_value": {
                    "idx": 0,
                    "text": "Hello world",
                    "tokens": 2,
                    "section": None,
                    "char_start": 0,
                    "char_end": 11,
                }
            }
        )
    ]

    extract_svc = MagicMock()
    extract_svc.extract_all.return_value = {
        "summary": {"short": "test"},
        "topics": {},
        "tags": ["test"],
        "entities": [],
        "embedding": [0.1, 0.2],
        "lang": "en",
    }
    extract_svc.extract_graph.return_value = {
        "entities": [{"name": "Hello", "type": "concept"}],
        "relations": [],
        "topics": [],
    }
    extract_svc.classify_taxonomy.return_value = {
        "domain": "Test",
        "subdomain": "Unit",
        "microtopics": [],
        "topic": {"title": "Test", "confidence": 1.0},
    }

    knowledge_svc = MagicMock()
    knowledge_svc.index_documents.return_value = ["d1:0"]

    cache = MagicMock()
    cache.get.return_value = None
    cache.set.return_value = None

    return {
        "alfred.pipeline.nodes.load_document._get_doc_storage": doc_svc,
        "alfred.pipeline.nodes.chunk._get_chunking_service": chunk_svc,
        "alfred.pipeline.nodes.extract._get_extraction_service": extract_svc,
        "alfred.pipeline.nodes.extract._get_cache": cache,
        "alfred.pipeline.nodes.classify._get_extraction_service": extract_svc,
        "alfred.pipeline.nodes.classify._get_cache": cache,
        "alfred.pipeline.nodes.embed._get_knowledge_service": knowledge_svc,
        "alfred.pipeline.nodes.persist._get_doc_storage": doc_svc,
    }


def test_full_pipeline_runs_all_stages():
    """End-to-end: graph runs load, chunk, extract, classify, embed, persist."""
    checkpointer = MemorySaver()
    graph = build_pipeline_graph(checkpointer=checkpointer)

    mocks = _mock_all_services()
    with contextlib.ExitStack() as stack:
        for target, mock_obj in mocks.items():
            stack.enter_context(patch(target, return_value=mock_obj))

        result = graph.invoke(
            {
                "doc_id": "d1",
                "user_id": "u1",
                "errors": [],
                "cache_hits": [],
                "force_replay": False,
                "replay_from": None,
            },
            config={"configurable": {"thread_id": "d1"}},
        )

    assert result["stage"] == "persist"
    assert result["title"] == "Test"
    assert result["embedding_indexed"] is True
    assert len(result["chunks"]) == 1
    assert "enrichment" in result
    assert "classification" in result


def test_pipeline_checkpoint_saves():
    """Pipeline checkpoints after each node."""
    checkpointer = MemorySaver()
    graph = build_pipeline_graph(checkpointer=checkpointer)

    doc_svc = MagicMock()
    doc_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test",
        "cleaned_text": "Hello",
        "raw_markdown": "# Hello",
        "hash": "testhash",
    }

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=doc_svc,
    ):
        try:
            graph.invoke(
                {
                    "doc_id": "d1",
                    "user_id": "u1",
                    "errors": [],
                    "cache_hits": [],
                    "force_replay": False,
                    "replay_from": None,
                },
                config={"configurable": {"thread_id": "d1"}},
            )
        except Exception:
            pass  # Expected: chunk fails without real service

    # Verify checkpoint was saved (load_document completed)
    checkpoint = checkpointer.get_tuple(
        {"configurable": {"thread_id": "d1", "checkpoint_ns": ""}}
    )
    assert checkpoint is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_graph.py::test_full_pipeline_runs_all_stages -v`
Expected: FAIL with ImportError: cannot import name 'build_pipeline_graph'

- [ ] **Step 3: Implement graph builder**

```python
# apps/alfred/pipeline/graph.py
"""LangGraph StateGraph definition for the document pipeline."""

from __future__ import annotations

import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, StateGraph

from alfred.pipeline.nodes import (
    chunk,
    classify,
    embed,
    extract,
    load_document,
    persist,
)
from alfred.pipeline.router import resolve_next_stage
from alfred.pipeline.state import DocumentPipelineState

logger = logging.getLogger(__name__)


def _wrap_node(fn, name: str):
    """Wrap a node function with error logging."""

    def wrapper(state: DocumentPipelineState) -> dict[str, Any]:
        try:
            return fn(state)
        except Exception:
            logger.exception("Pipeline node '%s' failed", name)
            raise  # Let LangGraph checkpoint the failure

    wrapper.__name__ = name
    return wrapper


def build_pipeline_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
) -> Any:
    """Build and compile the document pipeline StateGraph."""

    graph = StateGraph(DocumentPipelineState)

    # Add nodes
    graph.add_node("load_document", _wrap_node(load_document, "load_document"))
    graph.add_node("chunk", _wrap_node(chunk, "chunk"))
    graph.add_node("extract", _wrap_node(extract, "extract"))
    graph.add_node("classify", _wrap_node(classify, "classify"))
    graph.add_node("embed", _wrap_node(embed, "embed"))
    graph.add_node("persist", _wrap_node(persist, "persist"))

    # Entry point
    graph.set_entry_point("load_document")

    # Conditional routing after load_document (handles replay_from)
    graph.add_conditional_edges(
        "load_document",
        resolve_next_stage,
        {
            "chunk": "chunk",
            "extract": "extract",
            "classify": "classify",
            "embed": "embed",
            "persist": "persist",
        },
    )

    # Linear edges for the rest of the backbone
    graph.add_edge("chunk", "extract")
    graph.add_edge("extract", "classify")
    graph.add_edge("classify", "embed")
    graph.add_edge("embed", "persist")
    graph.add_edge("persist", END)

    return graph.compile(checkpointer=checkpointer)
```

- [ ] **Step 4: Update pipeline __init__.py**

```python
# apps/alfred/pipeline/__init__.py
"""Document ingestion pipeline -- LangGraph state machine."""

from alfred.pipeline.graph import build_pipeline_graph

__all__ = ["build_pipeline_graph"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_graph.py -v`
Expected: 2 PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/pipeline/graph.py apps/alfred/pipeline/__init__.py tests/alfred/pipeline/test_graph.py
git commit -m "feat(pipeline): wire LangGraph StateGraph with all backbone nodes"
```

---

### Task 6: Celery Task + Ingestion Hook

**Files:**
- Create: `apps/alfred/tasks/document_pipeline.py`
- Modify: `apps/alfred/core/celery.py:17-28` (add task module)
- Modify: `apps/alfred/core/celery.py:53-62` (add task route)
- Modify: `apps/alfred/core/celery.py:110-117` (add explicit import)
- Modify: `apps/alfred/tasks/__init__.py` (add import)
- Modify: `apps/alfred/services/doc_storage/_ingestion_mixin.py` (add hook)

- [ ] **Step 1: Create Celery task**

```python
# apps/alfred/tasks/document_pipeline.py
"""Celery task to run the document ingestion pipeline."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(
    name="alfred.tasks.document_pipeline.run_document_pipeline",
    bind=True,
    max_retries=2,
    default_retry_delay=5,
)
def run_document_pipeline(
    self,
    *,
    doc_id: str,
    user_id: str = "",
    force_replay: bool = False,
    replay_from: str | None = None,
) -> dict:
    """Run the document pipeline graph for a single document."""
    from alfred.core.settings import settings
    from alfred.pipeline.graph import build_pipeline_graph
    from alfred.services.checkpoint_postgres import (
        PostgresCheckpointConfig,
        PostgresCheckpointSaver,
    )

    dsn = settings.writer_checkpoint_dsn or settings.database_url.replace(
        "postgresql+psycopg", "postgresql"
    )

    checkpointer = PostgresCheckpointSaver(
        cfg=PostgresCheckpointConfig(dsn=dsn)
    )
    graph = build_pipeline_graph(checkpointer=checkpointer)

    initial_state = {
        "doc_id": doc_id,
        "user_id": user_id,
        "errors": [],
        "cache_hits": [],
        "force_replay": force_replay,
        "replay_from": replay_from,
    }

    thread_id = f"pipeline:{doc_id}"
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result = graph.invoke(initial_state, config=config)
        logger.info(
            "Pipeline completed for %s: stage=%s, cache_hits=%s",
            doc_id,
            result.get("stage"),
            result.get("cache_hits"),
        )
        return {
            "doc_id": doc_id,
            "status": "completed",
            "stage": result.get("stage"),
            "cache_hits": result.get("cache_hits", []),
            "errors": result.get("errors", []),
        }
    except Exception as exc:
        logger.exception("Pipeline failed for %s", doc_id)
        raise self.retry(exc=exc)
```

- [ ] **Step 2: Register task in Celery config**

In `apps/alfred/core/celery.py`, add `"alfred.tasks.document_pipeline"` to `task_modules` list (line ~27, after `"alfred.tasks.notion_import"`).

Add to `task_routes` dict (line ~62):
```python
"alfred.tasks.document_pipeline.*": {"queue": "default"},
```

Add to explicit imports block (line ~117):
```python
import alfred.tasks.document_pipeline  # noqa: F401
```

- [ ] **Step 3: Register task in tasks __init__.py**

Add to `apps/alfred/tasks/__init__.py`:
```python
from . import document_pipeline as document_pipeline
```

- [ ] **Step 4: Hook ingestion to fire pipeline**

In `apps/alfred/services/doc_storage/_ingestion_mixin.py`, in `ingest_document_store_only()`, after the result dict is built and before the return statement, add:

```python
# Fire document pipeline (non-blocking, skip duplicates)
if not result.get("duplicate"):
    try:
        from alfred.tasks.document_pipeline import run_document_pipeline

        run_document_pipeline.delay(
            doc_id=str(result["id"]),
            user_id=payload.metadata.get("user_id", ""),
        )
    except Exception:
        logger.warning(
            "Failed to enqueue pipeline task for %s",
            result["id"],
            exc_info=True,
        )
```

- [ ] **Step 5: Write Celery task test**

```python
# tests/alfred/pipeline/test_celery_task.py
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_run_document_pipeline_calls_graph():
    """Celery task builds graph and invokes with correct state."""
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "doc_id": "d1",
        "stage": "persist",
        "cache_hits": [],
        "errors": [],
    }

    with patch(
        "alfred.tasks.document_pipeline.build_pipeline_graph",
        return_value=mock_graph,
    ), patch(
        "alfred.tasks.document_pipeline.PostgresCheckpointSaver",
    ), patch(
        "alfred.tasks.document_pipeline.settings",
        writer_checkpoint_dsn="postgresql://test",
        database_url="postgresql+psycopg://test",
    ):
        from alfred.tasks.document_pipeline import run_document_pipeline

        # Call the task function directly (not via Celery)
        result = run_document_pipeline(doc_id="d1", user_id="u1")

    assert result["status"] == "completed"
    assert result["doc_id"] == "d1"
    mock_graph.invoke.assert_called_once()

    # Verify initial state passed to graph
    call_args = mock_graph.invoke.call_args
    initial_state = call_args[0][0]
    assert initial_state["doc_id"] == "d1"
    assert initial_state["force_replay"] is False

    # Verify thread_id config
    config = call_args[1]["config"] if "config" in call_args[1] else call_args[0][1]
    assert config["configurable"]["thread_id"] == "pipeline:d1"
```

- [ ] **Step 6: Run Celery task test**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_celery_task.py -v`
Expected: 1 PASSED

- [ ] **Step 7: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/tasks/document_pipeline.py apps/alfred/core/celery.py apps/alfred/tasks/__init__.py apps/alfred/services/doc_storage/_ingestion_mixin.py tests/alfred/pipeline/test_celery_task.py
git commit -m "feat(pipeline): add Celery task and post-ingestion hook"
```

---

### Task 7: Pipeline API Endpoints

**Files:**
- Create: `apps/alfred/api/pipeline/__init__.py`
- Create: `apps/alfred/api/pipeline/routes.py`
- Modify: `apps/alfred/api/__init__.py:11-88` (register router)
- Test: `tests/alfred/pipeline/test_pipeline_api.py`

- [ ] **Step 1: Write API tests**

```python
# tests/alfred/pipeline/test_pipeline_api.py
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alfred.api.pipeline import router


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_replay_endpoint(client: TestClient):
    with patch("alfred.api.pipeline.routes.run_document_pipeline") as mock_task:
        mock_task.delay.return_value = MagicMock(id="task-123")
        resp = client.post("/api/pipeline/d1/replay", params={"force": True})

    assert resp.status_code == 202
    body = resp.json()
    assert body["doc_id"] == "d1"
    assert body["task_id"] == "task-123"
    mock_task.delay.assert_called_once()


def test_status_endpoint(client: TestClient):
    mock_checkpointer = MagicMock()
    mock_checkpointer.get_tuple.return_value = MagicMock(
        checkpoint={
            "channel_values": {
                "stage": "persist",
                "errors": [],
                "cache_hits": ["extract"],
            }
        },
    )

    with patch(
        "alfred.api.pipeline.routes._get_checkpointer",
        return_value=mock_checkpointer,
    ):
        resp = client.get("/api/pipeline/d1/status")

    assert resp.status_code == 200
    body = resp.json()
    assert body["stage"] == "persist"


def test_status_not_found(client: TestClient):
    mock_checkpointer = MagicMock()
    mock_checkpointer.get_tuple.return_value = None

    with patch(
        "alfred.api.pipeline.routes._get_checkpointer",
        return_value=mock_checkpointer,
    ):
        resp = client.get("/api/pipeline/d1/status")

    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_pipeline_api.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement API routes**

```python
# apps/alfred/api/pipeline/__init__.py
from alfred.api.pipeline.routes import router

__all__ = ["router"]
```

```python
# apps/alfred/api/pipeline/routes.py
"""Pipeline replay and status API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


def _get_checkpointer():
    from alfred.core.settings import settings
    from alfred.services.checkpoint_postgres import (
        PostgresCheckpointConfig,
        PostgresCheckpointSaver,
    )

    dsn = settings.writer_checkpoint_dsn or settings.database_url.replace(
        "postgresql+psycopg", "postgresql"
    )
    return PostgresCheckpointSaver(cfg=PostgresCheckpointConfig(dsn=dsn))


@router.post("/{doc_id}/replay", status_code=202)
def replay_document(
    doc_id: str,
    from_stage: str | None = Query(None),
    force: bool = Query(False),
):
    """Replay the pipeline for a document. Dispatches to Celery."""
    from alfred.tasks.document_pipeline import run_document_pipeline

    result = run_document_pipeline.delay(
        doc_id=doc_id,
        force_replay=force,
        replay_from=from_stage,
    )

    return {
        "doc_id": doc_id,
        "task_id": result.id,
        "from_stage": from_stage,
        "force": force,
    }


@router.get("/{doc_id}/status")
def pipeline_status(doc_id: str):
    """Get the current pipeline state for a document."""
    checkpointer = _get_checkpointer()
    thread_id = f"pipeline:{doc_id}"

    checkpoint = checkpointer.get_tuple(
        {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    )
    if checkpoint is None:
        raise HTTPException(status_code=404, detail="No pipeline run found")

    values = checkpoint.checkpoint.get("channel_values", {})
    return {
        "doc_id": doc_id,
        "stage": values.get("stage"),
        "errors": values.get("errors", []),
        "cache_hits": values.get("cache_hits", []),
        "embedding_indexed": values.get("embedding_indexed", False),
    }


@router.post("/replay-batch", status_code=202)
def replay_batch(
    force: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
):
    """Replay pipeline for documents missing enrichment."""
    from alfred.core.dependencies import get_doc_storage_service
    from alfred.tasks.document_pipeline import run_document_pipeline

    svc = get_doc_storage_service()
    docs = svc.list_documents_needing_concepts_extraction(limit=limit)

    task_ids = []
    for doc in docs:
        result = run_document_pipeline.delay(
            doc_id=str(doc["id"]),
            force_replay=force,
        )
        task_ids.append({"doc_id": str(doc["id"]), "task_id": result.id})

    return {"queued": len(task_ids), "tasks": task_ids}
```

- [ ] **Step 4: Register router in api/__init__.py**

In `apps/alfred/api/__init__.py`, add the import inside `register_routes()`:
```python
from alfred.api.pipeline import router as pipeline_router
```

Add `pipeline_router` to the `routers` list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/test_pipeline_api.py -v`
Expected: 3 PASSED

- [ ] **Step 6: Commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/api/pipeline/ tests/alfred/pipeline/test_pipeline_api.py apps/alfred/api/__init__.py
git commit -m "feat(pipeline): add replay and status API endpoints"
```

---

### Task 8: Verify DocStorageService.update_document_enrichment Exists

The persist node calls `svc.update_document_enrichment(doc_id, update_data)`. This method may not exist yet.

**Files:**
- Possibly modify: `apps/alfred/services/doc_storage/_enrichment_mixin.py`

- [ ] **Step 1: Check if the method exists**

Run: `cd /Users/ashwinrachha/coding/alfred && grep -n "def update_document_enrichment" apps/alfred/services/doc_storage/*.py apps/alfred/services/doc_storage_pg.py`

- [ ] **Step 2: If not found, add to the enrichment mixin**

Add to `apps/alfred/services/doc_storage/_enrichment_mixin.py`:

```python
def update_document_enrichment(self, doc_id: str, data: dict[str, Any]) -> None:
    """Bulk-update enrichment fields on a DocumentRow."""
    from datetime import datetime, timezone

    from alfred.models.doc_storage import DocumentRow

    with self._get_session() as session:
        stmt = select(DocumentRow).where(DocumentRow.id == doc_id)
        doc = session.exec(stmt).first()
        if doc is None:
            logger.warning("update_document_enrichment: doc %s not found", doc_id)
            return

        for key, value in data.items():
            if hasattr(doc, key):
                setattr(doc, key, value)

        doc.processed_at = datetime.now(timezone.utc)
        session.add(doc)
        session.commit()
```

- [ ] **Step 3: Commit if changes were made**

```bash
cd /Users/ashwinrachha/coding/alfred
git add apps/alfred/services/doc_storage/
git commit -m "feat(pipeline): add update_document_enrichment to DocStorageService"
```

---

### Task 9: Run Full Test Suite

- [ ] **Step 1: Run all pipeline tests**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/alfred/pipeline/ -v`
Expected: All tests pass (approximately 23 tests)

- [ ] **Step 2: Run existing test suite for regressions**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run pytest tests/ -v --timeout=60`
Expected: No new failures

- [ ] **Step 3: Run linter**

Run: `cd /Users/ashwinrachha/coding/alfred && uv run ruff check apps/alfred/pipeline/ tests/alfred/pipeline/`
Expected: No errors

- [ ] **Step 4: Fix any issues and commit**

```bash
cd /Users/ashwinrachha/coding/alfred
git add -A
git commit -m "fix(pipeline): address test and lint issues"
```

---

## Summary

| Task | Description | Files | Tests |
|------|-------------|-------|-------|
| 1 | State schema + stage metadata | 2 created | 3 |
| 2 | Stage result cache + migration | 2 created | 4 |
| 3 | Replay router with prerequisites | 1 created | 4 |
| 4 | All 6 backbone nodes | 7 created | 7 |
| 5 | LangGraph graph definition | 1 created, 1 modified | 2 |
| 6 | Celery task + ingestion hook | 1 created, 3 modified | 1 |
| 7 | API endpoints (replay, status, batch) | 2 created, 1 modified | 3 |
| 8 | Verify/add update_document_enrichment | 0-1 modified | 0 |
| 9 | Full test suite verification | 0 | all |

**Total: ~17 files created, ~5 files modified, ~24 tests**
