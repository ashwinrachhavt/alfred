"""Postgres-backed document and notes storage service.

This mirrors the Mongo DocStorageService API but persists to Postgres via SQLModel.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from cachetools import TTLCache
from sqlalchemy import and_, func, or_, select
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
from alfred.services.llm_service import LLMService

_CHUNKING_SERVICE = ChunkingService()
logger = logging.getLogger(__name__)


def _token_count(text: str) -> int:
    return len((text or "").split())


def _parse_uuid(value: str | None) -> uuid.UUID | None:
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return None


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _parse_iso_date(value: str | None) -> date | None:
    dt = _parse_iso_datetime(value)
    return dt.date() if dt else None


def _read_text_file_best_effort(path: str | None) -> str | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


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


def _first_str(*candidates: Any) -> str | None:
    for c in candidates:
        if isinstance(c, str):
            s = c.strip()
            if s:
                return s
    return None


def _best_effort_title(*, row_title: str | None, meta: dict[str, Any] | None) -> str:
    meta = meta or {}
    title = _first_str(
        meta.get("title"),
        meta.get("page_title"),
        meta.get("name"),
        row_title,
    )
    return title or "Untitled"


def _best_effort_cover_url(meta: dict[str, Any] | None) -> str | None:
    meta = meta or {}
    return _first_str(
        meta.get("image"),
        meta.get("image_url"),
        meta.get("cover"),
        meta.get("cover_image"),
        meta.get("thumbnail"),
        meta.get("thumbnail_url"),
    )


def _best_effort_primary_topic(
    topics: dict[str, Any] | None,
    meta: dict[str, Any] | None,
) -> str | None:
    topics = topics or {}
    meta = meta or {}

    primary = topics.get("primary")
    if isinstance(primary, str) and primary.strip():
        return primary.strip()

    cls = topics.get("classification")
    if isinstance(cls, dict):
        for key in ("primary_topic", "primary", "topic", "category"):
            val = cls.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()

    enrichment = meta.get("enrichment")
    if isinstance(enrichment, dict):
        topics2 = enrichment.get("topics")
        if isinstance(topics2, dict):
            val = topics2.get("primary")
            if isinstance(val, str) and val.strip():
                return val.strip()

    return None


def _build_title_image_prompt(
    *,
    title: str,
    summary: str | None,
    primary_topic: str | None,
    domain: str | None,
) -> str:
    """Build an image-generation prompt for a document cover.

    The goal is a timeless, clean cover image that works well in a library UI.
    """

    title = (title or "").strip() or "Untitled"
    summary = (summary or "").strip() or None
    primary_topic = (primary_topic or "").strip() or None
    domain = (domain or "").strip() or None

    context_parts: list[str] = []
    if primary_topic:
        context_parts.append(f"Primary topic: {primary_topic}.")
    if domain:
        context_parts.append(f"Source domain: {domain}.")
    if summary:
        context_parts.append(f"Summary: {summary}.")

    context = "\n".join(context_parts)
    if context:
        context = f"\n{context}\n"

    return (
        "Create a high-quality, modern editorial illustration to be used as a cover image for a saved article.\n"
        f"Article title: {title}\n"
        f"{context}"
        "Constraints:\n"
        "- Do not include any text, lettering, watermarks, logos, or UI.\n"
        "- Avoid clutter; keep the composition minimal and readable at small sizes.\n"
        "- Use a tasteful color palette and crisp shapes; slightly abstract is fine.\n"
        "Output: a single image.\n"
    )


def _hsl_to_hex(*, hue: float, saturation: float, lightness: float) -> str:
    """Convert HSL (0-360, 0-1, 0-1) to hex RGB string."""

    def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
        return max(lo, min(hi, float(v)))

    h = (float(hue) % 360.0) / 360.0
    s = _clamp(saturation)
    light = _clamp(lightness)

    def _hue_to_rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = light
    else:
        q = light * (1 + s) if light < 0.5 else light + s - light * s
        p = 2 * light - q
        r = _hue_to_rgb(p, q, h + 1 / 3)
        g = _hue_to_rgb(p, q, h)
        b = _hue_to_rgb(p, q, h - 1 / 3)

    return "#{:02x}{:02x}{:02x}".format(
        int(round(r * 255)),
        int(round(g * 255)),
        int(round(b * 255)),
    )


def _topic_to_color(topic: str | None) -> str:
    """Deterministically map a topic string to a restrained, stable color."""

    topic_norm = (topic or "unknown").strip().lower()
    digest = hashlib.sha1(topic_norm.encode("utf-8")).digest()
    hue = int.from_bytes(digest[:2], "big") % 360
    return _hsl_to_hex(hue=float(hue), saturation=0.62, lightness=0.52)


def _extract_embedding(row_embedding: Any, row_enrichment: Any) -> list[float] | None:
    """Best-effort extraction of a float embedding from known shapes."""

    if isinstance(row_embedding, list) and row_embedding:
        try:
            return [float(x) for x in row_embedding]
        except Exception:
            return None

    if isinstance(row_enrichment, dict):
        emb = row_enrichment.get("embedding")
        if isinstance(emb, list) and emb:
            try:
                return [float(x) for x in emb]
            except Exception:
                return None

    return None


def _project_vectors_to_3d(vectors: list[list[float]]) -> list[list[float]]:
    """Reduce high-dimensional vectors to 3D coordinates."""

    if not vectors:
        return []

    if len(vectors) == 1:
        return [[0.0, 0.0, 0.0]]
    if len(vectors) == 2:
        return [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]

    import numpy as np
    from sklearn.decomposition import PCA

    dim = len(vectors[0])
    same_dim = [v for v in vectors if isinstance(v, list) and len(v) == dim]
    if len(same_dim) < 3:
        return [[0.0, 0.0, 0.0] for _ in vectors]

    mat = np.asarray(same_dim, dtype=np.float32)
    if mat.ndim != 2 or mat.shape[0] < 3:
        return [[0.0, 0.0, 0.0] for _ in vectors]

    mat = np.where(np.isfinite(mat), mat, 0.0).astype(np.float32, copy=False)

    pca = PCA(n_components=3)
    coords = pca.fit_transform(mat)
    coords = coords - np.mean(coords, axis=0, keepdims=True)

    norms = np.linalg.norm(coords, axis=1)
    max_norm = float(np.max(norms)) if coords.shape[0] else 1.0
    if max_norm > 0:
        coords = coords / max_norm

    return [[float(row[0]), float(row[1]), float(row[2])] for row in coords]


def _project_texts_to_3d(texts: list[str]) -> list[list[float]]:
    """Project a list of text snippets into 3D space (no embeddings required)."""

    if not texts:
        return []
    if len(texts) == 1:
        return [[0.0, 0.0, 0.0]]
    if len(texts) == 2:
        return [[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]

    import numpy as np
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer(max_features=2048, stop_words="english")
    mat = vectorizer.fit_transform([t or "" for t in texts])
    if mat.shape[0] < 3 or mat.shape[1] < 2:
        return [[0.0, 0.0, 0.0] for _ in texts]

    max_components = min(3, mat.shape[0] - 1, mat.shape[1] - 1)
    if max_components < 1:
        return [[0.0, 0.0, 0.0] for _ in texts]

    svd = TruncatedSVD(n_components=max_components, random_state=42)
    coords = svd.fit_transform(mat)
    coords = coords - np.mean(coords, axis=0, keepdims=True)

    norms = np.linalg.norm(coords, axis=1)
    max_norm = float(np.max(norms)) if coords.shape[0] else 1.0
    if max_norm > 0:
        coords = coords / max_norm

    if coords.shape[1] < 3:
        pad = np.zeros((coords.shape[0], 3 - coords.shape[1]), dtype=coords.dtype)
        coords = np.concatenate([coords, pad], axis=1)

    return [[float(row[0]), float(row[1]), float(row[2])] for row in coords]


def _encode_cursor(*, created_at: datetime, doc_id: str) -> str:
    payload = {"created_at": created_at.isoformat(), "id": doc_id}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    if not cursor:
        raise ValueError("cursor must not be empty")

    padded = cursor + "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(padded.encode("utf-8"))
        payload = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid cursor") from exc

    if not isinstance(payload, dict):
        raise ValueError("Invalid cursor")

    created_at_raw = payload.get("created_at")
    doc_id = payload.get("id")
    if not isinstance(created_at_raw, str) or not isinstance(doc_id, str):
        raise ValueError("Invalid cursor")

    try:
        created_at = datetime.fromisoformat(created_at_raw)
    except Exception as exc:
        raise ValueError("Invalid cursor") from exc
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return created_at, doc_id


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
        self.extraction_service = ExtractionService()
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
        uid = _parse_uuid(note_id)
        if uid is None:
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
        uid = _parse_uuid(note_id)
        if uid is None:
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
        uid = _parse_uuid(doc_id)
        if uid is None:
            raise ValueError("Invalid id")

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                raise ValueError("Document not found")

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
        uid = _parse_uuid(doc_id)
        if uid is None:
            return None
        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                return None
            return doc.raw_markdown or doc.cleaned_text or ""

    def get_document(self, doc_id: str) -> Dict[str, Any] | None:
        uid = _parse_uuid(doc_id)
        if uid is None:
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

    def get_document_details(self, doc_id: str) -> Dict[str, Any] | None:
        """Return the full persisted document payload for deep inspection views."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            return None

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
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

    def get_document_image_bytes(self, doc_id: str) -> bytes | None:
        """Return the stored document cover image bytes, if present."""

        uid = _parse_uuid(doc_id)
        if uid is None:
            return None

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
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
            raise ValueError("Invalid id")

        with _session_scope(self.session) as s:
            doc = s.get(DocumentRow, uid)
            if not doc:
                raise ValueError("Document not found")

            if (not force) and doc.image:
                return {"id": doc_id, "skipped": True, "reason": "image_already_present"}

            meta = doc.meta or {}
            title = _best_effort_title(row_title=doc.title, meta=meta)
            primary_topic = _best_effort_primary_topic(doc.topics, meta)

            summary_short = None
            if isinstance(doc.summary, dict):
                summary_short = _first_str(doc.summary.get("short"), doc.summary.get("summary"))

            prompt = _build_title_image_prompt(
                title=title,
                summary=summary_short,
                primary_topic=primary_topic,
                domain=doc.domain,
            )

            llm = self._ensure_llm_service()
            image_bytes, revised_prompt = llm.generate_image_png(
                prompt=prompt,
                model=model,
                size=size,
                quality=quality,
            )

            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            doc.image = image_bytes
            doc.updated_at = now

            generated_meta = {
                "model": model,
                "size": size,
                "quality": quality,
                "prompt": prompt,
                "revised_prompt": revised_prompt,
                "generated_at": now.isoformat(),
            }
            doc.meta = {**meta, "generated_cover_image": generated_meta}

            s.add(doc)
            s.commit()

            return {
                "id": doc_id,
                "skipped": False,
                "model": model,
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
                raise ValueError("Invalid cursor")

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

        if len(vectors) >= 3:
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
            stmt = select(DocumentRow).order_by(DocumentRow.captured_at.desc())
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
            stmt = select(DocChunkRow).order_by(DocChunkRow.captured_at.desc())
            count_stmt = select(func.count()).select_from(DocChunkRow)

            uid = _parse_uuid(doc_id) if doc_id else None
            if doc_id and uid is None:
                raise ValueError("Invalid doc_id")

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
