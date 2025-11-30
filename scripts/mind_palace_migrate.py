"""Mind Palace and Doc Storage migration utilities.

Usage:
    python -m scripts.mind_palace_migrate --dry-run
    python -m scripts.mind_palace_migrate --limit 100

Flags:
    --dry-run       Do not write changes; print a summary instead
    --limit N       Limit number of documents to examine per collection (default: no limit)

Notes:
    - Idempotent: It is safe to run multiple times.
    - Aligns Mongo records with canonical Pydantic models defined in
      `apps/alfred/schemas/documents.py` (re-exported from `alfred/schemas/mind_palace.py`).
    - Handles legacy fields like `raw_html` by unsetting them.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from alfred.connectors.mongo_connector import MongoConnector
from alfred.schemas.documents import (
    DocChunkRecord,
    DocumentRecord,
    MindPalaceDocumentRecord,
    NoteRecord,
)
from pymongo.collection import Collection

logger = logging.getLogger("mind_palace_migrate")


def _start_of_day_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return datetime(dt.year, dt.month, dt.day, tzinfo=timezone.utc)


def _domain_from_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return urlparse(url).netloc or None
    except Exception:
        return None


def _set_if_missing(doc: Dict[str, Any], field: str, value: Any) -> Tuple[bool, Any]:
    if field not in doc or doc.get(field) is None:
        return True, value
    return False, doc[field]


def migrate_documents(col: Collection, *, dry_run: bool, limit: int | None = None) -> int:
    cursor = col.find({}, limit=limit or 0)
    updated = 0
    for d in cursor:
        updates: Dict[str, Any] = {}
        dt_now = datetime.utcnow().replace(tzinfo=timezone.utc)

        # canonical_url
        changed, canonical = _set_if_missing(d, "canonical_url", d.get("source_url"))
        if changed:
            updates["canonical_url"] = canonical

        # domain
        changed, domain = _set_if_missing(d, "domain", _domain_from_url(canonical))
        if changed:
            updates["domain"] = domain

        # captured_at
        cap: datetime | None = d.get("captured_at")
        if cap is None:
            updates["captured_at"] = dt_now
            cap = dt_now
        elif cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
            updates["captured_at"] = cap

        # captured_hour, day_bucket
        if cap is not None:
            if d.get("captured_hour") is None:
                updates["captured_hour"] = cap.hour
            if d.get("day_bucket") is None:
                updates["day_bucket"] = _start_of_day_utc(cap)

        # processed_at/created_at/updated_at
        for ts in ("processed_at", "created_at", "updated_at"):
            if d.get(ts) is None:
                updates[ts] = dt_now

        # Remove legacy raw_html if present
        unset: Dict[str, int] = {}
        if "raw_html" in d:
            unset["raw_html"] = 1

        if updates or unset:
            updated += 1
            if dry_run:
                logger.info(
                    "documents %s would update: set=%s unset=%s",
                    d.get("_id"),
                    list(updates.keys()),
                    list(unset.keys()),
                )
            else:
                ops: Dict[str, Any] = {}
                if updates:
                    ops["$set"] = updates
                if unset:
                    ops["$unset"] = unset
                col.update_one({"_id": d["_id"]}, ops)
        # Validate shape (best-effort)
        try:
            DocumentRecord.model_validate({**d, **updates})
        except Exception as exc:
            logger.warning("documents %s validation failed: %s", d.get("_id"), exc)

    return updated


def migrate_doc_chunks(col: Collection, *, dry_run: bool, limit: int | None = None) -> int:
    cursor = col.find({}, limit=limit or 0)
    updated = 0
    dt_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    for d in cursor:
        updates: Dict[str, Any] = {}

        cap: datetime | None = d.get("captured_at")
        if cap is None:
            updates["captured_at"] = dt_now
            cap = dt_now
        elif cap.tzinfo is None:
            cap = cap.replace(tzinfo=timezone.utc)
            updates["captured_at"] = cap

        if cap is not None:
            if d.get("captured_hour") is None:
                updates["captured_hour"] = cap.hour
            if d.get("day_bucket") is None:
                updates["day_bucket"] = _start_of_day_utc(cap)

        if d.get("created_at") is None:
            updates["created_at"] = dt_now

        if updates:
            updated += 1
            if dry_run:
                logger.info("doc_chunks %s would update: %s", d.get("_id"), list(updates.keys()))
            else:
                col.update_one({"_id": d["_id"]}, {"$set": updates})

        try:
            DocChunkRecord.model_validate({**d, **updates})
        except Exception as exc:
            logger.warning("doc_chunks %s validation failed: %s", d.get("_id"), exc)

    return updated


def migrate_notes(col: Collection, *, dry_run: bool, limit: int | None = None) -> int:
    cursor = col.find({}, limit=limit or 0)
    updated = 0
    for d in cursor:
        if d.get("created_at") is None:
            updated += 1
            if dry_run:
                logger.info("notes %s would set created_at", d.get("_id"))
            else:
                col.update_one({"_id": d["_id"]}, {"$set": {"created_at": datetime.utcnow()}})
        try:
            NoteRecord.model_validate(d)
        except Exception as exc:
            logger.warning("notes %s validation failed: %s", d.get("_id"), exc)
    return updated


def migrate_mind_palace(col: Collection, *, dry_run: bool, limit: int | None = None) -> int:
    """Normalize proposed mind_palace_documents shape if collection exists.

    Since writes are not present today, this function simply validates and
    ensures timestamps exist for any existing documents.
    """
    try:
        cursor = col.find({}, limit=limit or 0)
    except Exception:
        # Collection may not exist yet.
        logger.info("mind_palace_documents collection not found; skipping")
        return 0

    updated = 0
    dt_now = datetime.utcnow().replace(tzinfo=timezone.utc)
    for d in cursor:
        updates: Dict[str, Any] = {}
        if d.get("created_at") is None:
            updates["created_at"] = dt_now
        if d.get("updated_at") is None:
            updates["updated_at"] = dt_now
        if d.get("chunk_ids") is None:
            updates["chunk_ids"] = []
        if d.get("tags") is None:
            updates["tags"] = []
        if d.get("metadata") is None:
            updates["metadata"] = {}

        if updates:
            updated += 1
            if dry_run:
                logger.info(
                    "mind_palace_documents %s would update: %s", d.get("_id"), list(updates.keys())
                )
            else:
                col.update_one({"_id": d["_id"]}, {"$set": updates})

        try:
            MindPalaceDocumentRecord.model_validate({**d, **updates})
        except Exception as exc:
            logger.warning("mind_palace_documents %s validation failed: %s", d.get("_id"), exc)
    return updated


def main() -> None:
    parser = argparse.ArgumentParser(description="Mind Palace migration")
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    parser.add_argument("--limit", type=int, default=None, help="Limit records per collection")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger.info("Starting migration (dry-run=%s, limit=%s)", args.dry_run, args.limit)

    with MongoConnector() as conn:
        db = conn.database
        documents = db.get_collection("documents")
        chunks = db.get_collection("doc_chunks")
        notes = db.get_collection("notes")
        mind_palace = db.get_collection("mind_palace_documents")

        n1 = migrate_documents(documents, dry_run=args.dry_run, limit=args.limit)
        n2 = migrate_doc_chunks(chunks, dry_run=args.dry_run, limit=args.limit)
        n3 = migrate_notes(notes, dry_run=args.dry_run, limit=args.limit)
        n4 = migrate_mind_palace(mind_palace, dry_run=args.dry_run, limit=args.limit)

    logger.info(
        "Migration summary: documents=%s, doc_chunks=%s, notes=%s, mind_palace_documents=%s",
        n1,
        n2,
        n3,
        n4,
    )


if __name__ == "__main__":  # pragma: no cover - script entrypoint
    main()
