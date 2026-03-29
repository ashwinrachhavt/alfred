"""Mixin: Document ingestion (create, store-only, and full pipeline)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import load_only
from sqlmodel import select

from alfred.core.exceptions import BadRequestError, NotFoundError
from alfred.core.settings import settings
from alfred.models.doc_storage import DocChunkRow, DocumentRow
from alfred.schemas.documents import DocumentIngest
from alfred.schemas.enrichment import normalize_enrichment
from alfred.services.doc_storage.utils import (
    domain_from_url as _domain_from_url,
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

from ._chunking_helpers import _build_doc_chunk_rows, _chunk_payloads_for_text
from ._session import _session_scope


class IngestionMixin:
    """Document ingestion — mixed into DocStorageService."""

    session: Any
    extraction_service: Any
    graph_service: Any

    # These are implemented on the host dataclass; declared here for type-checking.
    def _ensure_extraction_service(self) -> Any: ...
    def _ensure_graph_service(self) -> Any: ...
    def _ensure_llm_service(self) -> Any: ...

    def ingest_document(self, payload: DocumentIngest) -> dict[str, Any]:
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

    def ingest_document_basic(self, payload: DocumentIngest) -> dict[str, Any]:
        return self._ingest_document(
            payload, do_enrichment=False, do_classification=False, do_graph=False
        )

    def ingest_document_store_only(self, payload: DocumentIngest) -> dict[str, Any]:
        """Persist a document quickly without chunking or enrichment.

        This is intended for latency-sensitive ingestion paths (e.g., browser extension
        page saves) where chunking/enrichment can be performed asynchronously.
        """
        now = datetime.utcnow().replace(tzinfo=UTC)
        captured_at = payload.captured_at or now
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        day_bucket = _start_of_day_utc(captured_at)
        captured_hour = captured_at.astimezone(UTC).hour

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
            processed_at=None,
            created_at=now,
            updated_at=now,
            session_id=payload.session_id,
            agent_run_id=None,
            meta=payload.metadata or {},
            enrichment=enrichment_block,
            pipeline_status="pending",
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
            doc_id = str(doc_record.id)

        # Fire document pipeline (non-blocking)
        try:
            from alfred.tasks.document_pipeline import run_document_pipeline

            run_document_pipeline.delay(
                doc_id=doc_id,
                user_id=(payload.metadata or {}).get("user_id", ""),
            )
        except Exception:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to enqueue pipeline task for %s",
                doc_id,
                exc_info=True,
            )

        return {
            "id": doc_id,
            "duplicate": False,
        }

    def _ingest_document(
        self,
        payload: DocumentIngest,
        *,
        do_enrichment: bool,
        do_classification: bool,
        do_graph: bool,
    ) -> dict[str, Any]:
        now = datetime.utcnow().replace(tzinfo=UTC)
        captured_at = payload.captured_at or now
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        day_bucket = _start_of_day_utc(captured_at)
        captured_hour = captured_at.astimezone(UTC).hour

        cleaned_text = payload.cleaned_text
        content_hash = payload.hash or _sha256_hex(cleaned_text)
        tokens = payload.tokens if payload.tokens is not None else _token_count(cleaned_text)
        canonical = payload.canonical_url or payload.source_url
        domain = _domain_from_url(canonical)

        summary_obj: dict[str, Any] | None = None
        topics_obj: dict[str, Any] | None = None
        embedding_vec: list[float] | None = None
        entities_obj: dict[str, Any] | None = None

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

            chunk_ids: list[str] = []
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

    def process_document(self, doc_id: str, *, force: bool = False) -> dict[str, Any]:
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
                            else doc.captured_at.astimezone(UTC).hour
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

                now = datetime.utcnow().replace(tzinfo=UTC)
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
