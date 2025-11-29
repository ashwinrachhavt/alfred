"""Quick connectivity test for the Mongo service/connector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _add_repo_path() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    sys.path.append(str(repo_root / "apps"))


def main() -> int:
    _add_repo_path()

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
        print("MONGO_URI and/or MONGO_DATABASE are not configured.")
        return 2

    service = MongoService(default_collection=args.collection)

    try:
        service.ping()
    except Exception as exc:  # pragma: no cover - network interaction
        print(f"Mongo ping failed: {exc}")
        return 1

    print(f"OK: Connected to MongoDB at {uri} (database='{database}')")

    if args.find_one:
        doc: dict[str, Any] | None
        try:
            doc = service.find_one()
        except Exception as exc:  # pragma: no cover - network interaction
            print(f"find_one() failed: {exc}")
            return 1
        if doc is None:
            print(f"Collection '{args.collection}' is empty or not found.")
        else:
            print(f"Sample document from '{args.collection}': {doc}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
