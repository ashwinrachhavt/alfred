from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from alfred.core import agno_tracing
from alfred.services.mongo import MongoService
from alfred.services.slack import SlackService

router = APIRouter(prefix="/api/tools", tags=["tools"])
logger = logging.getLogger(__name__)


class SlackSendRequest(BaseModel):
    channel: str = Field(..., description="Channel ID or name (e.g., #general or C12345)")
    text: str = Field(..., description="Message text")
    thread_ts: Optional[str] = Field(None, description="Thread timestamp to reply within a thread")


@router.post("/slack/send")
def slack_send(payload: SlackSendRequest) -> dict[str, Any]:
    """Send a Slack message using configured SLACK_API_KEY."""
    try:
        svc = SlackService()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Slack not configured: {exc}")

    try:
        result = svc.send_message(
            channel=payload.channel, text=payload.text, thread_ts=payload.thread_ts
        )
        try:
            agno_tracing.log_tool_call(
                name="slack_send",
                args={"channel": payload.channel, "thread": bool(payload.thread_ts)},
                result={"permalink": result.get("permalink")},
            )
        except Exception:
            pass
        return result
    except Exception as exc:
        logger.warning("Slack send failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


class MongoQueryRequest(BaseModel):
    collection: str = Field(..., description="Mongo collection name")
    filter: dict[str, Any] | None = Field(None, description="MongoDB filter object")
    limit: int = Field(20, ge=0, le=100, description="Max number of documents to return")


@router.post("/mongo/query")
def mongo_query(payload: MongoQueryRequest) -> dict[str, Any]:
    """Read-only query against Mongo via MongoService."""
    coll = payload.collection.strip()
    if not coll:
        raise HTTPException(status_code=422, detail="collection is required")

    try:
        svc = MongoService(default_collection=coll)
        docs = svc.find_many(payload.filter or {}, limit=payload.limit)
        try:
            agno_tracing.log_tool_call(
                name="mongo_query",
                args={"collection": coll, "filter": payload.filter or {}, "limit": payload.limit},
                result={"count": len(docs)},
            )
        except Exception:
            pass
        return {"collection": coll, "count": len(docs), "items": docs}
    except Exception as exc:
        logger.warning("Mongo query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status")
def tools_status() -> dict[str, Any]:
    """Report configured tool backends for smoke testing."""
    has_slack = True
    try:
        SlackService()
    except Exception:
        has_slack = False

    mongo_ok = False
    try:
        mongo_ok = MongoService().ping()
    except Exception:
        mongo_ok = False

    tracing_enabled = agno_tracing.init() and agno_tracing.is_enabled()
    return {
        "slack": has_slack,
        "mongo": mongo_ok,
        "tracing": tracing_enabled,
    }
