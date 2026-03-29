"""Service layer for thinking canvas sessions.

Handles CRUD, archival, and forking of thinking sessions so API handlers
stay thin.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session, select

from alfred.core.utils import utcnow_naive
from alfred.models.thinking import ThinkingSessionRow
from alfred.schemas.thinking import (
    ThinkingBlock,
    ThinkingSessionCreate,
    ThinkingSessionResponse,
    ThinkingSessionSummary,
    ThinkingSessionUpdate,
)


def _row_to_response(row: ThinkingSessionRow) -> ThinkingSessionResponse:
    """Convert a DB row to a response schema."""
    blocks = [ThinkingBlock(**b) for b in (row.blocks or [])]
    return ThinkingSessionResponse(
        id=row.id or 0,
        title=row.title,
        status=row.status,
        blocks=blocks,
        tags=list(row.tags or []),
        topic=row.topic,
        source_input=row.source_input,
        pinned=row.pinned,
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _row_to_summary(row: ThinkingSessionRow) -> ThinkingSessionSummary:
    """Convert a DB row to a summary schema."""
    return ThinkingSessionSummary(
        id=row.id or 0,
        title=row.title,
        status=row.status,
        topic=row.topic,
        pinned=row.pinned,
        tags=list(row.tags or []),
        block_count=len(row.blocks or []),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


@dataclass
class ThinkingSessionService:
    """Encapsulates thinking session CRUD, archival, and forking."""

    session: Session

    def create_session(self, payload: ThinkingSessionCreate) -> ThinkingSessionResponse:
        """Create a new thinking session."""
        row = ThinkingSessionRow(
            title=payload.title.strip() if payload.title else None,
            topic=payload.topic.strip() if payload.topic else None,
            source_input=payload.source_input,
            blocks=[b.model_dump() for b in payload.blocks],
            tags=list(payload.tags),
        )
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_response(row)

    def get_session(self, session_id: int) -> ThinkingSessionResponse | None:
        """Fetch a single thinking session by id."""
        row = self.session.get(ThinkingSessionRow, session_id)
        if not row:
            return None
        return _row_to_response(row)

    def list_sessions(
        self,
        status: str | None = None,
        limit: int = 50,
        skip: int = 0,
    ) -> list[ThinkingSessionSummary]:
        """List sessions ordered by recency."""
        stmt = (
            select(ThinkingSessionRow)
            .order_by(ThinkingSessionRow.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        if status:
            stmt = stmt.where(ThinkingSessionRow.status == status)
        rows = list(self.session.exec(stmt))
        return [_row_to_summary(r) for r in rows]

    def update_session(
        self, session_id: int, payload: ThinkingSessionUpdate
    ) -> ThinkingSessionResponse | None:
        """Apply partial updates to a thinking session."""
        row = self.session.get(ThinkingSessionRow, session_id)
        if not row:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "title" in data and data["title"] is not None:
            row.title = str(data["title"]).strip()
        if "topic" in data and data["topic"] is not None:
            row.topic = str(data["topic"]).strip()
        if "blocks" in data and data["blocks"] is not None:
            row.blocks = [b.model_dump() for b in payload.blocks]  # type: ignore[union-attr]
        if "tags" in data and data["tags"] is not None:
            row.tags = list(data["tags"])
        if "pinned" in data and data["pinned"] is not None:
            row.pinned = bool(data["pinned"])
        if "status" in data and data["status"] is not None:
            row.status = str(data["status"])

        row.updated_at = utcnow_naive()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_response(row)

    def archive_session(self, session_id: int) -> ThinkingSessionResponse | None:
        """Archive a thinking session."""
        row = self.session.get(ThinkingSessionRow, session_id)
        if not row:
            return None
        row.status = "archived"
        row.updated_at = utcnow_naive()
        self.session.add(row)
        self.session.commit()
        self.session.refresh(row)
        return _row_to_response(row)

    def fork_session(self, session_id: int) -> ThinkingSessionResponse:
        """Create a copy of an existing session."""
        original = self.session.get(ThinkingSessionRow, session_id)
        if not original:
            raise ValueError("Thinking session not found")

        forked = ThinkingSessionRow(
            title=f"{original.title or 'Untitled'} (fork)",
            topic=original.topic,
            source_input=original.source_input,
            blocks=list(original.blocks or []),
            tags=list(original.tags or []),
            status="draft",
        )
        self.session.add(forked)
        self.session.commit()
        self.session.refresh(forked)
        return _row_to_response(forked)
