#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import uuid
from typing import Iterable

from alfred.core.database import SessionLocal
from alfred.models.doc_storage import DocumentRow
from alfred.services.doc_storage_pg import DocStorageService
from sqlalchemy import select

logger = logging.getLogger("scripts.generate_document_images")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate and persist OpenAI cover images for stored documents."
    )
    p.add_argument(
        "--doc-id",
        action="append",
        dest="doc_ids",
        help="Document UUID to process (repeatable). If omitted, processes recent docs missing images.",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max docs to process when --doc-id is not provided.",
    )
    p.add_argument("--force", action="store_true", help="Regenerate even if already present.")
    p.add_argument("--model", default="gpt-image-1", help="OpenAI image model.")
    p.add_argument("--size", default="1024x1024", help="Requested image size.")
    p.add_argument("--quality", default="high", help="Requested image quality.")
    p.add_argument("--dry-run", action="store_true", help="Print what would run without saving.")
    return p.parse_args()


def _find_docs_missing_images(limit: int) -> list[str]:
    limit = max(1, min(int(limit), 500))
    with SessionLocal() as s:
        stmt = (
            select(DocumentRow.id)
            .where(DocumentRow.image.is_(None))
            .order_by(DocumentRow.created_at.desc())
            .limit(limit)
        )
        rows = s.exec(stmt).all()
        ids: list[str] = []
        for row in rows:
            if isinstance(row, uuid.UUID):
                ids.append(str(row))
                continue
            if isinstance(row, str) and row.strip():
                ids.append(row.strip())
                continue
            if hasattr(row, "__len__") and hasattr(row, "__getitem__") and len(row) == 1:
                ids.append(str(row[0]))
                continue
            ids.append(str(row))
        return ids


def iter_target_doc_ids(args: argparse.Namespace) -> Iterable[str]:
    explicit = [x.strip() for x in (args.doc_ids or []) if isinstance(x, str) and x.strip()]
    if explicit:
        return explicit
    return _find_docs_missing_images(args.limit)


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    ids = list(iter_target_doc_ids(args))
    if not ids:
        logger.info("No documents to process.")
        return 0

    logger.info("Processing %d document(s).", len(ids))

    svc = DocStorageService()
    failures = 0

    for doc_id in ids:
        if args.dry_run:
            logger.info("[dry-run] Would generate image for %s", doc_id)
            continue

        try:
            res = svc.generate_document_title_image(
                doc_id,
                force=bool(args.force),
                model=str(args.model),
                size=str(args.size),
                quality=str(args.quality),
            )
            if res.get("skipped"):
                logger.info("Skipped %s (%s)", doc_id, res.get("reason") or "skipped")
            else:
                logger.info("Generated image for %s", doc_id)
        except Exception as exc:
            failures += 1
            logger.exception("Failed to generate image for %s: %s", doc_id, exc)

    if failures:
        logger.error("Done with %d failure(s).", failures)
        return 1

    logger.info("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
