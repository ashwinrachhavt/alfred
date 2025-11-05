"""CopilotKit integration helpers."""

from __future__ import annotations

from functools import lru_cache

from alfred.connectors.copilotkit import (
    CopilotKitUnavailable,
    load_remote_endpoint_classes,
)
from alfred.services.agentic_rag import build_agent_graph


@lru_cache(maxsize=1)
def get_copilotkit_remote_endpoint():
    """Create a singleton CopilotKit remote endpoint for Alfred."""

    try:
        endpoint_cls, agent_cls = load_remote_endpoint_classes()
    except CopilotKitUnavailable as exc:  # pragma: no cover - env specific
        raise RuntimeError(str(exc)) from exc

    agentic_graph = build_agent_graph()
    return endpoint_cls(
        agents=lambda _context: [
            agent_cls(
                name="alfred",
                description="Bruce Wayne OS assistant orchestrated by Alfred.",
                graph=agentic_graph,
            )
        ],
        actions=[],
    )
