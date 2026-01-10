from __future__ import annotations

import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterable

from pydantic import BaseModel, Field
from sqlmodel import Session, select

from alfred.core.database import SessionLocal
from alfred.core.settings import LLMProvider, settings
from alfred.core.utils import clamp_int
from alfred.models.doc_storage import QuickNoteRow
from alfred.schemas.documents import NoteCreate
from alfred.schemas.intelligence import MemoryCreateRequest, MemoryItem, MemoryListResponse
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.llm_service import LLMService
from alfred.services.thread_service import ThreadService

logger = logging.getLogger(__name__)

MEMORY_NOTE_KIND = "memory"
_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class _MemoryDraft(BaseModel):
    text: str = Field(..., min_length=1)
    tags: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class _ThreadMemoryDraft(BaseModel):
    memories: list[_MemoryDraft] = Field(default_factory=list)


def _first_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(str(value))
    except Exception:
        return None


def _normalize_tags(tags: Iterable[str] | None, *, max_tags: int = 12) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in tags or []:
        tag = " ".join((raw or "").strip().split())
        if not tag:
            continue
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(tag)
        if len(cleaned) >= max_tags:
            break
    return cleaned


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


@contextmanager
def _session_scope(session: Session | None):
    if session is not None:
        yield session
    else:
        with SessionLocal() as s:
            yield s


@dataclass(slots=True)
class MemoryService:
    """Context-aware personal memory stored as notes with structured metadata."""

    doc_storage: DocStorageService
    thread_service: ThreadService
    llm_service: LLMService | None = None

    def _llm(self) -> LLMService:
        return self.llm_service or LLMService()

    def create_memory(self, payload: MemoryCreateRequest) -> MemoryItem:
        meta: dict[str, Any] = dict(payload.metadata or {})
        meta.setdefault("kind", MEMORY_NOTE_KIND)
        if payload.user_id is not None:
            meta["user_id"] = int(payload.user_id)
        if payload.source:
            meta["source"] = payload.source
        if payload.thread_id:
            meta["thread_id"] = str(payload.thread_id)
        if payload.task_id:
            meta["task_id"] = str(payload.task_id)
        tags = _normalize_tags(payload.tags)
        if tags:
            meta["tags"] = tags
        if payload.links:
            meta["links"] = list(payload.links)

        note_id = self.doc_storage.create_note(
            NoteCreate(text=payload.text, source_url=None, metadata=meta)
        )
        note = self.doc_storage.get_note(note_id)
        if not note:
            raise RuntimeError("Memory not found after creation")
        return MemoryItem(
            id=note["id"],
            text=note["text"],
            source_url=note.get("source_url"),
            metadata=note.get("metadata") or {},
            created_at=note.get("created_at"),
        )

    def list_memories(
        self,
        *,
        q: str | None = None,
        user_id: int | None = None,
        source: str | None = None,
        thread_id: str | None = None,
        task_id: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> MemoryListResponse:
        skip = clamp_int(int(skip), lo=0, hi=50_000)
        limit = clamp_int(int(limit), lo=1, hi=200)

        q_norm = (q or "").strip() or None
        source_norm = (source or "").strip() or None
        thread_norm = (thread_id or "").strip() or None
        task_norm = (task_id or "").strip() or None

        stmt = select(QuickNoteRow).order_by(QuickNoteRow.created_at.desc())
        if q_norm:
            stmt = stmt.where(QuickNoteRow.text.ilike(f"%{q_norm}%"))

        with _session_scope(self.doc_storage.session) as s:
            rows = list(s.exec(stmt).all())

        filtered: list[QuickNoteRow] = []
        for row in rows:
            meta = row.meta or {}
            if meta.get("kind") != MEMORY_NOTE_KIND:
                continue
            if user_id is not None and _first_int(meta.get("user_id")) != int(user_id):
                continue
            if source_norm and (meta.get("source") != source_norm):
                continue
            if thread_norm and (str(meta.get("thread_id") or "") != thread_norm):
                continue
            if task_norm and (str(meta.get("task_id") or "") != task_norm):
                continue
            filtered.append(row)

        total = len(filtered)
        page = filtered[skip : skip + limit]

        items = [
            MemoryItem(
                id=str(row.id),
                text=row.text,
                source_url=row.source_url,
                metadata=row.meta or {},
                created_at=row.created_at,
            )
            for row in page
        ]
        return MemoryListResponse(items=items, total=total, skip=skip, limit=limit)

    def get_context_memories(
        self,
        *,
        query: str,
        user_id: int | None = None,
        limit: int = 6,
        max_scan: int = 500,
    ) -> list[MemoryItem]:
        """Return the most relevant memories for a query (simple lexical scoring)."""

        q = (query or "").strip()
        if not q:
            return []

        limit = clamp_int(int(limit), lo=1, hi=25)
        max_scan = clamp_int(int(max_scan), lo=25, hi=2000)

        q_tokens = _tokenize(q)
        if not q_tokens:
            return []

        stmt = select(QuickNoteRow).order_by(QuickNoteRow.created_at.desc()).limit(max_scan)
        with _session_scope(self.doc_storage.session) as s:
            rows = list(s.exec(stmt).all())

        scored: list[tuple[float, QuickNoteRow]] = []
        for row in rows:
            meta = row.meta or {}
            if meta.get("kind") != MEMORY_NOTE_KIND:
                continue
            if user_id is not None and _first_int(meta.get("user_id")) != int(user_id):
                continue
            overlap = len(q_tokens.intersection(_tokenize(row.text)))
            if overlap <= 0:
                continue
            score = overlap / max(1, len(q_tokens))
            scored.append((score, row))

        scored.sort(
            key=lambda pair: (
                pair[0],
                pair[1].created_at.timestamp() if pair[1].created_at else 0.0,
            ),
            reverse=True,
        )

        out: list[MemoryItem] = []
        for score, row in scored[:limit]:
            meta = dict(row.meta or {})
            meta.setdefault("score", round(float(score), 4))
            out.append(
                MemoryItem(
                    id=str(row.id),
                    text=row.text,
                    source_url=row.source_url,
                    metadata=meta,
                    created_at=row.created_at,
                )
            )
        return out

    def extract_memories_from_thread(
        self,
        *,
        thread_id: str,
        user_id: int | None = None,
        max_memories: int = 6,
        max_messages: int = 40,
    ) -> list[MemoryItem]:
        tid = (thread_id or "").strip()
        if not tid:
            raise ValueError("thread_id is required")

        max_memories = clamp_int(int(max_memories), lo=1, hi=12)
        max_messages = clamp_int(int(max_messages), lo=1, hi=200)

        messages = self.thread_service.list_messages(thread_id=tid, limit=max_messages, offset=0)
        if not messages:
            return []

        transcript_lines: list[str] = []
        for m in messages:
            role = (m.role or "").strip().lower() or "user"
            content = (m.content or "").strip()
            if not content:
                continue
            transcript_lines.append(f"{role}: {content}")

        transcript = "\n".join(transcript_lines).strip()
        if not transcript:
            return []

        drafts = self._try_llm_extract(transcript=transcript, max_memories=max_memories) or []
        if not drafts:
            return []

        created: list[MemoryItem] = []
        for d in drafts[:max_memories]:
            text = " ".join((d.text or "").strip().split())
            if not text:
                continue
            payload = MemoryCreateRequest(
                text=text,
                user_id=user_id,
                source="thread",
                thread_id=tid,
                tags=_normalize_tags(d.tags),
                metadata={"confidence": d.confidence} if d.confidence is not None else {},
            )
            created.append(self.create_memory(payload))
        return created

    def _try_llm_extract(self, *, transcript: str, max_memories: int) -> list[_MemoryDraft] | None:
        if settings.llm_provider != LLMProvider.openai:
            return None
        api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
        if not api_key and not settings.openai_base_url:
            return None

        sys = (
            "Extract durable personal work memories from a conversation transcript.\n"
            "Return JSON only.\n"
            "Only include memories that are likely to matter later (preferences, decisions, goals, constraints).\n"
            f"Return at most {max_memories} items.\n"
            "Each memory must be a single sentence.\n"
            "Do not include private secrets or credentials.\n"
        )
        try:
            out = self._llm().structured(
                [
                    {"role": "system", "content": sys},
                    {"role": "user", "content": transcript[:8000]},
                ],
                schema=_ThreadMemoryDraft,
                model=settings.llm_model,
            )
            items: list[_MemoryDraft] = []
            seen: set[str] = set()
            for mem in out.memories or []:
                text = " ".join((mem.text or "").strip().split())
                if not text:
                    continue
                key = text.lower()
                if key in seen:
                    continue
                seen.add(key)
                items.append(
                    _MemoryDraft(
                        text=text,
                        tags=_normalize_tags(mem.tags),
                        confidence=mem.confidence,
                    )
                )
                if len(items) >= max_memories:
                    break
            return items
        except Exception as exc:  # pragma: no cover - network/provider dependent
            logger.debug("LLM memory extraction failed; skipping: %s", exc)
            return None


__all__ = ["MEMORY_NOTE_KIND", "MemoryService"]
