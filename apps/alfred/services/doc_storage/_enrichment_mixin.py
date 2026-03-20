"""Mixin: Document enrichment, concept extraction, and title-image generation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import load_only

from alfred.core.exceptions import BadRequestError, NotFoundError
from alfred.core.utils import clamp_int
from alfred.models.doc_storage import DocumentRow
from alfred.schemas.enrichment import normalize_enrichment
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
    excerpt_for_cover_prompt as _excerpt_for_cover_prompt,
)
from alfred.services.doc_storage.utils import (
    first_str as _first_str,
)
from alfred.services.doc_storage.utils import (
    parse_uuid as _parse_uuid,
)
from alfred.services.doc_storage.utils import (
    sha256_hex as _sha256_hex,
)
from alfred.services.extraction_service import ExtractionService

from ._session import _session_scope


class EnrichmentMixin:
    """Enrichment, concept extraction, title-image generation — mixed into DocStorageService."""

    session: Any
    extraction_service: Any
    graph_service: Any

    def _ensure_extraction_service(self) -> Any: ...
    def _ensure_graph_service(self) -> Any: ...
    def _ensure_llm_service(self) -> Any: ...

    def enrich_document(self, doc_id: str, *, force: bool = False) -> dict[str, Any]:
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

            now = datetime.utcnow().replace(tzinfo=UTC)
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

            updates: dict[str, Any] = {
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

    def update_document_enrichment(self, doc_id: str, data: dict[str, Any]) -> None:
        """Bulk-update enrichment fields on a DocumentRow.

        Used by the pipeline persist node to write extraction/classification
        results back to the document.
        """
        uid = _parse_uuid(doc_id)
        if uid is None:
            return

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if doc is None:
                return

            for key, value in data.items():
                if hasattr(doc, key):
                    setattr(doc, key, value)

            doc.processed_at = datetime.now(UTC)
            s.add(doc)
            s.commit()

    def list_documents_needing_concepts_extraction(
        self,
        *,
        limit: int = 100,
        min_age_hours: int = 0,
        force: bool = False,
    ) -> list[DocumentRow]:
        """Return documents that are candidates for concept extraction."""

        now = datetime.utcnow().replace(tzinfo=UTC)
        from sqlmodel import select as sql_select

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
        """Return documents that are candidates for title/cover image generation."""

        limit = clamp_int(limit, lo=1, hi=500)
        now = datetime.utcnow().replace(tzinfo=UTC)

        from sqlmodel import select as sql_select

        stmt = sql_select(DocumentRow)
        if not force:
            stmt = stmt.where(DocumentRow.image.is_(None))
        if min_age_hours and min_age_hours > 0:
            cutoff = now - timedelta(hours=int(min_age_hours))
            stmt = stmt.where(DocumentRow.created_at <= cutoff)
        stmt = stmt.order_by(DocumentRow.created_at.desc()).limit(limit)

        with _session_scope(self.session) as s:
            return s.exec(stmt).all()

    def extract_document_concepts(self, doc_id: str, *, force: bool = False) -> dict[str, Any]:
        """Extract and persist a lightweight concept graph for a stored document."""

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

            now = datetime.utcnow().replace(tzinfo=UTC)
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
                    pass

            return {
                "id": doc_id,
                "skipped": False,
                "entities": len(payload["entities"]),
                "relations": len(payload["relations"]),
            }

    @staticmethod
    def build_document_title_image_prompt(self, doc_id: str) -> dict[str, Any]:
        """Build the OpenAI image prompt for a document cover image."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            raise ValueError("Invalid id")

        with _session_scope(self.session) as s:
            row = s.exec(
                select(
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
                raise ValueError("Document not found")

            meta, title_raw, topics, summary, domain, raw_markdown, cleaned_text = row
            meta = meta or {}
            title = _best_effort_title(row_title=title_raw, meta=meta)
            primary_topic = _best_effort_primary_topic(topics, meta)

            summary_short = None
            if isinstance(summary, dict):
                summary_short = _first_str(summary.get("short"), summary.get("summary"))

            source_text = (raw_markdown or cleaned_text or "").strip()
            excerpt = _excerpt_for_cover_prompt(source_text, max_chars=900)
            prompt = _build_title_image_prompt(
                title=title,
                summary=summary_short,
                primary_topic=primary_topic,
                domain=domain,
                excerpt=excerpt,
                visual_brief=None,
            )

            return {
                "id": doc_id,
                "title": title,
                "primary_topic": primary_topic,
                "summary_short": summary_short,
                "prompt": prompt,
            }

    def generate_document_title_image(
        self,
        doc_id: str,
        *,
        force: bool = False,
        model: str = "gpt-image-1",
        size: str = "1024x1024",
        quality: str = "high",
    ) -> dict[str, Any]:
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

            llm = self._ensure_llm_service()

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
                except Exception as exc:
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

            now = datetime.utcnow().replace(tzinfo=UTC)

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
