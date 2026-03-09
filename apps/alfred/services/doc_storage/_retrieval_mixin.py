"""Mixin: Document retrieval, listing, and text updates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import load_only

from alfred.core.exceptions import BadRequestError
from alfred.models.doc_storage import DocChunkRow, DocumentRow
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
    decode_cursor as _decode_cursor,
)
from alfred.services.doc_storage.utils import (
    encode_cursor as _encode_cursor,
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
    token_count as _token_count,
)

from ._session import _session_scope


class RetrievalMixin:
    """Document retrieval and listing — mixed into DocStorageService."""

    session: Any

    def get_document_text(self, doc_id: str) -> str | None:
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

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
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

    def get_document_details(self, doc_id: str) -> dict[str, Any] | None:
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
    ) -> dict[str, Any] | None:
        """Update a document's editable text payload."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            raise BadRequestError("Invalid id", code="invalid_id")

        now = datetime.now(UTC)

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

    # --------------- Explorer (Atheneum) ---------------
    def list_explorer_documents(
        self,
        *,
        limit: int,
        cursor: str | None = None,
        filter_topic: str | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
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
            title_val = _best_effort_title(row_title=doc.title, meta=meta)
            primary_topic = _best_effort_primary_topic(doc.topics, meta)

            summary_short = None
            if isinstance(doc.summary, dict):
                summary_short = _first_str(doc.summary.get("short"), doc.summary.get("summary"))

            items.append(
                {
                    "id": str(doc.id),
                    "title": title_val,
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

    def list_documents(
        self,
        *,
        q: str | None = None,
        topic: str | None = None,
        date: str | None = None,
        start: str | None = None,
        end: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
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
        doc_id: str | None = None,
        topic: str | None = None,
        date: str | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
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
