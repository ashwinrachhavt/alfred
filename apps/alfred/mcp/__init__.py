"""Alfred MCP Server — exposes Alfred's full API to Claude Code.

Auto-starts the FastAPI backend if not already running.
Provides both hand-crafted tools (direct DB) and a generic HTTP proxy
for the entire Alfred API surface.
"""
