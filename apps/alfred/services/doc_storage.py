"""Document and notes storage service (Mongo-backed).

Ports the core storage, indexing, and query logic from the legacy
notetaker backend into an internal service that can be consumed by
FastAPI routes. No AI/crawl features; strictly storage + filters.

Collections:
- notes
- documents
- doc_chunks

Typical usage (from an API route):
    svc = DocStorageService()
    svc.ensure_indexes()  # idempotent
    note_id = svc.create_note(NoteCreate(text="hello"))

This module deliberately avoids route concerns (validation errors ->
HTTP codes). API layers can translate exceptions to HTTP errors.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bson import ObjectId
from pymongo import TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from alfred.connectors.mongo_connector import MongoConnector
from alfred.core.settings import settings
from alfred.schemas.documents import (
    DocChunkRecord,
    DocumentIngest,
    DocumentRecord,
    NoteCreate,
    NoteRecord,
)
from alfred.schemas.enrichment import normalize_enrichment
from alfred.services.chunking import ChunkingService
from alfred.services.extraction_service import ExtractionService
from alfred.services.graph_service import GraphService


def _maybe_object_id(val: Optional[str]) -> Optional[ObjectId]:
    if not val:
        return None
    try:
        return ObjectId(val) if ObjectId.is_valid(val) else None
    except Exception:
        return None


def _token_count(text: str) -> int:
    try:
        return len((text or "").split())
    except Exception:
        return 0


def _sha256_hex(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _start_of_day_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


_CHUNKING_SERVICE = ChunkingService()


# -----------------
# Service
# -----------------
@dataclass
class DocStorageService:
    """Mongo-backed storage for notes/documents/chunks.

    Exposes methods that mirror the legacy backend's endpoints.
    """

    database: Database | None = None
    graph_service: Any | None = None
    extraction_service: Any | None = None

    def __post_init__(self) -> None:
        if self.database is None:
            self._connector = MongoConnector()
            self.database = self._connector.database
        else:
            self._connector = None  # type: ignore[assignment]
        self._notes: Collection = self.database.get_collection("notes")
        self._documents: Collection = self.database.get_collection("documents")
        self._chunks: Collection = self.database.get_collection("doc_chunks")

        # Optional collaborators (Graph/Extraction)
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
        if self.extraction_service is None:
            self.extraction_service = ExtractionService()

    # --------------- Health ---------------
    def ping(self) -> bool:
        if self._connector is not None:
            return self._connector.ping()
        # If injected DB, attempt a simple command
        try:
            self.database.client.admin.command("ping")  # type: ignore[attr-defined]
            return True
        except Exception as exc:  # pragma: no cover - network
            raise RuntimeError("MongoDB not reachable") from exc

    # --------------- Indexes ---------------
    def ensure_indexes(self) -> None:
        try:
            # documents
            self._documents.create_index([("hash", 1)], unique=True, name="uniq_hash")
            self._documents.create_index([("captured_at", -1)], name="captured_desc")
            self._documents.create_index([("day_bucket", -1)], name="day_bucket")
            self._documents.create_index([("captured_hour", 1)], name="captured_hour")
            self._documents.create_index(
                [("topics.primary", 1), ("captured_at", -1)], name="topic_time"
            )
            self._documents.create_index([("source_url", 1)], name="source_url")
            self._documents.create_index([("canonical_url", 1)], name="canonical_url")
            try:
                self._documents.create_index(
                    [("cleaned_text", TEXT), ("title", TEXT)], name="text_index"
                )
            except Exception:
                # Text index may fail in older Mongo versions or on Atlas free tier
                pass

            # doc_chunks
            self._chunks.create_index([("doc_id", 1), ("idx", 1)], name="doc_idx")
            self._chunks.create_index([("captured_at", -1)], name="chunk_time")
            self._chunks.create_index([("day_bucket", -1)], name="chunk_day")
            self._chunks.create_index([("topics.primary", 1)], name="chunk_topic")
        except Exception:
            # Index creation is best-effort
            pass

    # --------------- Notes ---------------
    def create_note(self, note: NoteCreate) -> str:
        record = NoteRecord(
            text=note.text,
            source_url=note.source_url,
            metadata=note.metadata or {},
            created_at=datetime.utcnow(),
        )
        res = self._notes.insert_one(record.model_dump())
        return str(res.inserted_id)

    def list_notes(self, *, q: Optional[str], skip: int, limit: int) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if q:
            query["text"] = {"$regex": q, "$options": "i"}
        cursor = (
            self._notes.find(query)
            .sort("created_at", -1)
            .skip(int(max(0, skip)))
            .limit(int(max(1, min(limit, 200))))
        )
        items = [self._serialize_note(doc) for doc in cursor]
        total = self._notes.count_documents(query)
        return {"items": items, "total": total, "skip": skip, "limit": limit}

    def get_note(self, note_id: str) -> Dict[str, Any] | None:
        if not ObjectId.is_valid(note_id):
            return None
        doc = self._notes.find_one({"_id": ObjectId(note_id)})
        return self._serialize_note(doc) if doc else None

    def delete_note(self, note_id: str) -> bool:
        if not ObjectId.is_valid(note_id):
            return False
        res = self._notes.delete_one({"_id": ObjectId(note_id)})
        return res.deleted_count > 0

    @staticmethod
    def _serialize_note(doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": str(doc.get("_id")),
            "text": doc.get("text", ""),
            "source_url": doc.get("source_url"),
            "metadata": doc.get("metadata") or {},
            "created_at": doc.get("created_at"),
        }

    # --------------- Documents ---------------
    def ingest_document(self, payload: DocumentIngest) -> Dict[str, Any]:
        now = datetime.utcnow().replace(tzinfo=timezone.utc)
        captured_at = payload.captured_at or now
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=timezone.utc)
        day_bucket = _start_of_day_utc(captured_at)
        captured_hour = captured_at.hour

        cleaned_text = payload.cleaned_text
        content_hash = payload.hash or _sha256_hex(cleaned_text)
        tokens = payload.tokens if payload.tokens is not None else _token_count(cleaned_text)
        canonical = payload.canonical_url or payload.source_url
        domain = _domain_from_url(canonical)

        # Enrichment via ExtractionService (OpenAI-backed): best-effort pre-persist
        summary_obj: Optional[Dict[str, Any]] = None
        topics_obj: Optional[Dict[str, Any]] = None
        embedding_vec: Optional[List[float]] = None
        entities_obj: Optional[Dict[str, Any]] = None

        if settings.enable_ingest_enrichment and self.extraction_service:
            try:
                enrich = self.extraction_service.extract_all(
                    cleaned_text=cleaned_text,
                    raw_markdown=payload.raw_markdown,
                    metadata=payload.metadata or {},
                )
                # Map lang
                if not payload.lang and enrich.get("lang"):
                    payload.lang = enrich.get("lang")
                # Map summary
                if enrich.get("summary"):
                    s = enrich["summary"] or {}
                    short = s.get("short") or ""
                    long = s.get("long") or None
                    summary_obj = {"short": short, "long": long} if (short or long) else None
                # Map topics/tags
                if enrich.get("topics") and not payload.topics:
                    topics_obj = enrich.get("topics")
                if enrich.get("tags") and not payload.tags:
                    payload.tags = enrich.get("tags")
                # Embedding
                if enrich.get("embedding") is not None and not payload.embedding:
                    embedding_vec = enrich.get("embedding")
                # Entities (store under a simple shape if present)
                ents = enrich.get("entities") or []
                if ents:
                    entities_obj = {"items": ents}
                # Attach enrichment block into metadata for normalization downstream
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

        # Optional taxonomy classification (best-effort)
        if settings.enable_ingest_classification and self.extraction_service:
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
                    text=payload.raw_markdown or cleaned_text, taxonomy_context=taxonomy_ctx
                )
                if cls:
                    if topics_obj is None:
                        topics_obj = payload.topics or {}
                        if not isinstance(topics_obj, dict):
                            topics_obj = {}
                    # attach under topics.classification
                    topics_obj = dict(topics_obj or {})
                    topics_obj["classification"] = cls
            except Exception:
                pass

        # Optional enrichment block (normalized if present)
        enrichment_block = None
        try:
            if (payload.metadata or {}).get("enrichment"):
                enrichment_block = normalize_enrichment(
                    payload.metadata.get("enrichment")
                ).model_dump()
        except Exception:
            enrichment_block = None

        record = DocumentRecord(
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
            summary=(
                summary_obj
                if summary_obj is not None
                else (payload.summary.model_dump() if payload.summary else None)
            ),
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
            session_id=_maybe_object_id(payload.session_id),
            agent_run_id=None,
            metadata=payload.metadata or {},
            enrichment=enrichment_block,
        )

        duplicate = False
        try:
            res = self._documents.insert_one(record.model_dump())
            doc_id = res.inserted_id
        except DuplicateKeyError:
            duplicate = True
            existing = self._documents.find_one({"hash": content_hash}, {"_id": 1})
            if not existing:
                raise ValueError("Duplicate content but missing record")
            doc_id = existing["_id"]

        chunk_ids: List[str] = []
        try:
            chunk_payloads = payload.chunks
            if (not chunk_payloads) and (cleaned_text or (payload.raw_markdown or "").strip()):
                # Prefer markdown source if provided to enable header-aware chunking
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
                chunk_docs: List[Dict[str, Any]] = []
                for ch in chunk_payloads:
                    ctokens = ch.tokens if ch.tokens is not None else _token_count(ch.text)
                    chunk_record = DocChunkRecord(
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
                        created_at=now,
                    )
                    chunk_docs.append(chunk_record.model_dump())
                if chunk_docs:
                    r = self._chunks.insert_many(chunk_docs)
                    chunk_ids = [str(i) for i in r.inserted_ids]
        except Exception:
            # Non-fatal: proceed without chunks
            chunk_ids = []

        # Optional: content graph extraction and topic hinting (best-effort)
        # Decoupled from Neo4j so topics.extracted can be written even without a graph backend.
        try:
            if self.extraction_service:
                full_text = payload.raw_markdown or cleaned_text
                extraction = self.extraction_service.extract_graph(
                    text=full_text,
                    metadata=payload.metadata or {},
                )
                entities = extraction.get("entities") or []
                relations = extraction.get("relations") or []
                topics_from_extraction = extraction.get("topics") or []
                doc_id_str = str(doc_id)

                # Write topics.extracted regardless of graph availability
                if topics_from_extraction:
                    self._documents.update_one(
                        {"_id": doc_id},
                        {"$set": {"topics.extracted": topics_from_extraction}},
                    )

                # If a graph service is configured, upsert nodes/edges
                if self.graph_service:
                    self.graph_service.upsert_document_node(
                        doc_id=doc_id_str,
                        title=payload.title,
                        source_url=payload.source_url,
                    )
                    for ent in entities:
                        name = ent.get("name")
                        etype = ent.get("type") or ent.get("type_")
                        if not name:
                            continue
                        self.graph_service.upsert_entity(name=name, type_=etype)
                        self.graph_service.link_doc_to_entity(doc_id=doc_id_str, name=name)
                    for rel in relations:
                        f = rel.get("from")
                        t = rel.get("to")
                        r = rel.get("type") or "RELATED_TO"
                        if f and t:
                            self.graph_service.link_entities(from_name=f, to_name=t, rel_type=r)
        except Exception:
            pass

        return {
            "id": str(doc_id),
            "duplicate": duplicate,
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
        }

    # --------------- Helpers ---------------
    def get_document_text(self, doc_id: str) -> Optional[str]:
        if not ObjectId.is_valid(doc_id):
            return None
        doc = self._documents.find_one({"_id": ObjectId(doc_id)})
        if not doc:
            return None
        return doc.get("raw_markdown") or doc.get("cleaned_text") or ""

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
        filt: Dict[str, Any] = {}
        if q:
            filt["$or"] = [
                {"title": {"$regex": q, "$options": "i"}},
                {"cleaned_text": {"$regex": q, "$options": "i"}},
            ]
        if topic:
            filt["topics.primary"] = topic
        if date:
            try:
                d = datetime.fromisoformat(date)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                filt["day_bucket"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            except Exception:
                pass
        if start or end:
            rng: Dict[str, Any] = {}
            if start:
                try:
                    rng["$gte"] = datetime.fromisoformat(start)
                except Exception:
                    pass
            if end:
                try:
                    rng["$lte"] = datetime.fromisoformat(end)
                except Exception:
                    pass
            if rng:
                filt["captured_at"] = rng

        cursor = (
            self._documents.find(
                filt,
                {
                    "cleaned_text": 0,
                    # raw_html was removed from storage; keep excluded if present in legacy data
                    "raw_html": 0,
                    "raw_markdown": 0,
                    "embedding": 0,
                    "entities": 0,
                },
            )
            .sort("captured_at", -1)
            .skip(int(max(0, skip)))
            .limit(int(max(1, min(limit, 200))))
        )
        items = []
        for d in cursor:
            items.append(
                {
                    "id": str(d.get("_id")),
                    "title": d.get("title"),
                    "source_url": d.get("source_url"),
                    "canonical_url": d.get("canonical_url"),
                    "topics": d.get("topics"),
                    "captured_at": d.get("captured_at"),
                    "tokens": d.get("tokens"),
                    "summary": (
                        (d.get("summary") or {}).get("short")
                        if isinstance(d.get("summary"), dict)
                        else None
                    ),
                }
            )
        total = self._documents.count_documents(filt)
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
        filt: Dict[str, Any] = {}
        if doc_id:
            if not ObjectId.is_valid(doc_id):
                raise ValueError("Invalid doc_id")
            filt["doc_id"] = ObjectId(doc_id)
        if topic:
            filt["topics.primary"] = topic
        if date:
            try:
                d = datetime.fromisoformat(date)
                if d.tzinfo is None:
                    d = d.replace(tzinfo=timezone.utc)
                filt["day_bucket"] = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            except Exception:
                pass
        cursor = (
            self._chunks.find(filt, {"embedding": 0})
            .sort("captured_at", -1)
            .skip(int(max(0, skip)))
            .limit(int(max(1, min(limit, 200))))
        )
        items = []
        for c in cursor:
            text = c.get("text") or ""
            preview = text[:260]
            items.append(
                {
                    "id": str(c.get("_id")),
                    "doc_id": str(c.get("doc_id")),
                    "idx": c.get("idx"),
                    "section": c.get("section"),
                    "text": preview,
                    "captured_at": c.get("captured_at"),
                }
            )
        total = self._chunks.count_documents(filt)
        return {"items": items, "total": total, "skip": skip, "limit": limit}
