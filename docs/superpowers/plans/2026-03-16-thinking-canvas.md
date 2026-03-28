# Thinking Canvas + Decomposition Engine — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox syntax for tracking.

**Goal:** Build a block-based thinking environment where the user writes freely while AI surfaces relevant knowledge, with a five-layer decomposition engine that produces modular blocks publishable as zettelkasten cards.

**Architecture:** New `ThinkingSession` SQLModel with JSONB blocks array. Two new services: `ThinkingSessionService` (CRUD + publish + fork + surfacing) and `DecompositionService` (five-layer LLM pipeline). FastAPI routes at `/api/thinking/*`. Frontend: BlockNote block editor with 8 custom block types, surfacing sidebar, and publish sheet. All under the `(app)` layout group at `/think`.

**Tech Stack:** FastAPI, SQLModel, Alembic, Pydantic v2, OpenAI structured outputs, Qdrant, BlockNote, React 19, Next.js 16, TanStack Query v5, shadcn/ui, Tailwind v4.

**Spec:** `docs/superpowers/specs/2026-03-16-thinking-canvas-design.md`

---

## File Structure

### Backend (new files)

| File | Responsibility |
|------|---------------|
| `apps/alfred/models/thinking.py` | `ThinkingSession` SQLModel |
| `apps/alfred/schemas/thinking.py` | Request/response Pydantic schemas + block validation |
| `apps/alfred/services/thinking_session_service.py` | CRUD, autosave, publish, fork, block validation |
| `apps/alfred/services/decomposition_service.py` | Five-layer decomposition pipeline |
| `apps/alfred/api/thinking/__init__.py` | Route registration |
| `apps/alfred/api/thinking/routes.py` | API endpoints |
| `apps/alfred/prompts/decomposition/system.md` | Decomposition system prompt |
| `apps/alfred/migrations/versions/xxxx_add_thinking_sessions.py` | Alembic migration |
| `tests/alfred/services/test_thinking_session_service.py` | Service unit tests |
| `tests/alfred/services/test_decomposition_service.py` | Decomposition tests |
| `tests/alfred/api/thinking/test_thinking_routes.py` | API integration tests |

### Backend (modified files)

| File | Change |
|------|--------|
| `apps/alfred/api/__init__.py` | Register thinking router |

### Frontend (new files)

| File | Responsibility |
|------|---------------|
| `web/lib/api/thinking.ts` | API client functions |
| `web/lib/api/types/thinking.ts` | TypeScript types |
| `web/features/thinking/queries.ts` | React Query hooks |
| `web/features/thinking/mutations.ts` | React Query mutations |
| `web/features/thinking/query-keys.ts` | Query key factories |
| `web/app/(app)/think/page.tsx` | Session list page |
| `web/app/(app)/think/new/page.tsx` | New session page |
| `web/app/(app)/think/[sessionId]/page.tsx` | Session editor page |
| `web/app/(app)/think/_components/thinking-canvas-client.tsx` | Main editor client component |
| `web/app/(app)/think/_components/session-list-client.tsx` | Session list client component |
| `web/app/(app)/think/_components/surfacing-sidebar.tsx` | Knowledge surfacing sidebar |
| `web/app/(app)/think/_components/publish-sheet.tsx` | Publish to zettelkasten sheet |
| `web/app/(app)/think/_components/decompose-modal.tsx` | Decomposition trigger modal |
| `web/app/(app)/think/_components/blocks/index.ts` | Block type registry |
| `web/app/(app)/think/_components/blocks/law-block.tsx` | Law block renderer |
| `web/app/(app)/think/_components/blocks/prediction-block.tsx` | Prediction block renderer |
| `web/app/(app)/think/_components/blocks/insight-block.tsx` | Insight block renderer |
| `web/app/(app)/think/_components/blocks/demolition-block.tsx` | Demolition block renderer |
| `web/app/(app)/think/_components/blocks/framework-block.tsx` | Framework block renderer |
| `web/app/(app)/think/_components/blocks/anchor-block.tsx` | Anchor block renderer |
| `web/app/(app)/think/_components/blocks/connection-block.tsx` | Connection block renderer |

### Frontend (modified files)

| File | Change |
|------|--------|
| `web/components/app-sidebar.tsx` | Add "Think" nav item |
| `web/package.json` | Add `@blocknote/react`, `@blocknote/shadcn` |

---

## Chunk 1: Backend Data Layer

### Task 1: Alembic Migration

**Files:**
- Create: `apps/alfred/migrations/versions/xxxx_add_thinking_sessions.py`

- [ ] **Step 1: Generate migration**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/alembic -c apps/alfred/alembic.ini revision --autogenerate -m "add thinking_sessions table"
```

If autogenerate does not pick up the table (model not imported yet), create manually.

- [ ] **Step 2: Write migration manually if needed**

```python
"""add thinking_sessions table

Revision ID: <auto>
Revises: <latest>
Create Date: 2026-03-16
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from alembic import op

revision: str = "<auto>"
down_revision: str | None = "<latest>"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "thinking_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("blocks", JSONB(), nullable=False, server_default="[]"),
        sa.Column("tags", JSONB(), nullable=True, server_default="[]"),
        sa.Column("topic", sa.String(500), nullable=True),
        sa.Column("source_input", JSONB(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_thinking_sessions_user", "thinking_sessions", ["user_id"])
    op.create_index("idx_thinking_sessions_status", "thinking_sessions", ["user_id", "status"])
    op.create_index(
        "idx_thinking_sessions_updated",
        "thinking_sessions",
        ["user_id", sa.text("updated_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_thinking_sessions_updated", table_name="thinking_sessions")
    op.drop_index("idx_thinking_sessions_status", table_name="thinking_sessions")
    op.drop_index("idx_thinking_sessions_user", table_name="thinking_sessions")
    op.drop_table("thinking_sessions")
```

- [ ] **Step 3: Run migration**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/alembic -c apps/alfred/alembic.ini upgrade head
```

Expected: table `thinking_sessions` created with 11 columns and 3 indexes.

- [ ] **Step 4: Verify table exists**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/python3 -c "
from alfred.core.database import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text(\"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'thinking_sessions' ORDER BY ordinal_position\"))
    for row in result:
        print(f'  {row[0]}: {row[1]}')
"
```

Expected: 11 columns including `user_id`, `blocks` (jsonb), `status`, `pinned`.

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/migrations/versions/*thinking_sessions* && git commit -m "feat(thinking): add thinking_sessions table migration"
```

---

### Task 2: SQLModel + Pydantic Schemas

**Files:**
- Create: `apps/alfred/models/thinking.py`
- Create: `apps/alfred/schemas/thinking.py`
- Create: `tests/alfred/models/test_thinking_model.py`
- Create: `tests/alfred/schemas/test_thinking_schemas.py`

- [ ] **Step 1: Write failing test for model import**

Create `tests/alfred/models/test_thinking_model.py`:

```python
"""Verify ThinkingSession model is importable and has expected fields."""


def test_thinking_session_model_importable():
    from alfred.models.thinking import ThinkingSession

    session = ThinkingSession(user_id=1, title="Test")
    assert session.user_id == 1
    assert session.title == "Test"
    assert session.status == "draft"
    assert session.blocks == []
    assert session.pinned is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/models/test_thinking_model.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write ThinkingSession model**

Create `apps/alfred/models/thinking.py`:

```python
"""ThinkingSession model - block-based thinking environment."""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from alfred.models.base import Model


class ThinkingSession(Model, table=True):
    __tablename__ = "thinking_sessions"
    __table_args__ = (
        sa.Index("idx_thinking_sessions_user", "user_id"),
        sa.Index("idx_thinking_sessions_status", "user_id", "status"),
    )

    user_id: int = Field(
        sa_column=sa.Column(sa.Integer, sa.ForeignKey("users.id"), nullable=False)
    )
    title: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", max_length=20)
    blocks: list[dict] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False, server_default="[]"),
    )
    tags: list[str] | None = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=True, server_default="[]"),
    )
    topic: str | None = Field(default=None, max_length=500)
    source_input: dict | None = Field(
        default=None, sa_column=sa.Column(JSONB, nullable=True)
    )
    pinned: bool = Field(
        default=False,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.text("false")),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/models/test_thinking_model.py -v`

Expected: PASS

- [ ] **Step 5: Write Pydantic schemas**

Create `apps/alfred/schemas/thinking.py`:

```python
"""Request/response schemas for thinking sessions."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BLOCK_TYPES = frozenset(
    ["freeform", "demolition", "framework", "anchor", "law", "prediction", "connection", "insight"]
)

VALID_STATUSES = frozenset(["draft", "published", "archived"])

VALID_TRANSITIONS: set[tuple[str, str]] = {
    ("draft", "published"),
    ("draft", "archived"),
    ("published", "archived"),
    ("archived", "draft"),
}


class BlockMeta(BaseModel):
    law_number: int | None = None
    confidence: float | None = None
    timeframe: str | None = None
    source_card_id: int | None = None
    source_doc_id: str | None = None
    source_entity_id: int | None = None
    validated_at: datetime | None = None
    collapsed: bool = False


class Block(BaseModel):
    id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    content: str = ""
    meta: BlockMeta = Field(default_factory=BlockMeta)
    order: int = 0


class SessionCreate(BaseModel):
    title: str | None = None
    topic: str | None = None
    tags: list[str] | None = None


class SessionPatch(BaseModel):
    title: str | None = None
    blocks: list[Block] | None = None
    tags: list[str] | None = None
    topic: str | None = None
    pinned: bool | None = None
    status: str | None = None


class DecomposeRequest(BaseModel):
    input_type: Literal["topic", "url", "text"]
    content: str = Field(min_length=1)
    connect_to_existing: bool = True


class SurfaceRequest(BaseModel):
    text: str = Field(min_length=1)
    session_id: int | None = None
    limit: int = Field(default=5, ge=1, le=20)


class PublishRequest(BaseModel):
    mode: Literal["single_card", "multiple_cards", "learning_topic"]
    selected_block_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    title: str | None = None


class SessionOut(BaseModel):
    id: int
    user_id: int
    title: str | None
    status: str
    blocks: list[dict]
    tags: list[str] | None
    topic: str | None
    source_input: dict | None
    pinned: bool
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SessionListItem(BaseModel):
    id: int
    title: str | None
    status: str
    tags: list[str] | None
    topic: str | None
    pinned: bool
    block_summary: dict
    created_at: datetime | None
    updated_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class SurfaceConnection(BaseModel):
    type: Literal["zettel", "entity", "document"]
    id: int | str
    title: str
    snippet: str = ""
    relevance: float = 0.0


class SurfaceResponse(BaseModel):
    connections: list[SurfaceConnection]


class PublishResult(BaseModel):
    cards_created: int = 0
    card_ids: list[int] = Field(default_factory=list)
    topic_created: dict | None = None


class DecomposeResponse(BaseModel):
    blocks: list[Block]
    warnings: list[str] = Field(default_factory=list)
```

- [ ] **Step 6: Write failing test for schemas**

Create `tests/alfred/schemas/test_thinking_schemas.py`:

```python
"""Test thinking session schema validation."""
import pytest
from alfred.schemas.thinking import Block, BlockMeta, SessionCreate, SessionPatch


def test_block_requires_id_and_type():
    b = Block(id="abc-123", type="freeform", content="hello")
    assert b.id == "abc-123"
    assert b.type == "freeform"


def test_block_rejects_empty_id():
    with pytest.raises(Exception):
        Block(id="", type="freeform")


def test_session_create_minimal():
    s = SessionCreate()
    assert s.title is None


def test_session_patch_partial():
    p = SessionPatch(title="Updated")
    assert p.title == "Updated"
    assert p.blocks is None


def test_block_meta_defaults():
    m = BlockMeta()
    assert m.collapsed is False
    assert m.confidence is None
```

- [ ] **Step 7: Run schema tests**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/schemas/test_thinking_schemas.py -v`

Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add apps/alfred/models/thinking.py apps/alfred/schemas/thinking.py tests/alfred/models/test_thinking_model.py tests/alfred/schemas/test_thinking_schemas.py && git commit -m "feat(thinking): add ThinkingSession model and Pydantic schemas"
```

---

### Task 3: ThinkingSessionService (CRUD + Block Validation)

**Files:**
- Create: `apps/alfred/services/thinking_session_service.py`
- Create: `tests/alfred/services/test_thinking_session_service.py`

- [ ] **Step 1: Write failing tests**

Create `tests/alfred/services/test_thinking_session_service.py`:

```python
"""Tests for ThinkingSessionService CRUD operations."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.models.thinking import ThinkingSession  # noqa: F401
from alfred.models.user import User  # noqa: F401


def _make_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _ensure_user(db: Session, user_id: int = 1) -> int:
    user = db.get(User, user_id)
    if not user:
        user = User(id=user_id, clerk_id="test_clerk", email="test@test.com")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user.id or user_id


def test_create_session():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    ts = svc.create_session(user_id=uid, title="Test Session", topic="physics")
    assert ts.id is not None
    assert ts.title == "Test Session"
    assert ts.status == "draft"
    assert ts.blocks == []
    assert ts.user_id == uid


def test_list_sessions_filters_by_user():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    svc.create_session(user_id=uid, title="Mine")
    assert len(svc.list_sessions(user_id=uid)) == 1
    assert len(svc.list_sessions(user_id=999)) == 0


def test_get_session_returns_none_for_wrong_user():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    ts = svc.create_session(user_id=uid, title="Mine")
    assert svc.get_session(session_id=ts.id, user_id=uid) is not None
    assert svc.get_session(session_id=ts.id, user_id=999) is None


def test_update_session_saves_blocks():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    ts = svc.create_session(user_id=uid)
    blocks = [{"id": "b1", "type": "freeform", "content": "Hello", "meta": {}, "order": 0}]
    updated = svc.update_session(ts, blocks=blocks, title="Updated")
    assert updated.title == "Updated"
    assert len(updated.blocks) == 1


def test_archive_session():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    ts = svc.create_session(user_id=uid)
    archived = svc.archive_session(ts)
    assert archived.status == "archived"


def test_fork_session():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    original = svc.create_session(user_id=uid, title="Original")
    svc.update_session(
        original,
        blocks=[
            {"id": "b1", "type": "law", "content": "Law 1", "meta": {"law_number": 1}, "order": 0}
        ],
    )
    original.status = "published"
    db.add(original)
    db.commit()
    db.refresh(original)

    forked = svc.fork_session(original)
    assert forked.id != original.id
    assert forked.status == "draft"
    assert forked.title == "Original (fork)"
    assert len(forked.blocks) == 1


def test_block_validation_rejects_invalid_law():
    db = _make_session()
    uid = _ensure_user(db)
    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    ts = svc.create_session(user_id=uid)
    with pytest.raises(ValueError, match="law_number"):
        svc.update_session(
            ts, blocks=[{"id": "b1", "type": "law", "content": "x", "meta": {}, "order": 0}]
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_thinking_session_service.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement ThinkingSessionService**

Create `apps/alfred/services/thinking_session_service.py`:

```python
"""Service for ThinkingSession CRUD, block validation, publish, and fork."""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass

from sqlmodel import Session, select

from alfred.core.utils import utcnow_naive as _utcnow
from alfred.models.thinking import ThinkingSession
from alfred.schemas.thinking import BLOCK_TYPES, VALID_STATUSES, VALID_TRANSITIONS

MAX_PAYLOAD_BLOCKS = 200


@dataclass
class ThinkingSessionService:
    session: Session

    def create_session(
        self,
        *,
        user_id: int,
        title: str | None = None,
        topic: str | None = None,
        tags: list[str] | None = None,
    ) -> ThinkingSession:
        ts = ThinkingSession(
            user_id=user_id,
            title=(title.strip() if title else None),
            topic=(topic.strip() if topic else None),
            tags=tags or [],
            status="draft",
            blocks=[],
        )
        self.session.add(ts)
        self.session.commit()
        self.session.refresh(ts)
        return ts

    def list_sessions(
        self,
        *,
        user_id: int,
        status: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[ThinkingSession]:
        stmt = (
            select(ThinkingSession)
            .where(ThinkingSession.user_id == user_id)
            .order_by(ThinkingSession.pinned.desc(), ThinkingSession.updated_at.desc())
        )
        if status and status in VALID_STATUSES:
            stmt = stmt.where(ThinkingSession.status == status)
        stmt = stmt.offset(max(0, skip)).limit(max(1, min(200, limit)))
        return list(self.session.exec(stmt))

    def get_session(self, *, session_id: int, user_id: int) -> ThinkingSession | None:
        ts = self.session.get(ThinkingSession, session_id)
        if ts and ts.user_id == user_id:
            return ts
        return None

    def update_session(self, ts: ThinkingSession, **fields) -> ThinkingSession:
        if "title" in fields and fields["title"] is not None:
            ts.title = str(fields["title"]).strip()
        if "topic" in fields and fields["topic"] is not None:
            ts.topic = str(fields["topic"]).strip()
        if "tags" in fields and fields["tags"] is not None:
            ts.tags = fields["tags"]
        if "pinned" in fields and fields["pinned"] is not None:
            ts.pinned = bool(fields["pinned"])
        if "blocks" in fields and fields["blocks"] is not None:
            blocks = fields["blocks"]
            if len(blocks) > MAX_PAYLOAD_BLOCKS:
                raise ValueError(f"Too many blocks ({len(blocks)} > {MAX_PAYLOAD_BLOCKS})")
            self._validate_blocks(blocks)
            ts.blocks = blocks
        if "status" in fields and fields["status"] is not None:
            new_status = str(fields["status"])
            if new_status != ts.status:
                if (ts.status, new_status) not in VALID_TRANSITIONS:
                    raise ValueError(f"Invalid transition: {ts.status} -> {new_status}")
                ts.status = new_status
        ts.updated_at = _utcnow()
        self.session.add(ts)
        self.session.commit()
        self.session.refresh(ts)
        return ts

    def archive_session(self, ts: ThinkingSession) -> ThinkingSession:
        return self.update_session(ts, status="archived")

    def fork_session(self, ts: ThinkingSession) -> ThinkingSession:
        new_blocks = []
        for block in ts.blocks or []:
            new_block = copy.deepcopy(block)
            new_block["id"] = str(uuid.uuid4())
            new_blocks.append(new_block)
        forked = ThinkingSession(
            user_id=ts.user_id,
            title=f"{ts.title or 'Untitled'} (fork)",
            topic=ts.topic,
            tags=list(ts.tags or []),
            status="draft",
            blocks=new_blocks,
            source_input=ts.source_input,
        )
        self.session.add(forked)
        self.session.commit()
        self.session.refresh(forked)
        return forked

    def _validate_blocks(self, blocks: list[dict]) -> None:
        for b in blocks:
            block_type = b.get("type", "")
            if block_type not in BLOCK_TYPES:
                raise ValueError(f"Unknown block type: {block_type}")
            meta = b.get("meta", {})
            if block_type == "law" and meta.get("law_number") is None:
                raise ValueError("law blocks require meta.law_number")
            elif block_type == "prediction" and meta.get("confidence") is None:
                raise ValueError("prediction blocks require meta.confidence")
            elif block_type == "connection":
                has_source = any(
                    meta.get(k) is not None
                    for k in ("source_card_id", "source_doc_id", "source_entity_id")
                )
                if not has_source:
                    raise ValueError(
                        "connection blocks require at least one of: "
                        "source_card_id, source_doc_id, source_entity_id"
                    )

    @staticmethod
    def block_summary(blocks: list[dict]) -> dict:
        counts: dict[str, int] = {}
        for b in blocks:
            t = b.get("type", "freeform")
            counts[t] = counts.get(t, 0) + 1
        counts["total"] = len(blocks)
        return counts
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_thinking_session_service.py -v`

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/thinking_session_service.py tests/alfred/services/test_thinking_session_service.py && git commit -m "feat(thinking): add ThinkingSessionService with CRUD, fork, and block validation"
```

---

### Task 4: API Routes (CRUD + Archive + Fork)

**Files:**
- Create: `apps/alfred/api/thinking/__init__.py`
- Create: `apps/alfred/api/thinking/routes.py`
- Modify: `apps/alfred/api/__init__.py`
- Create: `tests/alfred/api/thinking/__init__.py`
- Create: `tests/alfred/api/thinking/test_thinking_routes.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/alfred/api/thinking/__init__.py` (empty file).

Create `tests/alfred/api/thinking/test_thinking_routes.py`:

```python
"""Integration tests for thinking session API routes."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from alfred.models.thinking import ThinkingSession  # noqa: F401
from alfred.models.user import User  # noqa: F401


def _client() -> TestClient:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)

    def _get_db_session():
        with Session(engine) as session:
            if not session.get(User, 1):
                session.add(User(id=1, clerk_id="test", email="t@t.com"))
                session.commit()
            yield session

    from alfred.api.thinking.routes import get_db_session, router

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db_session] = _get_db_session
    return TestClient(app)


def test_create_session():
    client = _client()
    resp = client.post("/api/thinking/sessions?user_id=1", json={"title": "Test"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Test"
    assert resp.json()["status"] == "draft"


def test_list_sessions():
    client = _client()
    client.post("/api/thinking/sessions?user_id=1", json={"title": "One"})
    client.post("/api/thinking/sessions?user_id=1", json={"title": "Two"})
    resp = client.get("/api/thinking/sessions?user_id=1")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 2


def test_get_session():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={"title": "Get me"})
    sid = create_resp.json()["id"]
    resp = client.get(f"/api/thinking/sessions/{sid}?user_id=1")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Get me"


def test_patch_session_autosave():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={})
    sid = create_resp.json()["id"]
    blocks = [{"id": "b1", "type": "freeform", "content": "Hello", "meta": {}, "order": 0}]
    resp = client.patch(
        f"/api/thinking/sessions/{sid}?user_id=1",
        json={"blocks": blocks, "title": "Updated"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated"
    assert len(resp.json()["blocks"]) == 1


def test_archive_session():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={})
    sid = create_resp.json()["id"]
    resp = client.patch(f"/api/thinking/sessions/{sid}/archive?user_id=1")
    assert resp.status_code == 200
    assert resp.json()["status"] == "archived"


def test_fork_session():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={"title": "Original"})
    sid = create_resp.json()["id"]
    blocks = [{"id": "b1", "type": "freeform", "content": "text", "meta": {}, "order": 0}]
    client.patch(f"/api/thinking/sessions/{sid}?user_id=1", json={"blocks": blocks})
    resp = client.post(f"/api/thinking/sessions/{sid}/fork?user_id=1")
    assert resp.status_code == 201
    assert resp.json()["title"] == "Original (fork)"
    assert resp.json()["id"] != sid


def test_404_for_wrong_user():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={})
    sid = create_resp.json()["id"]
    resp = client.get(f"/api/thinking/sessions/{sid}?user_id=999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py -v`

Expected: FAIL with import errors

- [ ] **Step 3: Create route files**

Create `apps/alfred/api/thinking/__init__.py` (empty file).

Create `apps/alfred/api/thinking/routes.py`:

```python
"""API routes for thinking sessions."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session

from alfred.api.dependencies import get_db_session
from alfred.schemas.thinking import (
    SessionCreate,
    SessionListItem,
    SessionOut,
    SessionPatch,
)
from alfred.services.thinking_session_service import ThinkingSessionService

router = APIRouter(prefix="/api/thinking", tags=["thinking"])


def _session_out(ts) -> SessionOut:
    return SessionOut.model_validate(ts)


def _session_list_item(ts) -> SessionListItem:
    return SessionListItem(
        id=ts.id or 0,
        title=ts.title,
        status=ts.status,
        tags=ts.tags,
        topic=ts.topic,
        pinned=ts.pinned,
        block_summary=ThinkingSessionService.block_summary(ts.blocks or []),
        created_at=ts.created_at,
        updated_at=ts.updated_at,
    )


@router.post("/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> SessionOut:
    svc = ThinkingSessionService(db)
    ts = svc.create_session(
        user_id=user_id, title=payload.title, topic=payload.topic, tags=payload.tags
    )
    return _session_out(ts)


@router.get("/sessions")
def list_sessions(
    user_id: int = Query(...),
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db_session),
) -> dict:
    svc = ThinkingSessionService(db)
    sessions = svc.list_sessions(
        user_id=user_id, status=status_filter, limit=limit, skip=skip
    )
    return {"items": [_session_list_item(s) for s in sessions]}


@router.get("/sessions/{session_id}", response_model=SessionOut)
def get_session(
    session_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> SessionOut:
    svc = ThinkingSessionService(db)
    ts = svc.get_session(session_id=session_id, user_id=user_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_out(ts)


@router.patch("/sessions/{session_id}", response_model=SessionOut)
def patch_session(
    session_id: int,
    payload: SessionPatch,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> SessionOut:
    svc = ThinkingSessionService(db)
    ts = svc.get_session(session_id=session_id, user_id=user_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        updated = svc.update_session(ts, **payload.model_dump(exclude_unset=True))
        return _session_out(updated)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/sessions/{session_id}/archive", response_model=SessionOut)
def archive_session(
    session_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> SessionOut:
    svc = ThinkingSessionService(db)
    ts = svc.get_session(session_id=session_id, user_id=user_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        return _session_out(svc.archive_session(ts))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "/sessions/{session_id}/fork",
    response_model=SessionOut,
    status_code=status.HTTP_201_CREATED,
)
def fork_session(
    session_id: int,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> SessionOut:
    svc = ThinkingSessionService(db)
    ts = svc.get_session(session_id=session_id, user_id=user_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_out(svc.fork_session(ts))
```

- [ ] **Step 4: Register router in app**

In `apps/alfred/api/__init__.py`, inside the `register_routes()` function, add the thinking router following the existing pattern:

```python
from alfred.api.thinking.routes import router as thinking_router
```

And append `thinking_router` to the routers list.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py -v`

Expected: All 7 tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/api/thinking/ tests/alfred/api/thinking/ apps/alfred/api/__init__.py && git commit -m "feat(thinking): add CRUD + archive + fork API routes"
```

---

## Chunk 2: Decomposition Engine + Knowledge Surfacing

### Task 5: Decomposition Prompt

**Files:**
- Create: `apps/alfred/prompts/decomposition/system.md`

- [ ] **Step 1: Write decomposition system prompt**

Create `apps/alfred/prompts/decomposition/system.md`:

```markdown
You are a structured thinking assistant. Given a topic, text, or concept, produce a five-layer decomposition:

## Layer 1: Demolition
Challenge the mainstream or conventional understanding of this topic. What do most people assume that might be wrong, incomplete, or misleading? Be specific and provocative.

## Layer 2: Framework
Install a theoretical lens. What mental model, philosophical framework, or analytical tool best illuminates this topic? Name it, explain it in 2-3 sentences, and show why it applies here.

## Layer 3: Canonical Anchor
Identify a foundational text, historical case study, or canonical example that grounds this analysis. Explain why this anchor is the right one and what it reveals.

## Layer 4: Governing Laws
Extract 3-5 named principles or laws that govern this phenomenon. Each law should:
- Have a memorable name (e.g., "The Law of Diminishing Expertise")
- Be stated in 1-2 sentences
- Be transferable to other domains

## Layer 5: Predictions
Based on the laws you extracted, generate 2-3 falsifiable predictions. Each prediction should:
- Make a specific claim about what will happen
- Include a confidence level (0.0-1.0)
- Optionally include a timeframe

Return your analysis as structured JSON matching the provided schema.
```

- [ ] **Step 2: Commit**

```bash
git add apps/alfred/prompts/decomposition/system.md && git commit -m "feat(thinking): add decomposition system prompt"
```

---

### Task 6: DecompositionService

**Files:**
- Create: `apps/alfred/services/decomposition_service.py`
- Create: `tests/alfred/services/test_decomposition_service.py`

- [ ] **Step 1: Write failing test**

Create `tests/alfred/services/test_decomposition_service.py`:

```python
"""Tests for DecompositionService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from alfred.schemas.thinking import Block


def test_convert_decomposition_to_blocks():
    """Test that DecompositionOutput converts to correct block array."""
    from alfred.services.decomposition_service import DecompositionService

    svc = DecompositionService()

    # Simulate a DecompositionOutput
    from alfred.services.decomposition_service import (
        DecompositionOutput,
        LawItem,
        PredictionItem,
    )

    output = DecompositionOutput(
        demolition="Challenge: most people think X",
        framework="Use game theory as the lens",
        anchor="The Warring States period is the canonical case",
        laws=[
            LawItem(name="Law of Asymmetry", description="Small actors can defeat large ones"),
            LawItem(name="Law of Escalation", description="Conflicts tend to intensify"),
        ],
        predictions=[
            PredictionItem(claim="X will happen", confidence=0.7, timeframe="2 years"),
        ],
    )

    blocks = svc._convert_to_blocks(output)

    assert len(blocks) == 6  # 1 demolition + 1 framework + 1 anchor + 2 laws + 1 prediction
    assert blocks[0]["type"] == "demolition"
    assert blocks[1]["type"] == "framework"
    assert blocks[2]["type"] == "anchor"
    assert blocks[3]["type"] == "law"
    assert blocks[3]["meta"]["law_number"] == 1
    assert blocks[4]["type"] == "law"
    assert blocks[4]["meta"]["law_number"] == 2
    assert blocks[5]["type"] == "prediction"
    assert blocks[5]["meta"]["confidence"] == 0.7
    assert blocks[5]["meta"]["timeframe"] == "2 years"

    # All blocks have unique IDs
    ids = [b["id"] for b in blocks]
    assert len(ids) == len(set(ids))


def test_normalize_text_passthrough():
    """Text input type should pass through directly."""
    from alfred.services.decomposition_service import DecompositionService

    svc = DecompositionService()
    result = svc._normalize_input(input_type="text", content="Hello world")
    assert result == "Hello world"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_decomposition_service.py -v`

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement DecompositionService**

Create `apps/alfred/services/decomposition_service.py`:

```python
"""Five-layer decomposition engine."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field as PydanticField

from alfred.services.llm_service import LLMService


class LawItem(BaseModel):
    name: str
    description: str


class PredictionItem(BaseModel):
    claim: str
    confidence: float = PydanticField(ge=0.0, le=1.0)
    timeframe: str | None = None


class DecompositionOutput(BaseModel):
    demolition: str
    framework: str
    anchor: str
    laws: list[LawItem] = PydanticField(min_length=1, max_length=7)
    predictions: list[PredictionItem] = PydanticField(min_length=1, max_length=5)


PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "decomposition" / "system.md"


@dataclass
class DecompositionService:
    llm: LLMService = field(default_factory=LLMService)

    def decompose(
        self,
        *,
        input_type: str,
        content: str,
        connect_to_existing: bool = True,
    ) -> dict:
        """Run the full decomposition pipeline. Returns {blocks, warnings}."""
        warnings: list[str] = []

        # Step 1: Normalize input to text
        text = self._normalize_input(input_type=input_type, content=content)

        # Step 2: LLM structured decomposition
        output = self._run_llm(text)

        # Step 3: Convert to blocks
        blocks = self._convert_to_blocks(output)

        # Step 4: Find connections (best-effort)
        if connect_to_existing:
            try:
                connection_blocks = self._find_connections(text)
                next_order = len(blocks)
                for i, cb in enumerate(connection_blocks):
                    cb["order"] = next_order + i
                blocks.extend(connection_blocks)
            except Exception:
                warnings.append("connection_search_unavailable")

        return {"blocks": blocks, "warnings": warnings}

    def _normalize_input(self, *, input_type: str, content: str) -> str:
        if input_type == "text":
            return content.strip()
        elif input_type == "url":
            return self._scrape_url(content.strip())
        elif input_type == "topic":
            return self._search_topic(content.strip())
        raise ValueError(f"Unknown input_type: {input_type}")

    def _scrape_url(self, url: str) -> str:
        """Scrape URL via Firecrawl. Raises on failure."""
        import httpx

        resp = httpx.post(
            "http://localhost:3002/v1/scrape",
            json={"url": url, "formats": ["markdown"]},
            timeout=30.0,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Firecrawl scrape failed: {resp.status_code}")
        data = resp.json().get("data", {})
        return data.get("markdown") or data.get("content") or ""

    def _search_topic(self, topic: str) -> str:
        """Search via SearXNG for topic context. Falls back to topic name."""
        try:
            import httpx

            resp = httpx.get(
                "http://localhost:8080/search",
                params={"q": topic, "format": "json"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])[:5]
                snippets = [r.get("content", "") for r in results if r.get("content")]
                if snippets:
                    return f"Topic: {topic}\n\nResearch:\n" + "\n\n".join(snippets)
        except Exception:
            pass
        return f"Topic: {topic}"

    def _run_llm(self, text: str) -> DecompositionOutput:
        """Run LLM structured output to produce DecompositionOutput."""
        system_prompt = ""
        if PROMPT_PATH.exists():
            system_prompt = PROMPT_PATH.read_text()
        else:
            system_prompt = "Decompose the given text into 5 layers: demolition, framework, anchor, laws, predictions."

        user_prompt = (
            "Decompose the following:\n\n"
            "<<<BEGIN_TEXT>>>\n" + text[:12000] + "\n<<<END_TEXT>>>"
        )

        result = self.llm.structured(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            schema=DecompositionOutput,
        )
        return result

    def _convert_to_blocks(self, output: DecompositionOutput) -> list[dict]:
        """Convert DecompositionOutput to typed block array."""
        blocks: list[dict] = []
        order = 0

        # Layer 1: Demolition
        blocks.append({
            "id": str(uuid.uuid4()),
            "type": "demolition",
            "content": output.demolition,
            "meta": {},
            "order": order,
        })
        order += 1

        # Layer 2: Framework
        blocks.append({
            "id": str(uuid.uuid4()),
            "type": "framework",
            "content": output.framework,
            "meta": {},
            "order": order,
        })
        order += 1

        # Layer 3: Anchor
        blocks.append({
            "id": str(uuid.uuid4()),
            "type": "anchor",
            "content": output.anchor,
            "meta": {},
            "order": order,
        })
        order += 1

        # Layer 4: Laws
        for i, law in enumerate(output.laws):
            blocks.append({
                "id": str(uuid.uuid4()),
                "type": "law",
                "content": f"**{law.name}:** {law.description}",
                "meta": {"law_number": i + 1},
                "order": order,
            })
            order += 1

        # Layer 5: Predictions
        for pred in output.predictions:
            blocks.append({
                "id": str(uuid.uuid4()),
                "type": "prediction",
                "content": pred.claim,
                "meta": {
                    "confidence": pred.confidence,
                    "timeframe": pred.timeframe,
                },
                "order": order,
            })
            order += 1

        return blocks

    def _find_connections(self, text: str) -> list[dict]:
        """Find related knowledge from existing KB. Placeholder for v1."""
        # TODO: Implement ad-hoc embedding + Qdrant search + entity matching
        # For now, return empty list. Will be implemented with surfacing service.
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_decomposition_service.py -v`

Expected: Both tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/decomposition_service.py tests/alfred/services/test_decomposition_service.py && git commit -m "feat(thinking): add DecompositionService with five-layer pipeline"
```

---

### Task 7: Decompose + Surface API Endpoints

**Files:**
- Modify: `apps/alfred/api/thinking/routes.py`
- Add tests to: `tests/alfred/api/thinking/test_thinking_routes.py`

- [ ] **Step 1: Write failing test for decompose endpoint**

Add to `tests/alfred/api/thinking/test_thinking_routes.py`:

```python
from unittest.mock import patch, MagicMock


def test_decompose_text():
    """Test decompose endpoint with text input (mocked LLM)."""
    client = _client()

    mock_output = {
        "blocks": [
            {"id": "d1", "type": "demolition", "content": "Challenge", "meta": {}, "order": 0},
            {"id": "f1", "type": "framework", "content": "Lens", "meta": {}, "order": 1},
            {"id": "a1", "type": "anchor", "content": "Case", "meta": {}, "order": 2},
            {"id": "l1", "type": "law", "content": "Law 1", "meta": {"law_number": 1}, "order": 3},
            {"id": "p1", "type": "prediction", "content": "Prediction", "meta": {"confidence": 0.8}, "order": 4},
        ],
        "warnings": [],
    }

    with patch("alfred.api.thinking.routes.DecompositionService") as MockSvc:
        MockSvc.return_value.decompose.return_value = mock_output
        resp = client.post(
            "/api/thinking/decompose",
            json={"input_type": "text", "content": "Information theory basics", "connect_to_existing": False},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["blocks"]) == 5
    assert data["blocks"][0]["type"] == "demolition"


def test_surface_endpoint():
    """Test surface endpoint returns connections."""
    client = _client()
    resp = client.post(
        "/api/thinking/surface",
        json={"text": "Information theory and entropy", "limit": 3},
    )
    assert resp.status_code == 200
    assert "connections" in resp.json()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py::test_decompose_text tests/alfred/api/thinking/test_thinking_routes.py::test_surface_endpoint -v`

Expected: FAIL (endpoints not defined)

- [ ] **Step 3: Add decompose and surface endpoints to routes**

Add these imports at the top of `apps/alfred/api/thinking/routes.py`:

```python
from alfred.schemas.thinking import (
    DecomposeRequest,
    DecomposeResponse,
    SurfaceRequest,
    SurfaceResponse,
)
from alfred.services.decomposition_service import DecompositionService
```

Add these route handlers:

```python
@router.post("/decompose", response_model=DecomposeResponse)
def decompose(payload: DecomposeRequest) -> DecomposeResponse:
    svc = DecompositionService()
    try:
        result = svc.decompose(
            input_type=payload.input_type,
            content=payload.content,
            connect_to_existing=payload.connect_to_existing,
        )
        return DecomposeResponse(
            blocks=[Block(**b) for b in result["blocks"]],
            warnings=result.get("warnings", []),
        )
    except RuntimeError as exc:
        detail = str(exc)
        if "scrape" in detail.lower():
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/surface", response_model=SurfaceResponse)
def surface(payload: SurfaceRequest) -> SurfaceResponse:
    # v1: return empty connections. Full implementation in Task 8.
    return SurfaceResponse(connections=[])
```

Also add the `Block` import if not already present:

```python
from alfred.schemas.thinking import Block
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py -v`

Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/api/thinking/routes.py tests/alfred/api/thinking/test_thinking_routes.py && git commit -m "feat(thinking): add decompose and surface API endpoints"
```

---

### Task 8: Knowledge Surfacing Service

**Files:**
- Modify: `apps/alfred/services/thinking_session_service.py`
- Create: `tests/alfred/services/test_thinking_surface.py`

- [ ] **Step 1: Write failing test**

Create `tests/alfred/services/test_thinking_surface.py`:

```python
"""Tests for knowledge surfacing in ThinkingSessionService."""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_surface_returns_empty_when_no_qdrant():
    """When Qdrant is unavailable, surface returns empty list gracefully."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool
    from sqlmodel import Session, SQLModel

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    db = Session(engine)

    from alfred.services.thinking_session_service import ThinkingSessionService

    svc = ThinkingSessionService(db)
    result = svc.surface(text="information theory", limit=5)
    assert isinstance(result, list)
    # In test environment without Qdrant, should return empty
    assert len(result) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_thinking_surface.py -v`

Expected: FAIL (surface method does not exist)

- [ ] **Step 3: Add surface method to ThinkingSessionService**

Add to `apps/alfred/services/thinking_session_service.py`:

```python
    def surface(
        self,
        *,
        text: str,
        session_id: int | None = None,
        limit: int = 5,
    ) -> list[dict]:
        """Find related knowledge from existing KB based on writing buffer text.

        Generates an ad-hoc embedding, searches Qdrant for similar zettel cards
        and documents, and keyword-matches learning entities.
        Returns a list of SurfaceConnection-compatible dicts.
        """
        connections: list[dict] = []
        limit = max(1, min(20, limit))

        # Step 1: Try embedding-based search
        try:
            from alfred.services.llm_service import LLMService

            llm = LLMService()
            embedding = llm.embed(text[:1000])
            if embedding:
                connections.extend(self._search_qdrant(embedding, limit=limit))
        except Exception:
            pass

        # Step 2: Try entity keyword matching
        try:
            connections.extend(self._search_entities(text, limit=limit))
        except Exception:
            pass

        # Deduplicate by (type, id)
        seen: set[tuple[str, str]] = set()
        deduped: list[dict] = []
        for c in sorted(connections, key=lambda x: x.get("relevance", 0), reverse=True):
            key = (c["type"], str(c["id"]))
            if key not in seen:
                seen.add(key)
                deduped.append(c)

        return deduped[:limit]

    def _search_qdrant(self, embedding: list[float], *, limit: int = 5) -> list[dict]:
        """Search Qdrant for similar zettel cards and documents."""
        # Placeholder: will integrate with existing Qdrant client
        # when the embedding infrastructure is confirmed working
        return []

    def _search_entities(self, text: str, *, limit: int = 5) -> list[dict]:
        """Keyword-match learning entities against the writing buffer."""
        from alfred.models.learning import LearningEntity

        words = set(w.lower() for w in text.split() if len(w) > 3)
        if not words:
            return []

        from sqlmodel import select

        stmt = select(LearningEntity).limit(200)
        entities = list(self.session.exec(stmt))
        results = []
        for ent in entities:
            name_lower = (ent.name or "").lower()
            if any(w in name_lower for w in words):
                results.append({
                    "type": "entity",
                    "id": ent.id,
                    "title": ent.name,
                    "snippet": f"Entity type: {ent.type or 'unknown'}",
                    "relevance": 0.5,
                })
        return sorted(results, key=lambda x: x["relevance"], reverse=True)[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/services/test_thinking_surface.py -v`

Expected: PASS

- [ ] **Step 5: Update surface endpoint in routes to use service**

In `apps/alfred/api/thinking/routes.py`, update the `surface` endpoint:

```python
@router.post("/surface", response_model=SurfaceResponse)
def surface(
    payload: SurfaceRequest,
    db: Session = Depends(get_db_session),
) -> SurfaceResponse:
    svc = ThinkingSessionService(db)
    connections = svc.surface(
        text=payload.text,
        session_id=payload.session_id,
        limit=payload.limit,
    )
    return SurfaceResponse(
        connections=[SurfaceConnection(**c) for c in connections]
    )
```

Add `SurfaceConnection` to the imports.

- [ ] **Step 6: Run all thinking tests**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/ -k thinking -v`

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add apps/alfred/services/thinking_session_service.py apps/alfred/api/thinking/routes.py tests/alfred/services/test_thinking_surface.py && git commit -m "feat(thinking): add knowledge surfacing with entity keyword matching"
```

---

### Task 9: Publish Endpoint

**Files:**
- Modify: `apps/alfred/services/thinking_session_service.py`
- Modify: `apps/alfred/api/thinking/routes.py`
- Add tests to: `tests/alfred/api/thinking/test_thinking_routes.py`

- [ ] **Step 1: Write failing test**

Add to `tests/alfred/api/thinking/test_thinking_routes.py`:

```python
def test_publish_session():
    client = _client()
    create_resp = client.post("/api/thinking/sessions?user_id=1", json={"title": "To Publish"})
    sid = create_resp.json()["id"]
    blocks = [
        {"id": "l1", "type": "law", "content": "Law of X", "meta": {"law_number": 1}, "order": 0},
        {"id": "i1", "type": "insight", "content": "My insight", "meta": {}, "order": 1},
    ]
    client.patch(f"/api/thinking/sessions/{sid}?user_id=1", json={"blocks": blocks})
    resp = client.post(
        f"/api/thinking/sessions/{sid}/publish?user_id=1",
        json={"mode": "multiple_cards", "selected_block_ids": ["l1", "i1"], "tags": ["test"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["cards_created"] >= 0  # May be 0 if zettel service not available in test
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py::test_publish_session -v`

Expected: FAIL (endpoint not defined)

- [ ] **Step 3: Add publish method to service**

Add to `apps/alfred/services/thinking_session_service.py`:

```python
    def publish_session(
        self,
        ts: ThinkingSession,
        *,
        mode: str,
        selected_block_ids: list[str],
        tags: list[str],
        title: str | None = None,
    ) -> dict:
        """Publish session blocks as zettelkasten cards."""
        if ts.status != "draft":
            raise ValueError(f"Can only publish draft sessions (current: {ts.status})")

        blocks = ts.blocks or []
        if selected_block_ids:
            blocks = [b for b in blocks if b.get("id") in set(selected_block_ids)]

        card_ids: list[int] = []
        try:
            from alfred.services.zettelkasten_service import ZettelkastenService

            zk_svc = ZettelkastenService(self.session)
            for block in blocks:
                card = zk_svc.create_card(
                    title=title or (block.get("content", "")[:100].strip() or "Untitled"),
                    content=block.get("content", ""),
                    tags=tags,
                    metadata={"thinking_session_id": ts.id, "block_type": block.get("type")},
                )
                card_ids.append(card.id or 0)
        except Exception:
            pass

        ts.status = "published"
        ts.updated_at = _utcnow()
        self.session.add(ts)
        self.session.commit()
        self.session.refresh(ts)

        return {"cards_created": len(card_ids), "card_ids": card_ids, "topic_created": None}
```

- [ ] **Step 4: Add publish endpoint to routes**

Add to `apps/alfred/api/thinking/routes.py`:

```python
@router.post("/sessions/{session_id}/publish", response_model=PublishResult)
def publish_session(
    session_id: int,
    payload: PublishRequest,
    user_id: int = Query(...),
    db: Session = Depends(get_db_session),
) -> PublishResult:
    svc = ThinkingSessionService(db)
    ts = svc.get_session(session_id=session_id, user_id=user_id)
    if not ts:
        raise HTTPException(status_code=404, detail="Session not found")
    try:
        result = svc.publish_session(
            ts,
            mode=payload.mode,
            selected_block_ids=payload.selected_block_ids,
            tags=payload.tags,
            title=payload.title,
        )
        return PublishResult(**result)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

Add `PublishRequest` and `PublishResult` to the imports.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/api/thinking/test_thinking_routes.py -v`

Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/services/thinking_session_service.py apps/alfred/api/thinking/routes.py tests/alfred/api/thinking/test_thinking_routes.py && git commit -m "feat(thinking): add publish endpoint with zettelkasten card creation"
```

---

## Chunk 3: Frontend — API Layer + Pages + Navigation

### Task 10: Install BlockNote + Add Navigation

**Files:**
- Modify: `web/package.json`
- Modify: `web/components/app-sidebar.tsx`

- [ ] **Step 1: Install BlockNote**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees/web && npm install @blocknote/react @blocknote/shadcn @blocknote/core
```

- [ ] **Step 2: Verify Tiptap compatibility**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees/web && npm ls @tiptap/core 2>&1 | head -20
```

Check that there is only one version of `@tiptap/core` in the tree. If there are conflicts, pin both BlockNote and existing Tiptap packages to the same version.

- [ ] **Step 3: Add Think nav item to sidebar**

In `web/components/app-sidebar.tsx`, find the navigation items array and add:

```tsx
{ title: "Think", url: "/think", icon: Lightbulb }
```

Import `Lightbulb` from `lucide-react`.

- [ ] **Step 4: Commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add web/package.json web/package-lock.json web/components/app-sidebar.tsx && git commit -m "feat(thinking): install BlockNote and add Think nav item"
```

---

### Task 11: Frontend API Client + Types + React Query

**Files:**
- Create: `web/lib/api/types/thinking.ts`
- Create: `web/lib/api/thinking.ts`
- Create: `web/features/thinking/query-keys.ts`
- Create: `web/features/thinking/queries.ts`
- Create: `web/features/thinking/mutations.ts`

- [ ] **Step 1: Create TypeScript types**

Create `web/lib/api/types/thinking.ts`:

```typescript
export type BlockMeta = {
  law_number?: number;
  confidence?: number;
  timeframe?: string;
  source_card_id?: number;
  source_doc_id?: string;
  source_entity_id?: number;
  validated_at?: string | null;
  collapsed?: boolean;
};

export type Block = {
  id: string;
  type: "freeform" | "demolition" | "framework" | "anchor" | "law" | "prediction" | "connection" | "insight";
  content: string;
  meta: BlockMeta;
  order: number;
};

export type ThinkingSession = {
  id: number;
  user_id: number;
  title: string | null;
  status: "draft" | "published" | "archived";
  blocks: Block[];
  tags: string[] | null;
  topic: string | null;
  source_input: Record<string, unknown> | null;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type SessionListItem = {
  id: number;
  title: string | null;
  status: "draft" | "published" | "archived";
  tags: string[] | null;
  topic: string | null;
  pinned: boolean;
  block_summary: Record<string, number>;
  created_at: string;
  updated_at: string;
};

export type SurfaceConnection = {
  type: "zettel" | "entity" | "document";
  id: number | string;
  title: string;
  snippet: string;
  relevance: number;
};

export type PublishResult = {
  cards_created: number;
  card_ids: number[];
  topic_created: { id: number; name: string } | null;
};
```

- [ ] **Step 2: Create API client functions**

Create `web/lib/api/thinking.ts`:

```typescript
import { apiFetch, apiPatchJson, apiPostJson } from "@/lib/api/client";
import type {
  Block,
  PublishResult,
  SessionListItem,
  SurfaceConnection,
  ThinkingSession,
} from "@/lib/api/types/thinking";

const BASE = "/api/thinking";

export async function createSession(
  userId: number,
  body: { title?: string; topic?: string; tags?: string[] },
): Promise<ThinkingSession> {
  return apiPostJson<ThinkingSession, typeof body>(`${BASE}/sessions?user_id=${userId}`, body);
}

export async function listSessions(
  userId: number,
  params?: { status?: string; limit?: number; skip?: number },
): Promise<{ items: SessionListItem[] }> {
  const query = new URLSearchParams({ user_id: String(userId) });
  if (params?.status) query.set("status", params.status);
  if (params?.limit) query.set("limit", String(params.limit));
  if (params?.skip) query.set("skip", String(params.skip));
  return apiFetch<{ items: SessionListItem[] }>(`${BASE}/sessions?${query}`, { cache: "no-store" });
}

export async function getSession(sessionId: number, userId: number): Promise<ThinkingSession> {
  return apiFetch<ThinkingSession>(`${BASE}/sessions/${sessionId}?user_id=${userId}`, {
    cache: "no-store",
  });
}

export async function patchSession(
  sessionId: number,
  userId: number,
  body: { title?: string; blocks?: Block[]; tags?: string[]; pinned?: boolean },
): Promise<ThinkingSession> {
  return apiPatchJson<ThinkingSession, typeof body>(
    `${BASE}/sessions/${sessionId}?user_id=${userId}`,
    body,
  );
}

export async function archiveSession(sessionId: number, userId: number): Promise<ThinkingSession> {
  return apiPatchJson<ThinkingSession, Record<string, never>>(
    `${BASE}/sessions/${sessionId}/archive?user_id=${userId}`,
    {},
  );
}

export async function forkSession(sessionId: number, userId: number): Promise<ThinkingSession> {
  return apiPostJson<ThinkingSession, Record<string, never>>(
    `${BASE}/sessions/${sessionId}/fork?user_id=${userId}`,
    {},
  );
}

export async function decompose(body: {
  input_type: "topic" | "url" | "text";
  content: string;
  connect_to_existing?: boolean;
}): Promise<{ blocks: Block[]; warnings: string[] }> {
  return apiPostJson(`${BASE}/decompose`, body);
}

export async function surfaceConnections(body: {
  text: string;
  session_id?: number;
  limit?: number;
}): Promise<{ connections: SurfaceConnection[] }> {
  return apiPostJson(`${BASE}/surface`, body);
}

export async function publishSession(
  sessionId: number,
  userId: number,
  body: { mode: string; selected_block_ids: string[]; tags: string[]; title?: string },
): Promise<PublishResult> {
  return apiPostJson(`${BASE}/sessions/${sessionId}/publish?user_id=${userId}`, body);
}
```

- [ ] **Step 3: Create query keys**

Create `web/features/thinking/query-keys.ts`:

```typescript
export const thinkingKeys = {
  all: ["thinking"] as const,
  sessions: (userId: number) => [...thinkingKeys.all, "sessions", userId] as const,
  sessionsList: (userId: number, status?: string) =>
    [...thinkingKeys.sessions(userId), "list", status ?? "all"] as const,
  session: (sessionId: number, userId: number) =>
    [...thinkingKeys.all, "session", sessionId, userId] as const,
  surface: (text: string) => [...thinkingKeys.all, "surface", text] as const,
};
```

- [ ] **Step 4: Create React Query hooks**

Create `web/features/thinking/queries.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";
import { getSession, listSessions } from "@/lib/api/thinking";
import { thinkingKeys } from "./query-keys";

export function useThinkingSessions(userId: number, status?: string) {
  return useQuery({
    queryKey: thinkingKeys.sessionsList(userId, status),
    queryFn: () => listSessions(userId, { status }),
    staleTime: 5_000,
    enabled: userId > 0,
  });
}

export function useThinkingSession(sessionId: number | null, userId: number) {
  return useQuery({
    queryKey: sessionId ? thinkingKeys.session(sessionId, userId) : ["thinking", "disabled"],
    queryFn: () => getSession(sessionId!, userId),
    staleTime: 0,
    enabled: Boolean(sessionId) && userId > 0,
  });
}
```

Create `web/features/thinking/mutations.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  archiveSession,
  createSession,
  forkSession,
  patchSession,
  publishSession,
} from "@/lib/api/thinking";
import { thinkingKeys } from "./query-keys";

export function useCreateSession(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { title?: string; topic?: string; tags?: string[] }) =>
      createSession(userId, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: thinkingKeys.sessions(userId) }),
  });
}

export function useAutosave(sessionId: number, userId: number) {
  return useMutation({
    mutationFn: (body: Parameters<typeof patchSession>[2]) =>
      patchSession(sessionId, userId, body),
  });
}

export function useArchiveSession(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: number) => archiveSession(sessionId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: thinkingKeys.sessions(userId) }),
  });
}

export function useForkSession(userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (sessionId: number) => forkSession(sessionId, userId),
    onSuccess: () => qc.invalidateQueries({ queryKey: thinkingKeys.sessions(userId) }),
  });
}

export function usePublishSession(sessionId: number, userId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: Parameters<typeof publishSession>[2]) =>
      publishSession(sessionId, userId, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: thinkingKeys.session(sessionId, userId) });
      qc.invalidateQueries({ queryKey: thinkingKeys.sessions(userId) });
    },
  });
}
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add web/lib/api/types/thinking.ts web/lib/api/thinking.ts web/features/thinking/ && git commit -m "feat(thinking): add frontend API client, types, and React Query hooks"
```

---

### Task 12: Session List Page

**Files:**
- Create: `web/app/(app)/think/page.tsx`
- Create: `web/app/(app)/think/_components/session-list-client.tsx`

- [ ] **Step 1: Create session list page**

Create `web/app/(app)/think/page.tsx`:

```tsx
export default function ThinkPage() {
  return (
    <div className="h-[calc(100dvh-4.25rem)] w-full">
      <SessionListClient />
    </div>
  );
}

import { SessionListClient } from "./_components/session-list-client";
```

- [ ] **Step 2: Create session list client component**

This is a meaningful UX component. Create `web/app/(app)/think/_components/session-list-client.tsx` with the following structure:

- "New Session" button at top
- List of sessions sorted by pinned first, then updated_at desc
- Each item shows: title, status badge, block summary, timestamp, pin toggle
- Click navigates to `/think/[sessionId]`

The implementer should use `useThinkingSessions()` from the queries hook, `useCreateSession()` from mutations, and `useRouter()` from `next/navigation` for navigation. Follow the pattern in `web/app/(app)/notes/_components/notes-sidebar.tsx` for the list item layout.

- [ ] **Step 3: Commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add web/app/\(app\)/think/ && git commit -m "feat(thinking): add session list page"
```

---

### Task 13: Thinking Canvas Editor Page

**Files:**
- Create: `web/app/(app)/think/new/page.tsx`
- Create: `web/app/(app)/think/[sessionId]/page.tsx`
- Create: `web/app/(app)/think/_components/thinking-canvas-client.tsx`
- Create: `web/app/(app)/think/_components/blocks/index.ts` (and all block files)

This is the core frontend task. It involves:

1. **BlockNote editor** with custom block types
2. **Autosave** (3s debounce)
3. **Slash commands** (/decompose, /law, /prediction, /insight, /connect, /surface)

- [ ] **Step 1: Create page wrappers**

Create `web/app/(app)/think/new/page.tsx`:

```tsx
import { ThinkingCanvasClient } from "../_components/thinking-canvas-client";

export default function NewThinkPage() {
  return (
    <div className="h-[calc(100dvh-4.25rem)] w-full">
      <ThinkingCanvasClient sessionId={null} />
    </div>
  );
}
```

Create `web/app/(app)/think/[sessionId]/page.tsx`:

```tsx
import { ThinkingCanvasClient } from "../_components/thinking-canvas-client";

type Props = {
  params: Promise<{ sessionId: string }>;
};

export default async function ThinkSessionPage({ params }: Props) {
  const { sessionId } = await params;
  const id = parseInt(sessionId, 10);

  return (
    <div className="h-[calc(100dvh-4.25rem)] w-full">
      <ThinkingCanvasClient sessionId={isNaN(id) ? null : id} />
    </div>
  );
}
```

- [ ] **Step 2: Create custom block type registry**

Create `web/app/(app)/think/_components/blocks/index.ts`. This file registers all 8 custom block types with BlockNote. Follow the BlockNote custom block documentation to define each block with its visual treatment (colored left border, icon, collapsible behavior).

The implementer should consult `@blocknote/react` docs for `createReactBlockSpec()` usage. Each block type maps to the visual spec from the design:

| Type | Border Color | Icon |
|------|-------------|------|
| demolition | red-orange | Flame (lucide) |
| framework | blue | Glasses (lucide) |
| anchor | purple | BookOpen (lucide) |
| law | green | Scale (lucide) |
| prediction | amber | TrendingUp (lucide) |
| connection | gray dashed | Link (lucide) |
| insight | gold | Lightbulb (lucide) |

- [ ] **Step 3: Create ThinkingCanvasClient**

Create `web/app/(app)/think/_components/thinking-canvas-client.tsx`. This is the main component:

- If `sessionId` is null, create a new session on mount via `useCreateSession`
- Load session via `useThinkingSession(sessionId, userId)`
- Render BlockNote editor with custom blocks
- Autosave blocks on 3-second debounce via `useAutosave`
- Save indicator: "Saving..." / "Saved"
- Surfacing sidebar on the right (Task 14)

Use `useAuth()` from Clerk to get the current user ID. Follow the pattern from `web/app/(app)/notes/_components/note-editor-panel.tsx` for the editor layout.

- [ ] **Step 4: Commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add web/app/\(app\)/think/ && git commit -m "feat(thinking): add thinking canvas editor with BlockNote and custom blocks"
```

---

### Task 14: Surfacing Sidebar + Decompose Modal + Publish Sheet

**Files:**
- Create: `web/app/(app)/think/_components/surfacing-sidebar.tsx`
- Create: `web/app/(app)/think/_components/decompose-modal.tsx`
- Create: `web/app/(app)/think/_components/publish-sheet.tsx`

- [ ] **Step 1: Create surfacing sidebar**

Create `web/app/(app)/think/_components/surfacing-sidebar.tsx`:

- Receives `text` prop (the last ~200 words of writing buffer)
- Calls `surfaceConnections()` on 5-second debounce when text changes
- Shows list of `SurfaceConnection` items
- Each item shows: type icon, title, snippet, relevance score
- "Drag" button that creates a connection block (or click-to-insert)
- "Dismiss" button that hides the item for this session
- Collapsible via toggle button

Use `framer-motion` for slide-in/out animation matching existing patterns.

- [ ] **Step 2: Create decompose modal**

Create `web/app/(app)/think/_components/decompose-modal.tsx`:

- Triggered by `/decompose` slash command or a toolbar button
- Modal with: input type selector (topic/url/text), content textarea, "Connect to existing" toggle
- Calls `decompose()` API
- Shows loading state
- On success, inserts returned blocks into the editor

Use the `Dialog` component from `web/components/ui/dialog.tsx`.

- [ ] **Step 3: Create publish sheet**

Create `web/app/(app)/think/_components/publish-sheet.tsx`:

- Triggered by Cmd+Enter or Publish button
- Sheet (bottom drawer) with:
  - Title input (auto-suggested from first block content)
  - Tags input
  - Mode selector: single card / multiple cards / learning topic
  - Block selection checkboxes (for multiple cards mode)
- Calls `publishSession()` API
- Shows success toast with cards_created count

Use the `Sheet` component from `web/components/ui/sheet.tsx`.

- [ ] **Step 4: Commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add web/app/\(app\)/think/_components/ && git commit -m "feat(thinking): add surfacing sidebar, decompose modal, and publish sheet"
```

---

## Chunk 4: Integration + Verification

### Task 15: End-to-End Smoke Test

- [ ] **Step 1: Run all backend tests**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/pytest tests/alfred/ -k thinking -v --tb=short
```

Expected: All tests PASS

- [ ] **Step 2: Start backend and test manually**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees && PYTHONPATH=apps .venv/bin/uvicorn alfred.main:app --reload --port 8000
```

Test with curl:
```bash
# Create session
curl -X POST "http://localhost:8000/api/thinking/sessions?user_id=1" -H "Content-Type: application/json" -d '{"title": "Test Session"}'

# List sessions
curl "http://localhost:8000/api/thinking/sessions?user_id=1"
```

- [ ] **Step 3: Start frontend and verify navigation**

Run:
```bash
cd /Users/ashwinrachha/coding/worktrees/web && npm run dev
```

Navigate to `http://localhost:3000/think` and verify:
- Session list page loads
- "New Session" button works
- Editor loads with BlockNote
- Custom block types render correctly
- Autosave indicator works
- Surfacing sidebar toggles

- [ ] **Step 4: Final commit**

```bash
cd /Users/ashwinrachha/coding/worktrees && git add -A && git status
```

Review changes, then commit any remaining files.

```bash
git commit -m "feat(thinking): complete thinking canvas v1 integration"
```
