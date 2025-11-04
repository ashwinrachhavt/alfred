"""CopilotKit integration helpers."""

from functools import lru_cache

from copilotkit import CopilotKitRemoteEndpoint, LangGraphAgent

from alfred.services.agentic_rag import build_agent_graph


@lru_cache(maxsize=1)
def get_copilotkit_remote_endpoint() -> CopilotKitRemoteEndpoint:
    """Create a singleton CopilotKit remote endpoint for Alfred."""
    agentic_graph = build_agent_graph()
    return CopilotKitRemoteEndpoint(
        agents=lambda _context: [
            LangGraphAgent(
                name="alfred",
                description="Bruce Wayne OS assistant orchestrated by Alfred.",
                graph=agentic_graph,
            )
        ],
        actions=[],
    )
