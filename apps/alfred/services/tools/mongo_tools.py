from __future__ import annotations

import json
import logging
from typing import Any

from alfred.core.dependencies import get_mongo_service

logger = logging.getLogger(__name__)


def query_mongo(collection: str, filter_json: str, limit: int = 20) -> str:
    """Query MongoDB for documents using a JSON filter (read-only).

    Use this to fetch existing records or notes by simple criteria. The filter
    must be a valid JSON object; results are returned as markdown with a JSON
    code block. Does not modify the database.
    """
    coll = (collection or "").strip()
    if not coll:
        return "### Mongo Query\n\n⚠️ Missing required parameter: collection"

    try:
        filt: dict[str, Any]
        filt = json.loads(filter_json) if (filter_json or "").strip() else {}
        if not isinstance(filt, dict):
            return "### Mongo Query\n\n⚠️ The filter must be a JSON object."
    except json.JSONDecodeError as exc:
        return (
            "### Mongo Query\n\n"
            f'⚠️ Invalid JSON filter: {exc}. Provide an object like `{{"status": "open"}}`.'
        )

    try:
        n = max(0, min(int(limit), 100))
    except Exception:
        n = 20

    try:
        svc = get_mongo_service().with_collection(coll)
        docs = svc.find_many(filt, limit=n)
        if not docs:
            return (
                f"### Mongo Query — collection `{coll}`\n\nNo documents matched the given filter."
            )

        # Serialize using default=str to handle ObjectId, datetime, etc.
        as_json = json.dumps(docs, ensure_ascii=False, indent=2, default=str)
        header = f"### Mongo Query — collection `{coll}`\n\n"
        meta = f"Filter: `{json.dumps(filt, ensure_ascii=False)}`\nLimit: {n}\n\n"
        body = f"```json\n{as_json}\n```"
        out = header + meta + body
        return out
    except Exception as exc:  # pragma: no cover - defensive path
        logger.warning("mongo query failed: %s", exc)
        return f"### Mongo Query — collection `{coll}`\n\n⚠️ Query failed. Error: {exc}"
