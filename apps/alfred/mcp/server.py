"""Alfred MCP Server — exposes Alfred's knowledge base to Claude Code.

Run via:  python -m alfred.mcp.server
Config:   Add to ~/.claude/claude_code_config.json as an mcpServers entry.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)


@dataclass
class AlfredContext:
    """Shared resources initialized once at server startup."""

    session_factory: object  # sessionmaker callable
    session_id: str  # UUID for auto-logging this session


@asynccontextmanager
async def alfred_lifespan(server: FastMCP) -> AsyncIterator[AlfredContext]:
    """Initialize Alfred backend resources at startup."""
    try:
        from alfred.core.database import SessionLocal
    except Exception:
        logger.exception("Failed to initialize database — is DATABASE_URL set?")
        raise

    session_id = str(uuid4())
    logger.info("Alfred MCP server started (session=%s)", session_id)

    yield AlfredContext(
        session_factory=SessionLocal,
        session_id=session_id,
    )

    logger.info("Alfred MCP server shutting down (session=%s)", session_id)


mcp = FastMCP("alfred", lifespan=alfred_lifespan)

# Import tools so they register with the mcp instance via @mcp.tool()
import alfred.mcp.tools  # noqa: F401, E402

if __name__ == "__main__":
    mcp.run(transport="stdio")
