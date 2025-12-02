"""End-to-end Mongo cleaning pipeline.

Processes all documents in a Mongo collection (default: notes_db.documents):
- Cleans text (basic heuristics)
- Runs extraction (lang, summary, topics, tags, entities, embedding)
- Updates tokens + hash
- Optionally (re)chunks and writes to doc_chunks

Usage examples:
  PYTHONPATH=apps python apps/alfred/services/commands/text_cleaning.py --batch-size 200 --rechunk
  PYTHONPATH=apps python apps/alfred/services/commands/text_cleaning.py --query '{"source_url": {"$regex": "medium.com"}}'
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from alfred.schemas.documents import DocChunkRecord
from alfred.services.chunking import ChunkingService
from alfred.services.extraction_service import ExtractionService
from alfred.services.mongo import MongoService
from alfred.prompts import load_prompt
from bson import ObjectId
from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError
from tqdm.auto import tqdm


def _normalize_ws(text: str) -> str:
    t = (text or "").replace("\u00a0", " ")  # nbsp -> space
    # remove zero-width chars
    t = re.sub(r"[\u200B-\u200D\uFEFF]", "", t)
    # collapse >2 newlines
    t = re.sub(r"\n{3,}", "\n\n", t)
    # strip trailing spaces per line
    t = "\n".join(line.rstrip() for line in t.splitlines())
    return t.strip()


_NOISE_PATTERNS = [
    r"^\s*skip to .*",
    r"^\s*notifications\s*$",
    r"^\s*follow(ing)?\s*$",
    r"^\s*view list\s*$",
    r"^\s*join now\s*$",
    r"^\s*clap(s)?\s*$",
    r"^\s*conversation opened.*$",
]


def basic_clean(text: str) -> str:
    # Remove common UI/boilerplate lines
    lines = [ln for ln in (text or "").splitlines()]
    kept: List[str] = []
    for ln in lines:
        raw = ln.strip().lower()
        if any(re.match(p, raw) for p in _NOISE_PATTERNS):
            continue
        # drop tiny emoji-only lines
        if len(raw) <= 3 and re.sub(r"\W+", "", raw) == "":
            continue
        kept.append(ln)
    return _normalize_ws("\n".join(kept))


def _iter_docs(
    mongo: MongoService, collection: str, batch_size: int, filt: Dict[str, Any]
) -> Iterable[List[Dict[str, Any]]]:
    coll = mongo._connector.get_collection(collection)  # type: ignore[attr-defined]
    cursor = coll.find(filt).batch_size(max(1, batch_size))
    try:
        batch: List[Dict[str, Any]] = []
        for doc in cursor:
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        cursor.close()


def _rechunk_doc(mongo: MongoService, doc: Dict[str, Any], *, text: str) -> int:
    chunks_coll = mongo._connector.get_collection("doc_chunks")  # type: ignore[attr-defined]
    doc_id = doc.get("_id")
    if not isinstance(doc_id, ObjectId):
        return 0
    # Delete existing chunks
    chunks_coll.delete_many({"doc_id": doc_id})
    # Build new chunks
    svc = ChunkingService()
    max_tokens = doc.get("tokens") or 500
    overlap = min(100, int((max_tokens or 500) * 0.2))
    mode = "auto"
    content_type = (
        "markdown"
        if (doc.get("raw_markdown") or "").strip()
        else (doc.get("content_type") or "web")
    )
    payloads = svc.chunk(
        text, max_tokens=max_tokens, overlap=overlap, mode=mode, content_type=content_type
    )
    if not payloads:
        return 0
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    captured_at = doc.get("captured_at") or now
    captured_hour = captured_at.hour if hasattr(captured_at, "hour") else now.hour
    day_bucket = (
        datetime(captured_at.year, captured_at.month, captured_at.day, tzinfo=timezone.utc)
        if hasattr(captured_at, "year")
        else now
    )

    to_insert: List[Dict[str, Any]] = []
    for ch in payloads:
        ctokens = ch.tokens if ch.tokens is not None else len((ch.text or "").split())
        rec = DocChunkRecord(
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
        to_insert.append(rec.model_dump())
    res = chunks_coll.insert_many(to_insert)
    return len(res.inserted_ids)


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="End-to-end Mongo cleaning pipeline (notes_db)")
    parser.add_argument("--collection", default="documents")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument(
        "--query", type=str, default=None, help="JSON query string to filter documents"
    )
    parser.add_argument(
        "--rechunk", action="store_true", help="Rebuild doc_chunks for each document"
    )
    parser.add_argument(
        "--show-llm", action="store_true", help="Print extracted fields for debugging"
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Run taxonomy classification and store under topics.classification",
    )
    parser.add_argument(
        "--taxonomy-file",
        type=str,
        default=None,
        help="Path to a taxonomy context file to load into the prompt",
    )
    parser.add_argument(
        "--no-embed", action="store_true", help="Skip embedding generation for speed/cost"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    mongo = MongoService()
    if not mongo.ping():
        print("Mongo ping failed", file=sys.stderr)
        return 1

    extractor = ExtractionService()

    filt: Dict[str, Any] = json.loads(args.query) if args.query else {}
    coll = mongo._connector.get_collection(args.collection)  # type: ignore[attr-defined]
    total_docs = coll.count_documents(filt)
    total = 0
    updated = 0
    chunked = 0
    skipped_dupe = 0

    with tqdm(
        total=total_docs, desc="Cleaning", unit="doc", dynamic_ncols=True, mininterval=0.1
    ) as pbar:
        for batch in _iter_docs(mongo, args.collection, args.batch_size, filt):
            for doc in batch:
                total += 1
            _id = doc.get("_id")
            if not isinstance(_id, ObjectId):
                continue
            raw_markdown = doc.get("raw_markdown") or None
            cleaned_text_existing = doc.get("cleaned_text") or ""
            base_text = raw_markdown or cleaned_text_existing
            cleaned_text = basic_clean(base_text)

            enrich = extractor.extract_all(
                cleaned_text=cleaned_text,
                raw_markdown=raw_markdown,
                metadata=doc.get("metadata") or {},
                include_embedding=(not args.no_embed),
            )

            set_fields: Dict[str, Any] = {}

            # Compute diff-only updates to reflect true modifications
            def _maybe_set(key: str, new_val: Any):
                if new_val is None:
                    return
                old_val = doc.get(key)
                if old_val != new_val:
                    set_fields[key] = new_val

            if cleaned_text and cleaned_text != cleaned_text_existing:
                set_fields["cleaned_text"] = cleaned_text
            # Refresh tokens/hash (diff-aware)
            new_tokens = enrich.get("tokens")
            new_hash = enrich.get("hash")
            _maybe_set("tokens", new_tokens)
            _maybe_set("hash", new_hash)
            # Optional fields (diff-aware)
            _maybe_set("lang", enrich.get("lang"))
            _maybe_set("summary", enrich.get("summary"))
            _maybe_set("topics", enrich.get("topics"))
            _maybe_set("tags", enrich.get("tags"))
            _maybe_set("entities", enrich.get("entities"))
            if enrich.get("embedding") is not None:
                _maybe_set("embedding", enrich.get("embedding"))

            if args.show_llm:
                # Print a compact snapshot of extraction
                try:
                    brief = {
                        "lang": enrich.get("lang"),
                        "summary.short": (enrich.get("summary") or {}).get("short"),
                        "topics": enrich.get("topics"),
                        "tags": enrich.get("tags"),
                        "entities_n": len(enrich.get("entities") or []),
                        "embedding": bool(enrich.get("embedding")),
                    }
                    tqdm.write(f"LLM → {_id}: {json.dumps(brief, ensure_ascii=False)[:300]}")
                except Exception:
                    pass

            # Optional: taxonomy classification
            if args.classify:
                try:
                    if args.taxonomy_file and os.path.isfile(args.taxonomy_file):
                        with open(args.taxonomy_file, "r", encoding="utf-8") as fh:
                            taxonomy_ctx = fh.read()
                    else:
                        taxonomy_ctx = load_prompt("classification", "taxonomy_full.txt")
                    cls_doc = extractor.classify_taxonomy(
                        text=cleaned_text or base_text, taxonomy_context=taxonomy_ctx
                    )
                    # diff-aware nested set for topics.classification
                    existing_topics = doc.get("topics") or {}
                    existing_cls = (
                        existing_topics.get("classification")
                        if isinstance(existing_topics, dict)
                        else None
                    )
                    if existing_cls != cls_doc:
                        set_fields["topics.classification"] = cls_doc
                    # If title missing, fill from classification
                    if not (doc.get("title") or "").strip():
                        title = (
                            (cls_doc.get("topic") or {}).get("title")
                            if isinstance(cls_doc.get("topic"), dict)
                            else None
                        )
                        if title:
                            set_fields["title"] = title
                    if args.show_llm:
                        try:
                            tqdm.write(
                                f"CLS → {_id}: {json.dumps(cls_doc, ensure_ascii=False)[:300]}"
                            )
                        except Exception:
                            pass
                except Exception as exc:
                    tqdm.write(f"[CLS ERROR] {_id}: {exc}")

            if args.dry_run:
                tqdm.write(f"[DRY] Would update {_id} with keys: {list(set_fields.keys())}")
            else:
                # Duplicate hash protection: skip if new hash collides with another doc
                try:
                    if new_hash and new_hash != doc.get("hash"):
                        dupe = coll.find_one({"hash": new_hash, "_id": {"$ne": _id}}, {"_id": 1})
                        if dupe:
                            skipped_dupe += 1
                            tqdm.write(f"[SKIP DUP] {_id} → hash collides with {dupe['_id']}")
                            pbar.update(1)
                            continue

                    if set_fields:
                        res = mongo.update_one(
                            {"_id": _id}, {"$set": set_fields}, collection=args.collection
                        )
                        if (res or {}).get("modified_count", 0) > 0:
                            updated += 1
                    if args.rechunk:
                        c = _rechunk_doc(mongo, doc, text=cleaned_text or base_text)
                        chunked += c
                except DuplicateKeyError:
                    skipped_dupe += 1
                    tqdm.write(f"[SKIP DUP] {_id} → DuplicateKey on hash; skipped")
                except Exception as exc:
                    tqdm.write(f"[ERROR] {_id}: {exc}")

            pbar.update(1)

    print(
        f"Processed: {total}, Updated: {updated}, New Chunks: {chunked}, Skipped (dupe): {skipped_dupe}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
