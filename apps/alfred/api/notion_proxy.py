"""Expose a thin Notion proxy for the Alfred FastAPI backend."""

from __future__ import annotations

import httpx
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from alfred.core.config import settings

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _notion_headers() -> dict[str, str] | None:
    token = settings.notion_token
    if not token:
        return None
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def register_notion_proxy(app: FastAPI) -> None:
    """Register lightweight Notion database/page proxy routes."""

    @app.get("/api/notion")
    async def proxy_notion(databaseId: str | None = Query(None), pageId: str | None = Query(None)):
        headers = _notion_headers()
        if headers is None:
            return JSONResponse({"success": False, "error": "NOTION_TOKEN not configured"}, status_code=401)

        if not databaseId and not pageId:
            return JSONResponse(
                {"success": False, "error": "Provide either databaseId or pageId query param"},
                status_code=400,
            )

        async with httpx.AsyncClient(timeout=30.0) as client:
            if databaseId:
                response = await client.post(
                    f"{NOTION_API_BASE}/databases/{databaseId}/query",
                    headers=headers,
                )
            else:
                response = await client.get(
                    f"{NOTION_API_BASE}/pages/{pageId}",
                    headers=headers,
                )

        if response.status_code != 200:
            return JSONResponse(
                {
                    "success": False,
                    "error": f"HTTP {response.status_code}: {response.text}",
                },
                status_code=response.status_code,
            )

        return JSONResponse({"success": True, "data": response.json()})
