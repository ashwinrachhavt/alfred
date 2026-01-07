"""Thread/message persistence service (Postgres).

Threads are a simple, frontend-friendly abstraction for storing feature outputs
as an ordered sequence of messages. Each message stores both a displayable
`content` string and a structured JSON `data` payload.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlmodel import Session, select

from alfred.core.database import SessionLocal
from alfred.core.exceptions import NotFoundError
from alfred.core.utils import utcnow
from alfred.models.threads import ThreadMessageRow, ThreadRow


class ThreadNotFoundError(NotFoundError):
    default_code = "thread_not_found"


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _merge_dicts(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    if not patch:
        return dict(base)
    merged = dict(base)
    merged.update(patch)
    return merged


@dataclass(slots=True)
class ThreadService:
    """CRUD for threads and their messages."""

    def _session(self) -> Session:
        return SessionLocal()

    def get_thread(self, thread_id: str | uuid.UUID) -> ThreadRow:
        tid = _as_uuid(thread_id)
        with self._session() as s:
            row = s.exec(select(ThreadRow).where(ThreadRow.id == tid)).first()
            if row is None:
                raise ThreadNotFoundError(f"Thread not found: {tid}")
            return row

    def upsert_thread(
        self,
        *,
        thread_id: str | uuid.UUID | None = None,
        kind: str,
        title: str | None = None,
        user_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ThreadRow:
        if not (kind or "").strip():
            raise ValueError("kind is required")

        tid = _as_uuid(thread_id) if thread_id is not None else uuid.uuid4()
        now = utcnow()
        meta = metadata or {}

        with self._session() as s:
            existing = s.exec(select(ThreadRow).where(ThreadRow.id == tid)).first()
            if existing is None:
                created = ThreadRow(
                    id=tid,
                    kind=kind.strip(),
                    title=(title or "").strip() or None,
                    user_id=user_id,
                    meta=dict(meta),
                    created_at=now,
                    updated_at=now,
                )
                s.add(created)
                s.commit()
                s.refresh(created)
                return created

            existing.kind = kind.strip()
            if title is not None:
                existing.title = (title or "").strip() or None
            if user_id is not None:
                existing.user_id = user_id
            if metadata is not None:
                existing.meta = _merge_dicts(existing.meta or {}, meta)
            existing.updated_at = now
            s.add(existing)
            s.commit()
            s.refresh(existing)
            return existing

    def append_message(
        self,
        *,
        thread_id: str | uuid.UUID,
        role: str,
        content: str | None = None,
        data: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> ThreadMessageRow:
        tid = _as_uuid(thread_id)
        if not (role or "").strip():
            raise ValueError("role is required")

        now = created_at or utcnow()
        payload = data or {}
        with self._session() as s:
            thread = s.exec(select(ThreadRow).where(ThreadRow.id == tid)).first()
            if thread is None:
                raise ThreadNotFoundError(f"Thread not found: {tid}")

            msg = ThreadMessageRow(
                thread_id=tid,
                role=role.strip(),
                content=(content or "").strip() or None,
                data=dict(payload),
                created_at=now,
                updated_at=now,
            )
            s.add(msg)
            thread.updated_at = now
            s.add(thread)
            s.commit()
            s.refresh(msg)
            return msg

    def list_threads(
        self,
        *,
        kind: str | None = None,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ThreadRow]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        stmt = select(ThreadRow)
        if kind:
            stmt = stmt.where(ThreadRow.kind == kind)
        if user_id is not None:
            stmt = stmt.where(ThreadRow.user_id == user_id)
        stmt = stmt.order_by(sa.desc(ThreadRow.updated_at)).offset(offset).limit(limit)

        with self._session() as s:
            return list(s.exec(stmt).all())

    def list_messages(
        self,
        *,
        thread_id: str | uuid.UUID,
        limit: int = 200,
        offset: int = 0,
    ) -> list[ThreadMessageRow]:
        tid = _as_uuid(thread_id)
        limit = max(1, min(int(limit), 1000))
        offset = max(0, int(offset))

        stmt = (
            select(ThreadMessageRow)
            .where(ThreadMessageRow.thread_id == tid)
            .order_by(ThreadMessageRow.created_at.asc(), ThreadMessageRow.id.asc())
            .offset(offset)
            .limit(limit)
        )
        with self._session() as s:
            return list(s.exec(stmt).all())


__all__ = ["ThreadNotFoundError", "ThreadService"]
