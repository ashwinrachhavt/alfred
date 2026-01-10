"""Postgres-backed document and notes storage service.

This mirrors the Mongo DocStorageService API but persists to Postgres via SQLModel.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from cachetools import TTLCache
from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import load_only
from sqlmodel import Session

from alfred.core.database import SessionLocal
from alfred.core.exceptions import BadRequestError, NotFoundError
from alfred.core.settings import settings
from alfred.core.utils import clamp_int
from alfred.models.doc_storage import DocChunkRow, DocumentRow, QuickNoteRow
from alfred.schemas.documents import DocumentIngest, NoteCreate
from alfred.schemas.enrichment import normalize_enrichment
from alfred.services.chunking import ChunkingService
from alfred.services.doc_storage.semantic_map import (
    extract_embedding as _extract_embedding,
)
from alfred.services.doc_storage.semantic_map import (
    project_texts_to_3d as _project_texts_to_3d,
)
from alfred.services.doc_storage.semantic_map import (
    project_vectors_to_3d as _project_vectors_to_3d,
)
from alfred.services.doc_storage.semantic_map import (
    topic_to_color as _topic_to_color,
)
from alfred.services.doc_storage.utils import (
    apply_offset_limit as _apply_offset_limit,
)
from alfred.services.doc_storage.utils import (
    best_effort_cover_url as _best_effort_cover_url,
)
from alfred.services.doc_storage.utils import (
    best_effort_primary_topic as _best_effort_primary_topic,
)
from alfred.services.doc_storage.utils import (
    best_effort_title as _best_effort_title,
)
from alfred.services.doc_storage.utils import (
    build_title_image_prompt as _build_title_image_prompt,
)
from alfred.services.doc_storage.utils import (
    decode_cursor as _decode_cursor,
)
from alfred.services.doc_storage.utils import (
    domain_from_url as _domain_from_url,
)
from alfred.services.doc_storage.utils import (
    encode_cursor as _encode_cursor,
)
from alfred.services.doc_storage.utils import (
    excerpt_for_cover_prompt as _excerpt_for_cover_prompt,
)
from alfred.services.doc_storage.utils import (
    first_str as _first_str,
)
from alfred.services.doc_storage.utils import (
    parse_iso_date as _parse_iso_date,
)
from alfred.services.doc_storage.utils import (
    parse_iso_datetime as _parse_iso_datetime,
)
from alfred.services.doc_storage.utils import (
    parse_uuid as _parse_uuid,
)
from alfred.services.doc_storage.utils import (
    read_text_file_best_effort as _read_text_file_best_effort,
)
from alfred.services.doc_storage.utils import (
    sha256_hex as _sha256_hex,
)
from alfred.services.doc_storage.utils import (
    start_of_day_utc as _start_of_day_utc,
)
from alfred.services.doc_storage.utils import (
    token_count as _token_count,
)
from alfred.services.extraction_service import ExtractionService
from alfred.services.graph_service import GraphService
from alfred.services.llm_service import LLMService

_CHUNKING_SERVICE = ChunkingService()
logger = logging.getLogger(__name__)

HSL_LIGHTNESS_MIDPOINT = 0.5

SEMANTIC_MAP_DIMENSIONS = 3
MIN_PROJECTABLE_ITEMS = 3
PAIR_ITEM_COUNT = 2
MATRIX_EXPECTED_NDIM = 2
MIN_TFIDF_FEATURES = 2


def _chunk_payloads_for_text(
    *,
    src_text: str,
    max_tokens: int | None,
    content_type: str,
) -> list[Any]:
    """Chunk text into model-friendly sections for storage.

    Uses a conservative overlap based on the token budget.
    """

    token_budget = int(max_tokens or 0)
    budget = token_budget if token_budget > 0 else 500
    overlap = min(100, int(budget * 0.2))
    return _CHUNKING_SERVICE.chunk(
        src_text,
        max_tokens=budget,
        overlap=overlap,
        content_type=content_type,
        mode="auto",
    )


def _build_doc_chunk_rows(
    *,
    doc_id: uuid.UUID,
    chunk_payloads: list[Any],
    captured_at: datetime,
    captured_hour: int,
    day_bucket: date,
) -> list[DocChunkRow]:
    """Convert chunk payloads into persisted `DocChunkRow` records."""

    rows: list[DocChunkRow] = []
    for ch in chunk_payloads:
        ctokens = ch.tokens if ch.tokens is not None else _token_count(ch.text)
        rows.append(
            DocChunkRow(
                doc_id=doc_id,
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
    return rows


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
    llm_service: Any | None = None
    redis_client: Any | None = None
    semantic_map_cache_ttl_seconds: int = 600
    semantic_map_cache_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    semantic_map_cache: TTLCache[str, dict[str, Any]] = field(
        default_factory=lambda: TTLCache(maxsize=8, ttl=600),
        repr=False,
    )

    def __post_init__(self) -> None:
        # Keep initialization side-effect free (no DB/network clients).
        # Enrichment/classification/graph connections are created lazily only
        # when an enrichment path is invoked.
        self.semantic_map_cache = TTLCache(
            maxsize=8,
            ttl=int(self.semantic_map_cache_ttl_seconds),
        )
        return

    def _ensure_graph_service(self) -> Any | None:
        """Lazily create the graph service if Neo4j is configured."""

        if self.graph_service is not None:
            return self.graph_service
        if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
            return None
        self.graph_service = GraphService(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )
        return self.graph_service

    def _ensure_extraction_service(self) -> ExtractionService | None:
        """Lazily create the extraction service if enrichment is enabled."""

        if self.extraction_service is not None:
            return self.extraction_service
        needs_extraction = bool(
            settings.enable_ingest_enrichment
            or settings.enable_ingest_classification
            or self._ensure_graph_service() is not None
        )
        if not needs_extraction:
            return None
        self.extraction_service = ExtractionService(llm_service=self._ensure_llm_service())
        return self.extraction_service

    def _ensure_llm_service(self) -> LLMService:
        """Lazily create the LLM service for AI-powered features."""

        if self.llm_service is not None:
            return self.llm_service
        self.llm_service = LLMService()
        return self.llm_service

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
        record = QuickNoteRow(
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
            stmt = select(QuickNoteRow)
            if q:
                stmt = stmt.where(QuickNoteRow.text.ilike(f"%{q}%"))
            stmt = _apply_offset_limit(
                stmt.order_by(QuickNoteRow.created_at.desc()),
                skip=skip,
                limit=limit,
                max_limit=200,
            )
            items = s.exec(stmt).all()

            count_stmt = select(func.count()).select_from(QuickNoteRow)
            if q:
                count_stmt = count_stmt.where(QuickNoteRow.text.ilike(f"%{q}%"))
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
        uid = _parse_uuid(note_id)
        if uid is None:
            return None
        with _session_scope(self.session) as s:
            note = s.get(QuickNoteRow, uid)
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
        uid = _parse_uuid(note_id)
        if uid is None:
            return False
        with _session_scope(self.session) as s:
            note = s.get(QuickNoteRow, uid)
            if not note:
                return False
            s.delete(note)
            s.commit()
            return True

    # --------------- Documents ---------------
    def ingest_document(self, payload: DocumentIngest) -> Dict[str, Any]:
        do_enrichment = bool(settings.enable_ingest_enrichment)
        do_classification = bool(settings.enable_ingest_classification)
        if do_enrichment or do_classification:
            self._ensure_extraction_service()
        do_graph = bool(do_enrichment and self._ensure_graph_service())
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

    def ingest_document_store_only(self, payload: DocumentIngest) -> Dict[str, Any]:
        """Persist a document quickly without chunking or enrichment.

        This is intended for latency-sensitive ingestion paths (e.g., browser extension
        page saves) where chunking/enrichment can be performed asynchronously.
        """
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
            summary=(payload.summary.model_dump() if payload.summary else None),
            topics=payload.topics,
            entities=None,
            tags=payload.tags or [],
            embedding=payload.embedding,
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
            existing = s.exec(
                select(DocumentRow.id).where(DocumentRow.hash == content_hash)
            ).first()
            if existing:
                return {
                    "id": str(existing),
                    "duplicate": True,
                }

            s.add(doc_record)
            s.commit()
            s.refresh(doc_record)
            return {
                "id": str(doc_record.id),
                "duplicate": False,
            }

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
                taxonomy_ctx = _read_text_file_best_effort(settings.classification_taxonomy_path)
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
                chunk_payloads = _chunk_payloads_for_text(
                    src_text=src_text,
                    max_tokens=tokens,
                    content_type=(
                        "markdown" if payload.raw_markdown else (payload.content_type or "web")
                    ),
                )
            if chunk_payloads:
                chunk_rows = _build_doc_chunk_rows(
                    doc_id=doc_record.id,
                    chunk_payloads=list(chunk_payloads),
                    captured_at=captured_at,
                    captured_hour=captured_hour,
                    day_bucket=day_bucket,
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

    def process_document(self, doc_id: str, *, force: bool = False) -> Dict[str, Any]:
        """Generate missing chunks and (optionally) enrich/classify an existing document."""
        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        do_enrichment = bool(settings.enable_ingest_enrichment)
        do_classification = bool(settings.enable_ingest_classification)
        if do_enrichment or do_classification:
            self._ensure_extraction_service()

        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.raw_markdown,
                        DocumentRow.cleaned_text,
                        DocumentRow.tokens,
                        DocumentRow.content_type,
                        DocumentRow.captured_at,
                        DocumentRow.captured_hour,
                        DocumentRow.day_bucket,
                        DocumentRow.created_at,
                        DocumentRow.lang,
                        DocumentRow.summary,
                        DocumentRow.topics,
                        DocumentRow.tags,
                        DocumentRow.entities,
                        DocumentRow.embedding,
                        DocumentRow.enrichment,
                        DocumentRow.processed_at,
                        DocumentRow.updated_at,
                        DocumentRow.meta,
                    ),
                ),
            )
            if not doc:
                raise NotFoundError("Document not found", code="document_not_found")

            # ----------------- chunking -----------------
            existing_chunks = s.exec(
                select(func.count()).select_from(DocChunkRow).where(DocChunkRow.doc_id == uid)
            ).one()
            created_chunks = 0
            if int(existing_chunks or 0) == 0:
                src_text = (doc.raw_markdown or doc.cleaned_text or "").strip()
                if src_text:
                    tokens = int(doc.tokens or 0) or _token_count(src_text)
                    chunk_payloads = _chunk_payloads_for_text(
                        src_text=src_text,
                        max_tokens=tokens,
                        content_type=(
                            "markdown" if doc.raw_markdown else (doc.content_type or "web")
                        ),
                    )
                    if chunk_payloads:
                        day_bucket = doc.day_bucket or _start_of_day_utc(doc.captured_at)
                        captured_hour = (
                            int(doc.captured_hour)
                            if doc.captured_hour is not None
                            else doc.captured_at.astimezone(timezone.utc).hour
                        )
                        chunk_rows = _build_doc_chunk_rows(
                            doc_id=uid,
                            chunk_payloads=list(chunk_payloads),
                            captured_at=doc.captured_at,
                            captured_hour=captured_hour,
                            day_bucket=day_bucket,
                        )
                        s.add_all(chunk_rows)
                        s.commit()
                        created_chunks = len(chunk_rows)

            # ----------------- enrichment + classification -----------------
            ran_enrichment = False
            ran_classification = False
            if (do_enrichment or do_classification) and self.extraction_service:
                has_classification = bool(
                    isinstance(doc.topics, dict) and (doc.topics or {}).get("classification")
                )
                if (not force) and doc.enrichment and (not do_classification or has_classification):
                    return {
                        "id": doc_id,
                        "chunks_created": created_chunks,
                        "enrichment_skipped": True,
                    }

                now = datetime.utcnow().replace(tzinfo=timezone.utc)
                cleaned_text = (doc.cleaned_text or "").strip()
                raw_markdown = doc.raw_markdown
                metadata = doc.meta or {}

                enrich: dict[str, Any] = {}
                if do_enrichment:
                    try:
                        enrich = self.extraction_service.extract_all(
                            cleaned_text=cleaned_text,
                            raw_markdown=raw_markdown,
                            metadata=metadata,
                            include_graph=(self.graph_service is None),
                        )
                        ran_enrichment = True
                    except Exception:
                        enrich = {}

                topics_obj: dict[str, Any] | None = None
                if isinstance(enrich.get("topics"), dict):
                    topics_obj = dict(enrich.get("topics") or {})
                elif isinstance(doc.topics, dict):
                    topics_obj = dict(doc.topics or {})

                if do_classification:
                    try:
                        taxonomy_ctx = _read_text_file_best_effort(
                            settings.classification_taxonomy_path
                        )
                        cls = self.extraction_service.classify_taxonomy(
                            text=raw_markdown or cleaned_text,
                            taxonomy_context=taxonomy_ctx,
                        )
                        if cls:
                            topics_obj = dict(topics_obj or {})
                            topics_obj["classification"] = cls
                            ran_classification = True
                    except Exception:
                        pass

                if enrich.get("lang") and (force or not doc.lang):
                    doc.lang = enrich.get("lang")
                if enrich.get("summary") and (force or not doc.summary):
                    sdata = enrich.get("summary") or {}
                    short = sdata.get("short") or ""
                    long = sdata.get("long") or None
                    doc.summary = {"short": short, "long": long} if (short or long) else None
                if topics_obj and (force or not doc.topics):
                    doc.topics = topics_obj
                tags = enrich.get("tags") or []
                if isinstance(tags, list) and tags and (force or not (doc.tags or [])):
                    doc.tags = tags
                if enrich.get("entities") and (force or not doc.entities):
                    doc.entities = {"items": enrich.get("entities") or []}
                if enrich.get("embedding") is not None and (force or not doc.embedding):
                    doc.embedding = enrich.get("embedding")

                enrichment_block = None
                try:
                    summary_dict = enrich.get("summary") or {}
                    enrichment_block = normalize_enrichment(
                        {
                            "summary": summary_dict,
                            "bullets": summary_dict.get("bullets") or [],
                            "key_points": summary_dict.get("key_points") or [],
                            "topics": topics_obj,
                            "tags": tags if isinstance(tags, list) else [],
                        }
                    ).model_dump()
                except Exception:
                    enrichment_block = None

                doc.updated_at = now
                doc.processed_at = now
                if enrichment_block is not None:
                    doc.enrichment = enrichment_block
                s.add(doc)
                s.commit()

            return {
                "id": doc_id,
                "chunks_created": created_chunks,
                "ran_enrichment": ran_enrichment,
                "ran_classification": ran_classification,
                "has_graph": bool(self.graph_service),
            }

    def enrich_document(self, doc_id: str, *, force: bool = False) -> Dict[str, Any]:
        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.cleaned_text,
                        DocumentRow.raw_markdown,
                        DocumentRow.meta,
                        DocumentRow.enrichment,
                        DocumentRow.summary,
                        DocumentRow.topics,
                        DocumentRow.tags,
                        DocumentRow.entities,
                        DocumentRow.embedding,
                        DocumentRow.updated_at,
                        DocumentRow.processed_at,
                    ),
                ),
            )
            if not doc:
                raise NotFoundError("Document not found", code="document_not_found")

            if (not force) and doc.enrichment:
                return {"id": doc_id, "skipped": True}
            if not self._ensure_extraction_service():
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
                "meta": metadata,
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

            enrichment_block = None
            try:
                summary_dict = enrich.get("summary") or {}
                enrichment_block = normalize_enrichment(
                    {
                        "summary": summary_dict,
                        "bullets": summary_dict.get("bullets") or [],
                        "key_points": summary_dict.get("key_points") or [],
                        "topics": topics_obj,
                        "tags": tags,
                    }
                ).model_dump()
            except Exception:
                enrichment_block = None
            if enrichment_block is not None:
                updates["enrichment"] = enrichment_block

            for key, val in updates.items():
                setattr(doc, key, val)
            s.add(doc)
            s.commit()
            return {
                "id": doc_id,
                "skipped": False,
                "has_graph": bool(self.graph_service),
            }

    def list_documents_needing_concepts_extraction(
        self,
        *,
        limit: int = 100,
        min_age_hours: int = 0,
        force: bool = False,
    ) -> list[DocumentRow]:
        """Return documents that are candidates for concept extraction.

        By default, returns documents that:
        - have non-empty text (cleaned_text)
        - have not been extracted yet (`concepts_extracted_at IS NULL`)

        `force=True` includes already-extracted documents (useful for reprocessing).
        """

        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        # Use SQLModel's select so `Session.exec()` yields model instances (not Row tuples).
        from sqlmodel import select as sql_select  # noqa: PLC0415

        stmt = sql_select(DocumentRow).where(func.length(func.trim(DocumentRow.cleaned_text)) > 0)
        if not force:
            stmt = stmt.where(DocumentRow.concepts_extracted_at.is_(None))
        if min_age_hours and min_age_hours > 0:
            cutoff = now - timedelta(hours=int(min_age_hours))
            stmt = stmt.where(DocumentRow.created_at <= cutoff)
        stmt = stmt.order_by(DocumentRow.created_at.asc()).limit(clamp_int(limit, lo=1, hi=500))
        with _session_scope(self.session) as s:
            return s.exec(stmt).all()

    def list_documents_needing_title_images(
        self,
        *,
        limit: int = 100,
        min_age_hours: int = 0,
        force: bool = False,
    ) -> list[DocumentRow]:
        """Return documents that are candidates for title/cover image generation.

        By default, returns documents that:
        - do not have an image yet (`image IS NULL`)

        `force=True` includes documents that already have images (useful for reprocessing).
        """

        limit = clamp_int(limit, lo=1, hi=500)
        now = datetime.utcnow().replace(tzinfo=timezone.utc)

        from sqlmodel import select as sql_select  # noqa: PLC0415

        stmt = sql_select(DocumentRow)
        if not force:
            stmt = stmt.where(DocumentRow.image.is_(None))
        if min_age_hours and min_age_hours > 0:
            cutoff = now - timedelta(hours=int(min_age_hours))
            stmt = stmt.where(DocumentRow.created_at <= cutoff)
        stmt = stmt.order_by(DocumentRow.created_at.desc()).limit(limit)

        with _session_scope(self.session) as s:
            return s.exec(stmt).all()

    def extract_document_concepts(self, doc_id: str, *, force: bool = False) -> Dict[str, Any]:
        """Extract and persist a lightweight concept graph for a stored document.

        This is intentionally separate from document enrichment. The output is stored
        on the document row under `concepts`, plus `concepts_extracted_at` for ops/backlog.
        """

        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                raise NotFoundError("Document not found", code="document_not_found")

            if (not force) and doc.concepts_extracted_at:
                return {"id": doc_id, "skipped": True}

            text = (doc.raw_markdown or doc.cleaned_text or "").strip()
            if not text:
                raise BadRequestError("Document has no text", code="missing_document_text")

            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            extractor = self.extraction_service or ExtractionService(
                llm_service=self._ensure_llm_service()
            )

            try:
                graph = extractor.extract_graph(text=text, metadata={"doc_id": doc_id})
                payload = {
                    "entities": graph.get("entities") or [],
                    "relations": graph.get("relations") or [],
                    "topics": graph.get("topics") or [],
                }
                doc.concepts = payload
                doc.concepts_extracted_at = now
                doc.concepts_error = None
                doc.updated_at = now
                s.add(doc)
                s.commit()
            except Exception as exc:
                # Persist the error for operational inspection, but keep the exception visible.
                doc.concepts_error = str(exc)[:8000]
                doc.updated_at = now
                s.add(doc)
                s.commit()
                raise

            gs = self.graph_service or self._ensure_graph_service()
            if gs is not None:
                try:
                    gs.upsert_document_node(
                        doc_id=str(doc.id), title=doc.title, source_url=doc.source_url
                    )
                    for ent in payload["entities"]:
                        name = (ent.get("name") or "").strip() if isinstance(ent, dict) else ""
                        if not name:
                            continue
                        gs.upsert_entity(
                            name=name, type_=ent.get("type") if isinstance(ent, dict) else None
                        )
                        gs.link_doc_to_entity(doc_id=str(doc.id), name=name)
                    for rel in payload["relations"]:
                        if not isinstance(rel, dict):
                            continue
                        from_name = (rel.get("from") or "").strip()
                        to_name = (rel.get("to") or "").strip()
                        if from_name and to_name:
                            gs.link_entities(
                                from_name=from_name,
                                to_name=to_name,
                                rel_type=str(rel.get("type") or "RELATED_TO"),
                            )
                except Exception:
                    # Graph syncing is best-effort; do not fail concept extraction if Neo4j is flaky.
                    pass

            return {
                "id": doc_id,
                "skipped": False,
                "entities": len(payload["entities"]),
                "relations": len(payload["relations"]),
            }

    # --------------- Queries ---------------
    def get_document_text(self, doc_id: str) -> Optional[str]:
        uid = _parse_uuid(doc_id)
        if uid is None:
            return None
        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.raw_markdown,
                        DocumentRow.cleaned_text,
                    ),
                ),
            )
            if not doc:
                return None
            return doc.raw_markdown or doc.cleaned_text or ""

    def get_document(self, doc_id: str) -> Dict[str, Any] | None:
        uid = _parse_uuid(doc_id)
        if uid is None:
            return None
        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.title,
                        DocumentRow.source_url,
                        DocumentRow.canonical_url,
                        DocumentRow.topics,
                        DocumentRow.captured_at,
                        DocumentRow.tokens,
                        DocumentRow.summary,
                    ),
                ),
            )
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

    def get_document_details(self, doc_id: str) -> Dict[str, Any] | None:
        """Return the full persisted document payload for deep inspection views."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            return None

        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.source_url,
                        DocumentRow.canonical_url,
                        DocumentRow.domain,
                        DocumentRow.title,
                        DocumentRow.content_type,
                        DocumentRow.lang,
                        DocumentRow.raw_markdown,
                        DocumentRow.image,
                        DocumentRow.cleaned_text,
                        DocumentRow.tokens,
                        DocumentRow.summary,
                        DocumentRow.topics,
                        DocumentRow.entities,
                        DocumentRow.tags,
                        DocumentRow.captured_at,
                        DocumentRow.day_bucket,
                        DocumentRow.created_at,
                        DocumentRow.updated_at,
                        DocumentRow.session_id,
                        DocumentRow.meta,
                        DocumentRow.enrichment,
                    ),
                ),
            )
            if not doc:
                return None

            cover_url = None
            if doc.image:
                cover_url = f"/api/documents/{doc_id}/image"
            else:
                cover_url = _best_effort_cover_url(doc.meta or {})

            return {
                "id": str(doc.id),
                "source_url": doc.source_url,
                "canonical_url": doc.canonical_url,
                "domain": doc.domain,
                "title": doc.title,
                "cover_image_url": cover_url,
                "content_type": doc.content_type,
                "lang": doc.lang,
                "raw_markdown": doc.raw_markdown,
                "cleaned_text": doc.cleaned_text,
                "tokens": doc.tokens,
                "summary": doc.summary,
                "topics": doc.topics,
                "entities": doc.entities,
                "tags": doc.tags or [],
                "captured_at": doc.captured_at,
                "day_bucket": doc.day_bucket,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
                "session_id": doc.session_id,
                "metadata": doc.meta or {},
                "enrichment": doc.enrichment,
            }

    def update_document_text(
        self,
        doc_id: str,
        *,
        title: str | None = None,
        cleaned_text: str | None = None,
        raw_markdown: str | None = None,
        tiptap_json: dict[str, Any] | None = None,
        metadata_update: dict[str, Any] | None = None,
    ) -> Dict[str, Any] | None:
        """Update a document's editable text payload.

        This is intentionally lightweight:
        - Keeps the document identity stable (does not change hash/source_url).
        - Updates `updated_at` and refreshes `tokens` when plain-text changes.
        - Optionally stores TipTap editor JSON under metadata.
        - Optionally merges additional metadata onto the document record.
        """

        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        now = datetime.now(timezone.utc)

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                return None

            if title is not None:
                doc.title = title

            if cleaned_text is not None:
                doc.cleaned_text = cleaned_text
                doc.tokens = _token_count(cleaned_text)

            if raw_markdown is not None:
                doc.raw_markdown = raw_markdown

            if tiptap_json is not None:
                meta = dict(doc.meta or {})
                editor_meta = meta.get("editor")
                if not isinstance(editor_meta, dict):
                    editor_meta = {}
                editor_meta = dict(editor_meta)
                editor_meta.update({"provider": "tiptap", "tiptap_json": tiptap_json})
                meta["editor"] = editor_meta
                doc.meta = meta

            if metadata_update is not None:
                meta = dict(doc.meta or {})
                updates = dict(metadata_update)
                if isinstance(updates.get("notion"), dict) and isinstance(meta.get("notion"), dict):
                    merged = dict(meta["notion"])
                    merged.update(updates["notion"])
                    updates["notion"] = merged
                meta.update(updates)
                doc.meta = meta

            doc.updated_at = now
            s.add(doc)
            s.commit()

        return self.get_document_details(doc_id)

    def get_document_image_bytes(self, doc_id: str) -> bytes | None:
        """Return the stored document cover image bytes, if present."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            return None

        with _session_scope(self.session) as s:
            doc = s.get(
                DocumentRow,
                uid,
                options=(load_only(DocumentRow.id, DocumentRow.image),),
            )
            if not doc or not doc.image:
                return None
            return bytes(doc.image)

    def generate_document_title_image(
        self,
        doc_id: str,
        *,
        force: bool = False,
        model: str = "gpt-image-1",
        size: str = "1024x1024",
        quality: str = "high",
    ) -> Dict[str, Any]:
        """Generate and persist a title/cover image for a document via OpenAI."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        with _session_scope(self.session) as s:
            row = s.exec(
                select(
                    DocumentRow.image,
                    DocumentRow.meta,
                    DocumentRow.title,
                    DocumentRow.topics,
                    DocumentRow.summary,
                    DocumentRow.domain,
                    DocumentRow.raw_markdown,
                    DocumentRow.cleaned_text,
                ).where(DocumentRow.id == uid)
            ).one_or_none()
            if row is None:
                raise NotFoundError("Document not found", code="document_not_found")

            image_existing, meta, title_raw, topics, summary, domain, raw_markdown, cleaned_text = (
                row
            )
            if (not force) and image_existing:
                return {"id": doc_id, "skipped": True, "reason": "image_already_present"}

            meta = meta or {}
            title = _best_effort_title(row_title=title_raw, meta=meta)
            primary_topic = _best_effort_primary_topic(topics, meta)

            summary_short = None
            if isinstance(summary, dict):
                summary_short = _first_str(summary.get("short"), summary.get("summary"))

            source_text = (raw_markdown or cleaned_text or "").strip()
            excerpt = _excerpt_for_cover_prompt(source_text, max_chars=900)
            visual_brief = None
            try:
                if excerpt:
                    llm = self._ensure_llm_service()
                    visual_brief = llm.build_cover_visual_brief(
                        title=title,
                        primary_topic=primary_topic,
                        domain=domain,
                        excerpt=excerpt,
                        summary=summary_short,
                    )
            except Exception:
                visual_brief = None

            prompt = _build_title_image_prompt(
                title=title,
                summary=summary_short,
                primary_topic=primary_topic,
                domain=domain,
                excerpt=excerpt,
                visual_brief=visual_brief,
            )

            model_used = model
            tried_models = [model]
            if model == "gpt-image-1":
                tried_models = ["gpt-image-1", "dall-e-3", "dall-e-2"]

            image_bytes: bytes | None = None
            revised_prompt: str | None = None
            last_exc: Exception | None = None

            for candidate in tried_models:
                try:
                    image_bytes, revised_prompt = llm.generate_image_png(
                        prompt=prompt,
                        model=candidate,
                        size=size,
                        quality=quality,
                    )
                    model_used = candidate
                    last_exc = None
                    break
                except Exception as exc:  # noqa: BLE001
                    # If gpt-image-1 is blocked due to org verification, fall back to DALL·E.
                    if candidate == "gpt-image-1":
                        msg = str(exc)
                        if (
                            "must be verified" in msg.lower()
                            or "verify organization" in msg.lower()
                            or "403" in msg
                        ):
                            last_exc = exc
                            continue
                    raise

            if image_bytes is None:
                raise last_exc or RuntimeError("Failed to generate image")

            now = datetime.utcnow().replace(tzinfo=timezone.utc)

            generated_meta = {
                "model": model_used,
                "requested_model": model,
                "size": size,
                "quality": quality,
                "prompt": prompt,
                "prompt_strategy": "content_excerpt",
                "content_hash": _sha256_hex(source_text) if source_text else None,
                "revised_prompt": revised_prompt,
                "generated_at": now.isoformat(),
            }
            new_meta = {**meta, "generated_cover_image": generated_meta}

            s.exec(
                update(DocumentRow)
                .where(DocumentRow.id == uid)
                .values(
                    {
                        DocumentRow.__table__.c.image: image_bytes,
                        DocumentRow.__table__.c.updated_at: now,
                        DocumentRow.__table__.c.metadata: new_meta,
                    }
                )
            )
            s.commit()

            return {
                "id": doc_id,
                "skipped": False,
                "model": model_used,
                "size": size,
                "quality": quality,
            }

    # --------------- Explorer (Atheneum) ---------------
    def list_explorer_documents(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        filter_topic: str | None = None,
        search: str | None = None,
    ) -> Dict[str, Any]:
        """Cursor-paginated documents list for the Shelf (Explorer) view."""

        limit = max(1, min(int(limit), 200))
        topic = (filter_topic or "").strip() or None
        q = (search or "").strip() or None

        cursor_created_at: datetime | None = None
        cursor_uuid: uuid.UUID | None = None
        if cursor:
            cursor_created_at, cursor_id = _decode_cursor(cursor)
            cursor_uuid = _parse_uuid(cursor_id)
            if cursor_uuid is None:
                raise BadRequestError("Invalid cursor", code="invalid_cursor")

        with _session_scope(self.session) as s:
            has_image = (DocumentRow.image.isnot(None)).label("has_image")
            stmt = select(
                DocumentRow.id,
                DocumentRow.title,
                DocumentRow.meta,
                DocumentRow.summary,
                DocumentRow.topics,
                DocumentRow.created_at,
                DocumentRow.day_bucket,
                DocumentRow.source_url,
                DocumentRow.canonical_url,
                has_image,
            )

            if q:
                stmt = stmt.where(
                    DocumentRow.title.ilike(f"%{q}%") | DocumentRow.cleaned_text.ilike(f"%{q}%")
                )

            if topic:
                stmt = stmt.where(DocumentRow.topics["primary"].astext == topic)  # type: ignore[index]

            if cursor_created_at is not None and cursor_uuid is not None:
                stmt = stmt.where(
                    or_(
                        DocumentRow.created_at < cursor_created_at,
                        and_(
                            DocumentRow.created_at == cursor_created_at,
                            DocumentRow.id < cursor_uuid,
                        ),
                    )
                )

            stmt = stmt.order_by(DocumentRow.created_at.desc(), DocumentRow.id.desc()).limit(
                limit + 1
            )
            rows = s.exec(stmt).all()

        page_rows = rows[:limit]
        has_more = len(rows) > limit

        items: list[dict[str, Any]] = []
        for doc in page_rows:
            meta = doc.meta or {}
            title = _best_effort_title(row_title=doc.title, meta=meta)
            primary_topic = _best_effort_primary_topic(doc.topics, meta)

            summary_short = None
            if isinstance(doc.summary, dict):
                summary_short = _first_str(doc.summary.get("short"), doc.summary.get("summary"))

            items.append(
                {
                    "id": str(doc.id),
                    "title": title,
                    "cover_image_url": (
                        f"/api/documents/{doc.id}/image"
                        if getattr(doc, "has_image", False)
                        else _best_effort_cover_url(meta)
                    ),
                    "summary": summary_short,
                    "created_at": doc.created_at,
                    "day_bucket": doc.day_bucket,
                    "primary_topic": primary_topic,
                    "source_url": doc.source_url,
                    "canonical_url": doc.canonical_url,
                }
            )

        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(created_at=last.created_at, doc_id=str(last.id))

        return {
            "items": items,
            "next_cursor": next_cursor,
            "limit": limit,
            "filter_topic": topic,
            "search": q,
        }

    def get_semantic_map_points(
        self,
        *,
        limit: int = 5000,
        force_refresh: bool = False,
    ) -> list[dict[str, Any]]:
        """Return 3D-projected document points for the semantic map (Galaxy)."""

        limit = max(1, min(int(limit), 20_000))
        cache_key = f"documents:semantic-map:v1:limit:{limit}"

        version = self._current_semantic_map_version()
        if not force_refresh:
            cached = self._get_cached_semantic_map(cache_key, version=version)
            if cached is not None:
                return cached

        docs = self._fetch_docs_for_semantic_map(limit=limit)

        vectors: list[list[float]] = []
        embedded_docs: list[dict[str, Any]] = []
        expected_dim: int | None = None
        for d in docs:
            emb = _extract_embedding(d.get("embedding"), d.get("enrichment"))
            if not emb:
                continue
            if expected_dim is None:
                expected_dim = len(emb)
            if len(emb) != expected_dim:
                continue
            vectors.append(emb)
            embedded_docs.append(d)

        items: list[dict[str, Any]] = []

        if len(vectors) >= MIN_PROJECTABLE_ITEMS:
            coords = _project_vectors_to_3d(vectors)
            for d, pos in zip(embedded_docs, coords, strict=False):
                topic = d.get("primary_topic")
                items.append(
                    {
                        "id": d["id"],
                        "pos": pos,
                        "color": _topic_to_color(topic),
                        "label": d.get("label") or d["id"],
                        "primary_topic": topic,
                    }
                )
        else:
            texts = [f"{d.get('label') or ''} {d.get('primary_topic') or ''}".strip() for d in docs]
            coords = _project_texts_to_3d(texts)
            for d, pos in zip(docs, coords, strict=False):
                topic = d.get("primary_topic")
                items.append(
                    {
                        "id": d["id"],
                        "pos": pos,
                        "color": _topic_to_color(topic),
                        "label": d.get("label") or d["id"],
                        "primary_topic": topic,
                    }
                )

        self._set_cached_semantic_map(cache_key, version=version, items=items)
        return items

    def _current_semantic_map_version(self) -> str:
        """Return a lightweight version string for semantic map cache invalidation."""

        with _session_scope(self.session) as s:
            ts = s.exec(select(func.max(DocumentRow.updated_at))).one()[0]
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            return ts.isoformat()
        return "none"

    def _fetch_docs_for_semantic_map(self, *, limit: int) -> list[dict[str, Any]]:
        with _session_scope(self.session) as s:
            stmt = (
                select(
                    DocumentRow.id,
                    DocumentRow.title,
                    DocumentRow.meta,
                    DocumentRow.topics,
                    DocumentRow.enrichment,
                    DocumentRow.embedding,
                )
                .order_by(DocumentRow.updated_at.desc())
                .limit(limit)
            )
            rows = s.exec(stmt).all()

        docs: list[dict[str, Any]] = []
        for row in rows:
            meta = row.meta or {}
            label = _best_effort_title(row_title=row.title, meta=meta)
            primary_topic = _best_effort_primary_topic(row.topics, meta)
            docs.append(
                {
                    "id": str(row.id),
                    "label": label,
                    "primary_topic": primary_topic,
                    "meta": meta,
                    "topics": row.topics or {},
                    "enrichment": row.enrichment or {},
                    "embedding": row.embedding,
                }
            )
        return docs

    def _get_cached_semantic_map(
        self,
        cache_key: str,
        *,
        version: str,
    ) -> list[dict[str, Any]] | None:
        if self.redis_client is not None:
            try:
                raw = self.redis_client.get(cache_key)
                if raw:
                    payload = json.loads(raw)
                    if payload.get("version") == version and isinstance(payload.get("items"), list):
                        return payload["items"]
            except Exception:
                logger.exception("Failed reading semantic map cache from Redis")

        with self.semantic_map_cache_lock:
            cached = self.semantic_map_cache.get(cache_key)
        if cached and cached.get("version") == version and isinstance(cached.get("items"), list):
            return cached["items"]
        return None

    def _set_cached_semantic_map(
        self, cache_key: str, *, version: str, items: list[dict[str, Any]]
    ) -> None:
        payload = {"version": version, "items": items}

        if self.redis_client is not None:
            try:
                self.redis_client.setex(
                    cache_key, self.semantic_map_cache_ttl_seconds, json.dumps(payload)
                )
            except Exception:
                logger.exception("Failed writing semantic map cache to Redis")

        with self.semantic_map_cache_lock:
            self.semantic_map_cache[cache_key] = payload

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
            stmt = (
                select(DocumentRow)
                .options(
                    load_only(
                        DocumentRow.id,
                        DocumentRow.title,
                        DocumentRow.source_url,
                        DocumentRow.canonical_url,
                        DocumentRow.topics,
                        DocumentRow.captured_at,
                        DocumentRow.tokens,
                        DocumentRow.summary,
                    )
                )
                .order_by(DocumentRow.captured_at.desc())
            )
            count_stmt = select(func.count()).select_from(DocumentRow)

            conditions = []
            if q:
                conditions.append(
                    DocumentRow.title.ilike(f"%{q}%") | DocumentRow.cleaned_text.ilike(f"%{q}%")
                )
            if topic:
                conditions.append(DocumentRow.topics["primary"].astext == topic)  # type: ignore[index]
            if (d := _parse_iso_date(date)) is not None:
                conditions.append(DocumentRow.day_bucket == d)
            if (dt := _parse_iso_datetime(start)) is not None:
                conditions.append(DocumentRow.captured_at >= dt)
            if (dt := _parse_iso_datetime(end)) is not None:
                conditions.append(DocumentRow.captured_at <= dt)

            for cond in conditions:
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

            stmt = _apply_offset_limit(stmt, skip=skip, limit=limit, max_limit=200)
            rows = s.exec(stmt).all()
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
            stmt = (
                select(DocChunkRow)
                .options(
                    load_only(
                        DocChunkRow.id,
                        DocChunkRow.doc_id,
                        DocChunkRow.idx,
                        DocChunkRow.section,
                        DocChunkRow.text,
                        DocChunkRow.captured_at,
                        DocChunkRow.day_bucket,
                    )
                )
                .order_by(DocChunkRow.captured_at.desc())
            )
            count_stmt = select(func.count()).select_from(DocChunkRow)

            uid = _parse_uuid(doc_id) if doc_id else None
            if doc_id and uid is None:
                raise BadRequestError("Invalid doc_id", code="invalid_id")

            conditions = []
            if uid is not None:
                conditions.append(DocChunkRow.doc_id == uid)
            if topic:
                conditions.append(DocChunkRow.topics["primary"].astext == topic)  # type: ignore[index]
            if (d := _parse_iso_date(date)) is not None:
                conditions.append(DocChunkRow.day_bucket == d)

            for cond in conditions:
                stmt = stmt.where(cond)
                count_stmt = count_stmt.where(cond)

            stmt = _apply_offset_limit(stmt, skip=skip, limit=limit, max_limit=200)
            rows = s.exec(stmt).all()
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
