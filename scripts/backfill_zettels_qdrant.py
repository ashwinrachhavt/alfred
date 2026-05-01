#!/usr/bin/env python3
from __future__ import annotations

"""Backfill existing zettel embeddings into the Qdrant zettel collection."""

import argparse
import logging

from sqlalchemy import func
from sqlmodel import select

from alfred.core.database import SessionLocal
from alfred.core.settings import settings
from alfred.models.zettel import ZettelCard
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger("scripts.backfill_zettels_qdrant")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed and index existing zettels into the configured Qdrant collection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report how many non-archived zettels would be indexed without writing to Qdrant.",
    )
    return parser.parse_args()


def _count_searchable_zettels() -> int:
    with SessionLocal() as session:
        stmt = (
            select(func.count())
            .select_from(ZettelCard)
            .where(ZettelCard.status != "archived")
        )
        return int(session.exec(stmt).one())


def main() -> int:
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    total = _count_searchable_zettels()
    if args.dry_run:
        logger.info(
            "Would backfill %d non-archived zettel(s) into %s.",
            total,
            settings.qdrant_zettels_collection,
        )
        return 0

    with SessionLocal() as session:
        svc = ZettelkastenService(session=session)
        indexed = svc.sync_all_to_vector_index()

    logger.info(
        "Indexed %d zettel(s) into %s.",
        indexed,
        settings.qdrant_zettels_collection,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
