"""Alfred MCP Server — exposes Alfred's knowledge base to Claude Code.

Run via:  python -m alfred.mcp.server
Config:   Add to ~/.claude/claude_code_config.json as an mcpServers entry.

On startup, checks if the Alfred FastAPI backend is running at localhost:8000.
If not, spawns it automatically so the generic API proxy tool works.
"""

import logging
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

ALFRED_API_URL = "http://localhost:8000"
ALFRED_HEALTH_ENDPOINT = "/healthz"
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # apps/alfred/mcp -> project root
ENV_FILE = PROJECT_ROOT / "apps" / "alfred" / ".env"


def _load_env_vars() -> dict[str, str]:
    """Parse apps/alfred/.env into a dict, skipping comments and placeholders."""
    env = dict(**__import__("os").environ)
    if not ENV_FILE.exists():
        return env
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "<" in line:
            continue
        # Strip inline comments
        if " #" in line:
            line = line[: line.index(" #")]
        if "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("\"'")
    return env


def _is_backend_running() -> bool:
    """Check if the Alfred FastAPI backend is healthy."""
    try:
        resp = httpx.get(f"{ALFRED_API_URL}{ALFRED_HEALTH_ENDPOINT}", timeout=3)
        return resp.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


def _start_backend() -> subprocess.Popen:
    """Spawn the Alfred FastAPI backend as a background subprocess."""
    env = _load_env_vars()
    cmd = [
        sys.executable, "-m", "uvicorn",
        "alfred.main:app",
        "--port", "8000",
        "--host", "127.0.0.1",
    ]
    logger.info("Starting Alfred backend: %s", " ".join(cmd))
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    # Wait for backend to become healthy
    for attempt in range(20):
        if proc.poll() is not None:
            stderr_out = proc.stderr.read().decode() if proc.stderr else ""
            raise RuntimeError(f"Backend process exited immediately: {stderr_out[:500]}")
        if _is_backend_running():
            logger.info("Alfred backend is ready (attempt %d)", attempt + 1)
            return proc
        time.sleep(0.5)

    proc.terminate()
    raise RuntimeError("Alfred backend did not become healthy within 10 seconds")


@dataclass
class AlfredContext:
    """Shared resources initialized once at server startup."""

    session_factory: object  # sessionmaker callable
    session_id: str  # UUID for auto-logging this session
    backend_process: subprocess.Popen | None = field(default=None, repr=False)


@asynccontextmanager
async def alfred_lifespan(server: FastMCP) -> AsyncIterator[AlfredContext]:
    """Initialize Alfred backend resources at startup."""
    # Auto-start backend if not running
    backend_proc = None
    if _is_backend_running():
        logger.info("Alfred backend already running at %s", ALFRED_API_URL)
    else:
        logger.info("Alfred backend not detected — starting automatically...")
        try:
            backend_proc = _start_backend()
        except RuntimeError:
            logger.exception("Failed to auto-start Alfred backend")
            # Continue anyway — hand-crafted tools using direct DB still work

    # Initialize direct DB access for hand-crafted tools
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
        backend_process=backend_proc,
    )

    # Shutdown: clean up auto-started backend
    if backend_proc and backend_proc.poll() is None:
        logger.info("Shutting down auto-started Alfred backend (pid=%d)", backend_proc.pid)
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()

    logger.info("Alfred MCP server shutting down (session=%s)", session_id)


mcp = FastMCP("alfred", lifespan=alfred_lifespan)

# Import tools so they register with the mcp instance via @mcp.tool()
import alfred.mcp.tools  # noqa: F401

if __name__ == "__main__":
    mcp.run(transport="stdio")
