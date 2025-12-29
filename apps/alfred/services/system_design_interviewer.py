"""Heuristic system-design "interviewer".

The system design feature is designed to work even when no LLM credentials are
configured. This module provides lightweight, deterministic defaults and can be
extended to use `LLMService` for richer analysis when available.
"""

from __future__ import annotations

import uuid

from alfred.schemas.system_design import (
    DesignPrompt,
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramQuestion,
    DiagramSuggestion,
    ExcalidrawData,
    SystemDesignKnowledgeDraft,
    SystemDesignSession,
)


def _new_id() -> str:
    return uuid.uuid4().hex


class SystemDesignInterviewer:
    """Provides analysis, critique, and prompts for system design sessions.

    When an LLM client is not configured, methods fall back to predictable,
    low-friction defaults so the UI/API remains usable.
    """

    def __init__(self, *, llm_service=None) -> None:  # noqa: ANN001
        self._llm_service = llm_service

    def present_design_problem(self, problem: str) -> DesignPrompt:
        return DesignPrompt(
            problem=problem,
            constraints=[
                "Define functional + non-functional requirements",
                "Estimate scale and choose storage/compute accordingly",
                "Call out tradeoffs and failure modes",
            ],
            target_scale=None,
        )

    def analyze_diagram(self, diagram: ExcalidrawData) -> DiagramAnalysis:
        # Minimal heuristic: if the diagram is empty, suggest common building blocks.
        if not diagram.elements:
            return DiagramAnalysis(
                detected_components=[],
                missing_components=["client", "service", "database"],
                bottlenecks=[],
                best_practices_hints=[
                    "Start with a simple request flow, then add caching/queues as needed.",
                    "Add observability (logs/metrics/tracing) early.",
                ],
                completeness_score=10,
            )

        return DiagramAnalysis(
            detected_components=[],
            missing_components=[],
            bottlenecks=[],
            best_practices_hints=[],
            completeness_score=50,
        )

    def ask_probing_questions(self, diagram: ExcalidrawData) -> list[DiagramQuestion]:
        return [
            DiagramQuestion(
                id=_new_id(),
                text="What are the top read/write paths and their latency targets?",
                rationale="Clarifies performance requirements and hot paths.",
            ),
            DiagramQuestion(
                id=_new_id(),
                text="What happens when your primary datastore is unavailable?",
                rationale="Surfaces resiliency and failover strategy.",
            ),
            DiagramQuestion(
                id=_new_id(),
                text="Which parts need strong consistency vs eventual consistency?",
                rationale="Guides data model and replication decisions.",
            ),
        ]

    def suggest_improvements(self, diagram: ExcalidrawData) -> list[DiagramSuggestion]:
        return [
            DiagramSuggestion(
                id=_new_id(),
                text="Add caching for hot reads (and define invalidation strategy).",
                priority="high",
            ),
            DiagramSuggestion(
                id=_new_id(),
                text="Introduce async processing for heavy writes via a queue.",
                priority="medium",
            ),
            DiagramSuggestion(
                id=_new_id(),
                text="Add rate limiting and auth at the edge or gateway.",
                priority="medium",
            ),
        ]

    def evaluate_design(self, diagram: ExcalidrawData) -> DiagramEvaluation:
        analysis = self.analyze_diagram(diagram)
        completeness = analysis.completeness_score
        return DiagramEvaluation(
            completeness=completeness,
            scalability=min(100, completeness + 10),
            tradeoffs=min(100, completeness + 5),
            communication=min(100, completeness + 15),
            technical_depth=min(100, completeness + 5),
            notes=analysis.best_practices_hints,
        )

    def knowledge_draft(self, session: SystemDesignSession) -> SystemDesignKnowledgeDraft:
        # Keep the default draft minimal; downstream flows can enrich it.
        return SystemDesignKnowledgeDraft(
            topics=[],
            zettels=[],
            notes=[
                f"Problem: {session.problem_statement}",
                "Capture key assumptions, constraints, and tradeoffs as you iterate.",
            ],
        )
