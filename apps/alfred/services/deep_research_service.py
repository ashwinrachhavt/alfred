"""Deprecated — use ``alfred.services.research_service`` instead.

This module re-exports the renamed symbols for backwards compatibility.
"""

from alfred.services.research_service import (
    DeepResearchReport,
    DeepResearchService,
    EnrichedSource,
    ReportSection,
    ResearchReport,
    ResearchService,
    generate_deep_research,
)

__all__ = [
    "DeepResearchReport",
    "DeepResearchService",
    "EnrichedSource",
    "ReportSection",
    "ResearchReport",
    "ResearchService",
    "generate_deep_research",
]
