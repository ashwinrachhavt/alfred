"""Postgres-backed document and notes storage service.

This mirrors the Mongo DocStorageService API but persists to Postgres via SQLModel.
"""

from __future__ import annotations

import hashlib
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlmodel import Session

from alfred.core.database import SessionLocal
from alfred.core.settings import settings
from alfred.core.utils import clamp_int
from alfred.models.doc_storage import DocChunkRow, DocumentRow, NoteRow
from alfred.schemas.documents import DocumentIngest, NoteCreate
from alfred.schemas.enrichment import normalize_enrichment
from alfred.services.chunking import ChunkingService
from alfred.services.extraction_service import ExtractionService
from alfred.services.graph_service import GraphService

_CHUNKING_SERVICE = ChunkingService()


def _token_count(text: str) -> int:
    try:
        return len((text or "").split())
    except Exception:
        return 0


def _sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _start_of_day_utc(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def _apply_offset_limit(stmt, *, skip: int, limit: int, max_limit: int = 200):  # noqa: ANN001
    return stmt.offset(int(skip)).limit(clamp_int(limit, lo=1, hi=max_limit))


@contextmanager
def _session_scope(session: Session | None = None):
    if session is not None:
        yield session
    else:
        with SessionLocal() as s:
            yield s


@dataclass
class DocStorageService:
    """Postgres-backed storage for notes/documents/chunks."""

    session: Session | None = None
    graph_service: Any | None = None
    extraction_service: Any | None = None

    def __post_init__(self) -> None:
        if (
            self.graph_service is None
            and settings.neo4j_uri
            and settings.neo4j_user
            and settings.neo4j_password
        ):
            self.graph_service = GraphService(
                uri=settings.neo4j_uri,
                user=settings.neo4j_user,
                password=settings.neo4j_password,
            )
        needs_extraction = bool(
            settings.enable_ingest_enrichment
            or settings.enable_ingest_classification
            or self.graph_service is not None
        )
        if self.extraction_service is None and needs_extraction:
            self.extraction_service = ExtractionService()

    # --------------- Health ---------------
    def ping(self) -> bool:
        try:
            with _session_scope(self.session) as s:
                s.exec(select(func.now())).first()
            return True
        except Exception as exc:  # pragma: no cover - external IO
            raise RuntimeError("Postgres not reachable") from exc

    def ensure_indexes(self) -> None:  # indexes handled via Alembic
        return

    # --------------- Notes ---------------
    def create_note(self, note: NoteCreate) -> str:
        record = NoteRow(
            text=note.text,
            source_url=note.source_url,
            meta=note.metadata or {},
        )
        with _session_scope(self.session) as s:
            s.add(record)
            s.commit()
            s.refresh(record)
            return str(record.id)

    def list_notes(self, *, q: Optional[str], skip: int, limit: int) -> Dict[str, Any]:
        with _session_scope(self.session) as s:
            stmt = select(NoteRow)
            if q:
                stmt = stmt.where(NoteRow.text.ilike(f"%{q}%"))
            stmt = _apply_offset_limit(
                stmt.order_by(NoteRow.created_at.desc()),
                skip=skip,
                limit=limit,
                max_limit=200,
            )
            items = s.exec(stmt).all()

            count_stmt = select(func.count()).select_from(NoteRow)
            if q:
                count_stmt = count_stmt.where(NoteRow.text.ilike(f"%{q}%"))
            total = s.exec(count_stmt).one()[0]

            return {
                "items": [
                    {
                        "id": str(n.id),
                        "text": n.text,
                        "source_url": n.source_url,
                        "metadata": n.meta or {},
                        "created_at": n.created_at,
                    }
                    for n in items
                ],
                "total": total,
                "skip": skip,
                "limit": limit,
            }

    def get_note(self, note_id: str) -> Dict[str, Any] | None:
        try:
            uid = uuid.UUID(note_id)
        except Exception:
            return None
        with _session_scope(self.session) as s:
            note = s.get(NoteRow, uid)
            if not note:
                return None
            return {
                "id": str(note.id),
                "text": note.text,
                "source_url": note.source_url,
                "metadata": note.meta or {},
                "created_at": note.created_at,
            }

    def delete_note(self, note_id: str) -> bool:
        try:
            uid = uuid.UUID(note_id)
        except Exception:
            return False
        with _session_scope(self.session) as s:
            note = s.get(NoteRow, uid)
            if not note:
                return False
            s.delete(note)
            s.commit()
            return True

    # --------------- Documents ---------------
    def ingest_document(self, payload: DocumentIngest) -> Dict[str, Any]:
        do_enrichment = bool(settings.enable_ingest_enrichment)
        do_classification = bool(settings.enable_ingest_classification)
        do_graph = bool(do_enrichment and self.graph_service)
        return self._ingest_document(
            payload,
            do_enrichment=do_enrichment,
            do_classification=do_classification,
            do_graph=do_graph,
        )

    def ingest_document_basic(self, payload: DocumentIngest) -> Dict[str, Any]:
        return self._ingest_document(
            payload, do_enrichment=False, do_classification=False, do_graph=False
        )

    def _ingest_document(
        self,
        payload: DocumentIngest,
        *,
        do_enrichment: bool,
        do_classification: bool,
        do_graph: bool,
    ) -> Dict[str, Any]:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        captured_at = payload.captured_at or now
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        day_bucket = _start_of_day_utc(captured_at)
        captured_hour = captured_at.astimezone(timezone.utc).hour

        cleaned_text = payload.cleaned_text
        content_hash = payload.hash or _sha256_hex(cleaned_text)
        tokens = payload.tokens if payload.tokens is not None else _token_count(cleaned_text)
        canonical = payload.canonical_url or payload.source_url
        domain = _domain_from_url(canonical)

        summary_obj: Dict[str, Any] | None = None
        topics_obj: Dict[str, Any] | None = None
        embedding_vec: List[float] | None = None
        entities_obj: Dict[str, Any] | None = None

        if do_enrichment and self.extraction_service:
            try:
                enrich = self.extraction_service.extract_all(
                    cleaned_text=cleaned_text,
                    raw_markdown=payload.raw_markdown,
                    meta=payload.metadata or {},
                    include_graph=not do_graph,
                )
                if not payload.lang and enrich.get("lang"):
                    payload.lang = enrich.get("lang")
                if enrich.get("summary"):
                    s = enrich["summary"] or {}
                    short = s.get("short") or ""
                    long = s.get("long") or None
                    summary_obj = {"short": short, "long": long} if (short or long) else None
                if enrich.get("topics") and not payload.topics:
                    topics_obj = enrich.get("topics")
                if enrich.get("tags") and not payload.tags:
                    payload.tags = enrich.get("tags")
                if enrich.get("embedding") is not None and not payload.embedding:
                    embedding_vec = enrich.get("embedding")
                ents = enrich.get("entities") or []
                if ents:
                    entities_obj = {"items": ents}
                payload.metadata = payload.metadata or {}
                payload.metadata.setdefault(
                    "enrichment",
                    {
                        "summary": summary_obj or {},
                        "topics": topics_obj or {},
                        "tags": payload.tags or [],
                    },
                )
            except Exception:
                pass

        if do_classification and self.extraction_service:
            try:
                taxonomy_ctx = None
                if settings.classification_taxonomy_path:
                    try:
                        with open(
                            settings.classification_taxonomy_path, "r", encoding="utf-8"
                        ) as fh:
                            taxonomy_ctx = fh.read()
                    except Exception:
                        taxonomy_ctx = None
                cls = self.extraction_service.classify_taxonomy(
                    text=payload.raw_markdown or cleaned_text,
                    taxonomy_context=taxonomy_ctx,
                )
                if cls:
                    topics_obj = dict(topics_obj or payload.topics or {})
                    topics_obj["classification"] = cls
            except Exception:
                pass

        enrichment_block = None
        try:
            if (payload.metadata or {}).get("enrichment"):
                enrichment_block = normalize_enrichment(
                    payload.metadata.get("enrichment")
                ).model_dump()
        except Exception:
            enrichment_block = None

        doc_record = DocumentRow(
            source_url=payload.source_url,
            canonical_url=canonical,
            domain=domain,
            title=payload.title,
            content_type=payload.content_type or "web",
            lang=payload.lang,
            raw_markdown=payload.raw_markdown,
            cleaned_text=cleaned_text,
            tokens=tokens,
            hash=content_hash,
            summary=summary_obj
            if summary_obj is not None
            else (payload.summary.model_dump() if payload.summary else None),
            topics=(topics_obj if topics_obj is not None else payload.topics),
            entities=entities_obj,
            tags=payload.tags or [],
            embedding=(embedding_vec if embedding_vec is not None else payload.embedding),
            captured_at=captured_at,
            captured_hour=captured_hour,
            day_bucket=day_bucket,
            published_at=payload.published_at,
            processed_at=payload.processed_at or now,
            created_at=now,
            updated_at=now,
            session_id=payload.session_id,
            agent_run_id=None,
            meta=payload.metadata or {},
            enrichment=enrichment_block,
        )

        with _session_scope(self.session) as s:
            # duplicate fast-path
            existing = s.exec(
                select(DocumentRow.id).where(DocumentRow.hash == content_hash)
            ).first()
            if existing:
                return {
                    "id": str(existing),
                    "duplicate": True,
                    "chunk_count": 0,
                    "chunk_ids": [],
                }

            s.add(doc_record)
            s.commit()
            s.refresh(doc_record)

            chunk_ids: List[str] = []
            chunk_payloads = payload.chunks
            if (not chunk_payloads) and (cleaned_text or (payload.raw_markdown or "").strip()):
                src_text = payload.raw_markdown or cleaned_text
                chunk_payloads = _CHUNKING_SERVICE.chunk(
                    src_text,
                    max_tokens=tokens if tokens and tokens > 0 else 500,
                    overlap=min(100, int((tokens or 500) * 0.2)),
                    content_type=(
                        "markdown" if payload.raw_markdown else (payload.content_type or "web")
                    ),
                    mode="auto",
                )
            if chunk_payloads:
                chunk_rows: list[DocChunkRow] = []
                for ch in chunk_payloads:
                    ctokens = ch.tokens if ch.tokens is not None else _token_count(ch.text)
                    chunk_rows.append(
                        DocChunkRow(
                            doc_id=doc_record.id,
                            idx=ch.idx,
                            text=ch.text,
                            tokens=ctokens,
                            section=ch.section,
                            char_start=ch.char_start,
                            char_end=ch.char_end,
                            embedding=ch.embedding,
                            topics=None,
                            captured_at=captured_at,
                            captured_hour=captured_hour,
                            day_bucket=day_bucket,
                        )
                    )
                s.add_all(chunk_rows)
                s.commit()
                chunk_ids = [str(c.id) for c in chunk_rows]

            return {
                "id": str(doc_record.id),
                "duplicate": False,
                "chunk_count": len(chunk_ids),
                "chunk_ids": chunk_ids,
            }

    def enrich_document(self, doc_id: str, *, force: bool = False) -> Dict[str, Any]:
        try:
            uid = uuid.UUID(doc_id)
        except Exception:
            raise ValueError("Invalid id")

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                raise ValueError("Document not found")

            if (not force) and doc.enrichment:
                return {"id": doc_id, "skipped": True}
            if not self.extraction_service:
                raise RuntimeError("Extraction service not configured")

            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            cleaned_text = (doc.cleaned_text or "").strip()
            raw_markdown = doc.raw_markdown
            metadata = doc.meta or {}

            enrich = self.extraction_service.extract_all(
                cleaned_text=cleaned_text,
                raw_markdown=raw_markdown,
                metadata=metadata,
                include_graph=(self.graph_service is None),
            )

            summary_obj = None
            topics_obj = None
            tags = enrich.get("tags") or []
            embedding_vec = enrich.get("embedding")
            entities_obj = (
                {"items": enrich.get("entities") or []} if enrich.get("entities") else None
            )
            if enrich.get("summary"):
                sdata = enrich["summary"] or {}
                short = sdata.get("short") or ""
                long = sdata.get("long") or None
                summary_obj = {"short": short, "long": long} if (short or long) else None
            if enrich.get("topics"):
                topics_obj = enrich.get("topics")

            updates: Dict[str, Any] = {
                "updated_at": now,
                "processed_at": now,
                "meta": {**metadata, "enrichment": enrich.get("metadata", {})},
            }
            if summary_obj is not None:
                updates["summary"] = summary_obj
            if topics_obj is not None:
                updates["topics"] = topics_obj
            if tags:
                updates["tags"] = tags
            if embedding_vec is not None:
                updates["embedding"] = embedding_vec
            if entities_obj is not None:
                updates["entities"] = entities_obj

            for key, val in updates.items():
                setattr(doc, key, val)
            s.add(doc)
            s.commit()
            return {
                "id": doc_id,
                "skipped": False,
                "has_graph": bool(self.graph_service),
            }

    # --------------- Queries ---------------
    def get_document_text(self, doc_id: str) -> Optional[str]:
        try:
            uid = uuid.UUID(doc_id)
        except Exception:
            return None
        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                return None
            return doc.raw_markdown or doc.cleaned_text or ""

    def get_document(self, doc_id: str) -> Dict[str, Any] | None:
        try:
            uid = uuid.UUID(doc_id)
        except Exception:
            return None
        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                return None
            return {
                "id": str(doc.id),
                "title": doc.title,
                "source_url": doc.source_url,
                "canonical_url": doc.canonical_url,
                "topics": doc.topics,
                "captured_at": doc.captured_at,
                "tokens": doc.tokens,
                "summary": (
                    (doc.summary or {}).get("short") if isinstance(doc.summary, dict) else None
                ),
            }

    def list_documents(
        self,
        *,
        q: Optional[str] = None,
        topic: Optional[str] = None,
        date: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        with _session_scope(self.session) as s:
            stmt = select(DocumentRow).order_by(DocumentRow.captured_at.desc())
            if q:
                stmt = stmt.where(
                    DocumentRow.title.ilike(f"%{q}%") | DocumentRow.cleaned_text.ilike(f"%{q}%")
                )
            if topic:
                stmt = stmt.where(DocumentRow.topics["primary"].astext == topic)  # type: ignore[index]
            if date:
                try:
                    d = datetime.fromisoformat(date)
                    stmt = stmt.where(DocumentRow.day_bucket == d.date())
                except Exception:
                    pass
            if start or end:
                rng = []
                if start:
                    try:
                        rng.append(DocumentRow.captured_at >= datetime.fromisoformat(start))
                    except Exception:
                        pass
                if end:
                    try:
                        rng.append(DocumentRow.captured_at <= datetime.fromisoformat(end))
                    except Exception:
                        pass
                for cond in rng:
                    stmt = stmt.where(cond)

            stmt = _apply_offset_limit(stmt, skip=skip, limit=limit, max_limit=200)
            rows = s.exec(stmt).all()

            count_stmt = select(func.count()).select_from(DocumentRow)
            if q:
                count_stmt = count_stmt.where(
                    DocumentRow.title.ilike(f"%{q}%") | DocumentRow.cleaned_text.ilike(f"%{q}%")
                )
            if topic:
                count_stmt = count_stmt.where(DocumentRow.topics["primary"].astext == topic)  # type: ignore[index]
            if date:
                try:
                    d = datetime.fromisoformat(date)
                    count_stmt = count_stmt.where(DocumentRow.day_bucket == d.date())
                except Exception:
                    pass
            if start:
                try:
                    count_stmt = count_stmt.where(
                        DocumentRow.captured_at >= datetime.fromisoformat(start)
                    )
                except Exception:
                    pass
            if end:
                try:
                    count_stmt = count_stmt.where(
                        DocumentRow.captured_at <= datetime.fromisoformat(end)
                    )
                except Exception:
                    pass
            total = s.exec(count_stmt).one()[0]

            items = []
            for drow in rows:
                items.append(
                    {
                        "id": str(drow.id),
                        "title": drow.title,
                        "source_url": drow.source_url,
                        "canonical_url": drow.canonical_url,
                        "topics": drow.topics,
                        "captured_at": drow.captured_at,
                        "tokens": drow.tokens,
                        "summary": (
                            (drow.summary or {}).get("short")
                            if isinstance(drow.summary, dict)
                            else None
                        ),
                    }
                )
            return {"items": items, "total": total, "skip": skip, "limit": limit}

    def list_chunks(
        self,
        *,
        doc_id: Optional[str] = None,
        topic: Optional[str] = None,
        date: Optional[str] = None,
        skip: int = 0,
        limit: int = 20,
    ) -> Dict[str, Any]:
        with _session_scope(self.session) as s:
            stmt = select(DocChunkRow).order_by(DocChunkRow.captured_at.desc())
            if doc_id:
                try:
                    uid = uuid.UUID(doc_id)
                    stmt = stmt.where(DocChunkRow.doc_id == uid)
                except Exception:
                    raise ValueError("Invalid doc_id")
            if topic:
                stmt = stmt.where(DocChunkRow.topics["primary"].astext == topic)  # type: ignore[index]
            if date:
                try:
                    d = datetime.fromisoformat(date)
                    stmt = stmt.where(DocChunkRow.day_bucket == d.date())
                except Exception:
                    pass
            stmt = _apply_offset_limit(stmt, skip=skip, limit=limit, max_limit=200)
            rows = s.exec(stmt).all()

            count_stmt = select(func.count()).select_from(DocChunkRow)
            if doc_id:
                try:
                    uid = uuid.UUID(doc_id)
                    count_stmt = count_stmt.where(DocChunkRow.doc_id == uid)
                except Exception:
                    pass
            if topic:
                count_stmt = count_stmt.where(DocChunkRow.topics["primary"].astext == topic)  # type: ignore[index]
            if date:
                try:
                    d = datetime.fromisoformat(date)
                    count_stmt = count_stmt.where(DocChunkRow.day_bucket == d.date())
                except Exception:
                    pass
            total = s.exec(count_stmt).one()[0]

            items = []
            for c in rows:
                text = c.text or ""
                preview = text[:260]
                items.append(
                    {
                        "id": str(c.id),
                        "doc_id": str(c.doc_id),
                        "idx": c.idx,
                        "section": c.section,
                        "text": preview,
                        "captured_at": c.captured_at,
                    }
                )
            return {"items": items, "total": total, "skip": skip, "limit": limit}


__all__ = ["DocStorageService"]
