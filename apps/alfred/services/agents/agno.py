import logging
from typing import Optional

# Local services
from alfred.core.logging import setup_logging
from alfred.services.doc_storage import DocStorageService
from dotenv import load_dotenv


def fetch_notes(q: Optional[str] = None, *, skip: int = 0, limit: int = 10) -> dict:
    """Return notes from Mongo via DocStorageService.

    Args:
        q: Optional case-insensitive substring filter on note text.
        skip: Number of items to skip.
        limit: Max number of items to return (capped in service).
    """
    svc = DocStorageService()
    svc.ensure_indexes()
    return svc.list_notes(q=q, skip=skip, limit=limit)


def fetch_documents(
    *,
    q: Optional[str] = None,
    topic: Optional[str] = None,
    date: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    skip: int = 0,
    limit: int = 10,
) -> dict:
    """Return documents from Mongo via DocStorageService.

    Args mirror the underlying service and support simple text, topic,
    and time-based filtering.
    """
    svc = DocStorageService()
    svc.ensure_indexes()
    return svc.list_documents(
        q=q,
        topic=topic,
        date=date,
        start=start,
        end=end,
        skip=skip,
        limit=limit,
    )


def main() -> None:
    load_dotenv()
    setup_logging()
    log = logging.getLogger("agents.test")

    try:
        svc = DocStorageService()
        ok = svc.ping()
        log.info("Mongo ping: %s", ok)
    except Exception as e:  # pragma: no cover - connection error path
        log.error(
            "Mongo connection failed: %s. Ensure MONGO_URI and MONGO_DATABASE are set.",
            e,
        )
        return

    notes = fetch_notes(q=None, limit=5)
    if notes.get("items"):
        log.info("First note: %s", notes["items"][0])

    docs = fetch_documents(q=None, limit=5)
    log.info(
        "Documents total=%s returned=%s",
        docs.get("total"),
        len(docs.get("items", [])),
    )
    if docs.get("items"):
        log.info("First document: %s", docs["items"][0])


if __name__ == "__main__":
    main()
