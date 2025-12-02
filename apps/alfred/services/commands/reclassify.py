"""Re-run taxonomy classification and backfill fields on existing documents.

Classifies documents into (domain, subdomain, microtopics, topic{title,confidence})
and writes the result under `topics.classification`. Optionally backfills the
document `title` when missing.

Examples:
  # Classify only docs missing classification (default filter)
  PYTHONPATH=apps python apps/alfred/services/commands/reclassify.py

  # Classify every document
  PYTHONPATH=apps python apps/alfred/services/commands/reclassify.py --all

  # Restrict to a subset via a custom Mongo filter
  PYTHONPATH=apps python apps/alfred/services/commands/reclassify.py \
      --query '{"source_url": {"$regex": "medium.com"}}'

Notes:
  - Requires OPENAI_API_KEY (or configured provider) for LLM-backed classification.
  - No embeddings or other enrichment are performed — classification only.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

from alfred.prompts import load_prompt
from alfred.services.extraction_service import ExtractionService
from alfred.services.mongo import MongoService
from dotenv import load_dotenv
from tqdm.auto import tqdm


def _iter_docs(mongo: MongoService, collection: str, batch_size: int, filt: Dict[str, Any]):
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


def main(argv: Optional[List[str]] = None) -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Backfill topics.classification for documents")
    parser.add_argument("--collection", default="documents")
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--query", type=str, default=None, help="JSON filter for documents")
    parser.add_argument(
        "--all", action="store_true", help="Ignore default filter and process all docs"
    )
    parser.add_argument(
        "--taxonomy-file", type=str, default=None, help="Path to taxonomy context file"
    )
    parser.add_argument(
        "--no-title-backfill",
        action="store_true",
        help="Do not set document title from classification when missing",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--show-llm", action="store_true")
    args = parser.parse_args(argv)

    mongo = MongoService()
    if not mongo.ping():
        print("Mongo ping failed", flush=True)
        return 1

    extractor = ExtractionService()
    coll = mongo._connector.get_collection(args.collection)  # type: ignore[attr-defined]

    # Default filter: only documents missing classification
    if args.all:
        filt: Dict[str, Any] = json.loads(args.query) if args.query else {}
    else:
        base = {"topics.classification": {"$exists": False}}
        if args.query:
            user = json.loads(args.query)
            base = {"$and": [base, user]}
        filt = base

    total_docs = coll.count_documents(filt)
    updated = 0
    total = 0

    # Load taxonomy context
    if args.taxonomy_file and os.path.isfile(args.taxonomy_file):
        with open(args.taxonomy_file, "r", encoding="utf-8") as fh:
            taxonomy_ctx = fh.read()
    else:
        taxonomy_ctx = load_prompt("classification", "taxonomy_full.txt")

    with tqdm(total=total_docs, desc="Classifying", unit="doc", dynamic_ncols=True) as pbar:
        for batch in _iter_docs(mongo, args.collection, args.batch_size, filt):
            for doc in batch:
                total += 1
                _id = doc.get("_id")
                cleaned_text = (doc.get("cleaned_text") or "").strip()
                raw_markdown = (doc.get("raw_markdown") or "").strip()
                base_text = cleaned_text or raw_markdown
                if not base_text:
                    pbar.update(1)
                    continue

                try:
                    cls_doc = extractor.classify_taxonomy(
                        text=base_text, taxonomy_context=taxonomy_ctx
                    )
                    if args.show_llm:
                        try:
                            from json import dumps

                            tqdm.write(f"CLS → {_id}: {dumps(cls_doc, ensure_ascii=False)[:300]}")
                        except Exception:
                            pass

                    # Prefer nested update when topics is a dict; else replace topics with a dict
                    existing_topics = doc.get("topics")
                    if isinstance(existing_topics, dict):
                        set_fields: Dict[str, Any] = {"topics.classification": cls_doc}
                    else:
                        # Fallback: create topics as an object to hold classification
                        set_fields = {"topics": {"classification": cls_doc}}

                    # Backfill title if missing
                    if not args.no_title_backfill and not (doc.get("title") or "").strip():
                        topic = cls_doc.get("topic") if isinstance(cls_doc, dict) else None
                        title = topic.get("title") if isinstance(topic, dict) else None
                        if title:
                            set_fields["title"] = title

                    if args.dry_run:
                        tqdm.write(
                            f"[DRY] Would update {_id} with keys: {list(set_fields.keys())}",
                        )
                    else:
                        res = mongo.update_one(
                            {"_id": _id}, {"$set": set_fields}, collection=args.collection
                        )
                        if (res or {}).get("modified_count", 0) > 0:
                            updated += 1
                except Exception as exc:
                    tqdm.write(f"[CLS ERROR] {_id}: {exc}")
                finally:
                    pbar.update(1)

    print(f"Processed: {total}, Updated: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
