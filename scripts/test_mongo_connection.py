"""Quick connectivity test for the Mongo service/connector."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any


def _bootstrap_paths_and_env() -> None:
    """Add `apps/` to sys.path and load env via sitecustomize."""
    repo_root = Path(__file__).resolve().parents[1]
    apps_dir = repo_root / "apps"
    if str(apps_dir) not in sys.path:
        sys.path.append(str(apps_dir))
    try:  # Ensure `.env` is loaded consistently
        import sitecustomize  # noqa: F401
    except Exception:
        pass


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
