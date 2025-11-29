"""Quick connectivity test for the Mongo service/connector."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

from scripts._bootstrap import bootstrap


def _bootstrap_paths_and_env() -> None:
    bootstrap()


logger = logging.getLogger("scripts.test_mongo_connection")


def main() -> int:
    _bootstrap_paths_and_env()

    from alfred.core.config import settings
    from alfred.services.mongo import MongoService

    parser = argparse.ArgumentParser(description="Test MongoDB connectivity")
    parser.add_argument(
        "--collection",
        default="system_health",
        help="Collection to use for optional queries",
    )
    parser.add_argument(
        "--find-one",
        action="store_true",
        help="Attempt to fetch a single document from the target collection",
    )
    args = parser.parse_args()

    uri = settings.mongo_uri
    database = settings.mongo_database
    if not uri or not database:
        logger.error("MONGO_URI and/or MONGO_DATABASE are not configured.")
        return 2

    service = MongoService(default_collection=args.collection)

    try:
        service.ping()
    except Exception as exc:  # pragma: no cover - network interaction
        logger.error("Mongo ping failed: %s", exc)
        return 1

    logger.info("OK: Connected to MongoDB at %s (database='%s')", uri, database)

    if args.find_one:
        doc: dict[str, Any] | None
        try:
            doc = service.find_one()
        except Exception as exc:  # pragma: no cover - network interaction
            logger.error("find_one() failed: %s", exc)
            return 1
        if doc is None:
            logger.info("Collection '%s' is empty or not found.", args.collection)
        else:
            logger.info("Sample document from '%s': %s", args.collection, doc)

    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    raise SystemExit(main())
