"""Deep research subsystem — wraps the deepagents package with Alfred tools + specs."""

from alfred.services.deep_research.registry import (
    ResearchToolRegistry,
    get_tool_registry,
)
from alfred.services.deep_research.service import DeepResearchService

__all__ = ["DeepResearchService", "ResearchToolRegistry", "get_tool_registry"]
