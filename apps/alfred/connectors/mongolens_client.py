"""Client wrapper for MongoDB Lens MCP server.

This connector is optional. It communicates with a MongoDB Lens MCP HTTP
server to run natural-language queries against MongoDB and return structured
results. It is designed to be used by AI agents, and gracefully handled as an
optional dependency via settings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from alfred.core.config import settings

logger = logging.getLogger(__name__)


class MongoLensMCPClient:
    def __init__(
        self,
        *,
        server_url: str | None = None,
        database: str | None = None,
        connection_string: str | None = None,
        timeout: float | None = None,
    ) -> None:
        self.server_url = (server_url or settings.mcp_server_url or "").rstrip("/")
        self.database = database or settings.mcp_database or settings.mongo_database
        self.connection_string = connection_string or settings.mongo_uri
        self.timeout = timeout or float(settings.mcp_timeout)

        if not self.server_url:
            raise ValueError("MCP server URL not configured (MCP_SERVER_URL)")

    async def health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.server_url}/health")
                return resp.status_code == 200
        except Exception as exc:
            logger.debug("MCP health check failed: %s", exc)
            return False

    async def query(self, query: str, *, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = {
            "query": query,
            "context": context or {},
            "database": self.database,
            "connection_string": self.connection_string,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(f"{self.server_url}/query", json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"MCP server error {resp.status_code}: {resp.text}")
            return resp.json()

