from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlparse

from bson import ObjectId

from alfred.services.mind_palace.enrichment import EnrichmentService
from alfred.services.mind_palace.extraction import ExtractionService
from alfred.services.mind_palace.models import PageInput, PageResult
from alfred.services.mongo import MongoService


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


COLLECTION = "mind_palace_documents"


def _serialize_id(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return None
    out = dict(doc)
    _id = out.pop("_id", None)
    if _id is not None:
        out["id"] = str(_id)
    return out


class MindPalaceService:
    """High-level service coordinating extraction, persistence, and enrichment."""

    def __init__(
        self,
        mongo: Optional[MongoService] = None,
        extractor: Optional[ExtractionService] = None,
        enricher: Optional[EnrichmentService] = None,
    ) -> None:
        self._mongo = (mongo or MongoService()).with_collection(COLLECTION)
        self._extractor = extractor or ExtractionService()
        self._enricher = enricher or EnrichmentService()

    def create_page(self, payload: PageInput, *, enrich: bool = False) -> PageResult:
        now = datetime.utcnow()
        word_count = self._extractor.compute_word_count(payload.raw_text)
        links = self._extractor.extract_hyperlinks(payload.html, payload.raw_text, payload.page_url)
        domain = _domain(payload.page_url)
        favicon = f"https://www.google.com/s2/favicons?sz=128&domain={domain}" if domain else None
        doc = {
            "user_id": payload.user_id,
            "source": {
                "url": payload.page_url,
                "title": payload.page_title,
                "favicon_url": favicon,
                "domain": domain,
                "captured_at": now,
                "selection_type": payload.selection_type,
                "source_type": "web_page",
            },
            "raw_text": payload.raw_text,
            "html": payload.html,
            "word_count": word_count,
            "hyperlinks": links,
            "topic_category": None,
            "summary": None,
            "highlights": [],
            "insights": [],
            "domain_summary": None,
            "tags": [],
            "topic_graph": {
                "primary_node": None,
                "related_nodes": [],
            },
            "status": "pending_enrichment",
            "error_message": None,
            "model_metadata": {
                "model_name": None,
                "prompt_version": "v1",
                "temperature": None,
                "enriched_at": None,
            },
            "created_at": now,
            "updated_at": now,
        }
        inserted_id = self._mongo.insert_one(doc)
        if enrich:
            ok = self.enrich_now(inserted_id)
            return PageResult(id=inserted_id, status="ready" if ok else "error")
        # Let caller schedule background enrichment
        return PageResult(id=inserted_id, status="pending_enrichment")

    def enrich_now(self, id: str) -> bool:
        """Run enrichment synchronously. Returns True on success."""
        # Load doc
        try:
            oid = ObjectId(id)
        except Exception:
            return False
        doc = self._mongo.find_one({"_id": oid})
        if not doc:
            return False
        self._mongo.update_one(
            {"_id": oid}, {"$set": {"status": "enriching", "updated_at": datetime.utcnow()}}
        )
        try:
            result = self._enricher.run(
                raw_text=doc.get("raw_text", ""),
                url=(doc.get("source") or {}).get("url"),
                title=(doc.get("source") or {}).get("title"),
            )
            now = datetime.utcnow()
            update = {
                "topic_category": result.topic_category,
                "summary": result.summary,
                "highlights": result.highlights,
                "insights": result.insights,
                "domain_summary": result.domain_summary,
                "tags": result.tags,
                "topic_graph": result.topic_graph or doc.get("topic_graph"),
                "status": "ready",
                "model_metadata": {
                    "model_name": result.model_name,
                    "prompt_version": result.prompt_version,
                    "temperature": result.temperature,
                    "enriched_at": now,
                },
                "updated_at": now,
            }
            self._mongo.update_one({"_id": oid}, {"$set": update})
            return True
        except Exception as exc:
            self._mongo.update_one(
                {"_id": oid},
                {
                    "$set": {
                        "status": "error",
                        "error_message": str(exc),
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            return False

    def get(self, id: str) -> dict[str, Any] | None:
        try:
            oid = ObjectId(id)
        except Exception:
            return None
        return _serialize_id(self._mongo.find_one({"_id": oid}))

    def search(
        self, *, q: str | None, topic: str | None, domain: str | None, limit: int = 20
    ) -> list[dict[str, Any]]:
        filter_: dict[str, Any] = {}
        if topic:
            filter_["$or"] = [
                {"topic_category": {"$regex": topic, "$options": "i"}},
                {"tags": topic},
                {"topic_graph.primary_node": {"$regex": topic, "$options": "i"}},
                {"topic_graph.related_nodes": topic},
            ]
        if domain:
            filter_["source.domain"] = {"$regex": f"^{domain}$", "$options": "i"}
        if q:
            filter_ = (
                {
                    "$and": [
                        filter_,
                        {
                            "$or": [
                                {"summary": {"$regex": q, "$options": "i"}},
                                {"raw_text": {"$regex": q, "$options": "i"}},
                                {"highlights.bullet": {"$regex": q, "$options": "i"}},
                                {"insights.statement": {"$regex": q, "$options": "i"}},
                            ]
                        },
                    ]
                }
                if filter_
                else {
                    "$or": [
                        {"summary": {"$regex": q, "$options": "i"}},
                        {"raw_text": {"$regex": q, "$options": "i"}},
                        {"highlights.bullet": {"$regex": q, "$options": "i"}},
                        {"insights.statement": {"$regex": q, "$options": "i"}},
                    ]
                }
            )
        rows = self._mongo.find_many(
            filter_, sort=[("created_at", -1)], limit=max(1, min(limit, 100))
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            sr = _serialize_id(r)
            if sr:
                out.append(sr)
        return out

    def ensure_indexes(self) -> None:
        try:
            coll = self._mongo._collection(None)  # type: ignore[attr-defined]
            coll.create_index([("created_at", -1)], name="created_desc")
            coll.create_index([("status", 1), ("created_at", -1)], name="status_created")
            coll.create_index([("source.domain", 1)], name="source_domain")
            try:
                coll.create_index(
                    [
                        ("summary", "text"),
                        ("raw_text", "text"),
                        ("highlights.bullet", "text"),
                        ("insights.statement", "text"),
                    ],
                    name="text_search",
                    default_language="english",
                )
            except Exception:
                pass
        except Exception:
            pass

    # Enrichment is handled by EnrichmentService; no private helpers here for clarity.


# No global singletons; prefer DI via FastAPI Depends or explicit construction.
