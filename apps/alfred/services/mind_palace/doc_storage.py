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
from pydantic import BaseModel, Field, field_validator
from pymongo import TEXT
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from alfred.connectors.mongo_connector import MongoConnector


# -----------------
# Pydantic models
# -----------------
class NoteCreate(BaseModel):
    text: str
    source_url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("text")
    @classmethod
    def text_must_have_content(cls, value: str) -> str:
        trimmed = (value or "").strip()
        if not trimmed:
            raise ValueError("text must not be empty")
        return trimmed


class DocSummary(BaseModel):
    short: Optional[str] = None
    bullets: Optional[List[str]] = None
    key_points: Optional[List[str]] = None


class DocumentIngestChunk(BaseModel):
    idx: int
    text: str
    tokens: Optional[int] = None
    section: Optional[str] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    embedding: Optional[List[float]] = None

    @field_validator("idx")
    @classmethod
    def idx_nonneg(cls, v: int) -> int:
        if v < 0:
            raise ValueError("idx must be >= 0")
        return v

    @field_validator("text")
    @classmethod
    def chunk_text_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("chunk text must not be empty")
        return v


class DocumentIngest(BaseModel):
    source_url: str
    canonical_url: Optional[str] = None
    title: Optional[str] = None
    content_type: Optional[str] = None
    lang: Optional[str] = None
    raw_html: Optional[str] = None
    raw_markdown: Optional[str] = None
    cleaned_text: str
    tokens: Optional[int] = None
    hash: Optional[str] = None
    summary: Optional[DocSummary] = None
    topics: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    embedding: Optional[List[float]] = None
    captured_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    processed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    chunks: List[DocumentIngestChunk] = Field(default_factory=list)
    session_id: Optional[str] = None

    @field_validator("cleaned_text")
    @classmethod
    def cleaned_text_not_empty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("cleaned_text must not be empty")
        return v.strip()

    @field_validator("source_url")
    @classmethod
    def source_url_required(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("source_url required")
        return v


# -----------------
# Utilities
# -----------------
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


# -----------------
# Service
# -----------------
@dataclass
class DocStorageService:
    """Mongo-backed storage for notes/documents/chunks.

    Exposes methods that mirror the legacy backend's endpoints.
    """

    database: Database | None = None

    def __post_init__(self) -> None:
        if self.database is None:
            self._connector = MongoConnector()
            self.database = self._connector.database
        else:
            self._connector = None  # type: ignore[assignment]
        self._notes: Collection = self.database.get_collection("notes")
        self._documents: Collection = self.database.get_collection("documents")
        self._chunks: Collection = self.database.get_collection("doc_chunks")

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
        doc = {
            "text": note.text,
            "source_url": note.source_url,
            "metadata": note.metadata or {},
            "created_at": datetime.utcnow(),
        }
        res = self._notes.insert_one(doc)
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

        doc: Dict[str, Any] = {
            "source_url": payload.source_url,
            "canonical_url": canonical,
            "domain": domain,
            "title": payload.title,
            "content_type": payload.content_type or "web",
            "lang": payload.lang,
            "raw_html": payload.raw_html,
            "raw_markdown": payload.raw_markdown,
            "cleaned_text": cleaned_text,
            "tokens": tokens,
            "hash": content_hash,
            "summary": (payload.summary.model_dump() if payload.summary else None),
            "topics": payload.topics,
            "entities": None,
            "tags": payload.tags or [],
            "embedding": payload.embedding,
            "captured_at": captured_at,
            "captured_hour": captured_hour,
            "day_bucket": day_bucket,
            "published_at": payload.published_at,
            "processed_at": payload.processed_at or now,
            "created_at": now,
            "updated_at": now,
            "session_id": _maybe_object_id(payload.session_id),
            "agent_run_id": None,
            "metadata": payload.metadata or {},
        }

        duplicate = False
        try:
            res = self._documents.insert_one(doc)
            doc_id = res.inserted_id
        except DuplicateKeyError:
            duplicate = True
            existing = self._documents.find_one({"hash": content_hash}, {"_id": 1})
            if not existing:
                raise ValueError("Duplicate content but missing record")
            doc_id = existing["_id"]

        chunk_ids: List[str] = []
        if payload.chunks:
            chunk_docs: List[Dict[str, Any]] = []
            for ch in payload.chunks:
                ctokens = ch.tokens if ch.tokens is not None else _token_count(ch.text)
                chunk_docs.append(
                    {
                        "doc_id": doc_id,
                        "idx": ch.idx,
                        "text": ch.text,
                        "tokens": ctokens,
                        "section": ch.section,
                        "char_start": ch.char_start,
                        "char_end": ch.char_end,
                        "embedding": ch.embedding,
                        "topics": None,
                        "captured_at": captured_at,
                        "captured_hour": captured_hour,
                        "day_bucket": day_bucket,
                        "created_at": now,
                    }
                )
            if chunk_docs:
                r = self._chunks.insert_many(chunk_docs)
                chunk_ids = [str(i) for i in r.inserted_ids]

        return {
            "id": str(doc_id),
            "duplicate": duplicate,
            "chunk_count": len(chunk_ids),
            "chunk_ids": chunk_ids,
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
                    "summary": ((d.get("summary") or {}).get("short") if isinstance(d.get("summary"), dict) else None),
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
            text = (c.get("text") or "")
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

