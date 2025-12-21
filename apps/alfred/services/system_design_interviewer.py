from __future__ import annotations

from dataclasses import dataclass
from typing import List

from alfred.schemas.system_design import (
    DiagramAnalysis,
    DiagramEvaluation,
    DiagramQuestion,
    DiagramQuestionSet,
    DiagramSuggestion,
    DiagramSuggestionSet,
    DesignPrompt,
    ExcalidrawData,
    SystemDesignKnowledgeDraft,
    SystemDesignSession,
)
from alfred.services.llm_service import LLMService
from alfred.services.system_design_heuristics import (
    analyze_diagram,
    ask_probing_questions,
    knowledge_draft,
    suggest_improvements,
    evaluate_design,
    summarize_diagram,
)


@dataclass
class SystemDesignInterviewer:
    llm_service: LLMService | None = None

    def present_design_problem(self, problem: str) -> DesignPrompt:
        if not self.llm_service:
            return DesignPrompt(problem=problem.strip(), constraints=[], target_scale=None)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a system design interviewer. Return a concise prompt with "
                    "constraints and an optional target scale."
                ),
            },
            {"role": "user", "content": f"Problem: {problem.strip()}"},
        ]
        try:
            return self.llm_service.structured(messages, DesignPrompt)
        except Exception:
            return DesignPrompt(problem=problem.strip(), constraints=[], target_scale=None)

    def analyze_diagram(self, diagram: ExcalidrawData) -> DiagramAnalysis:
        if not self.llm_service:
            return analyze_diagram(diagram)
        summary = summarize_diagram(diagram)
        messages = [
            {
                "role": "system",
                "content": (
                    "Analyze a system design diagram and return missing components, "
                    "invalid connections, bottlenecks, and best-practice hints."
                ),
            },
            {"role": "user", "content": f"Diagram summary: {summary}"},
        ]
        try:
            return self.llm_service.structured(messages, DiagramAnalysis)
        except Exception:
            return analyze_diagram(diagram)

    def ask_probing_questions(self, diagram: ExcalidrawData) -> List[DiagramQuestion]:
        if not self.llm_service:
            return ask_probing_questions(diagram)
        summary = summarize_diagram(diagram)
        messages = [
            {
                "role": "system",
                "content": "Generate 3-5 probing system design questions.",
            },
            {"role": "user", "content": f"Diagram summary: {summary}"},
        ]
        try:
            return self.llm_service.structured(messages, DiagramQuestionSet).items
        except Exception:
            return ask_probing_questions(diagram)

    def suggest_improvements(self, diagram: ExcalidrawData) -> List[DiagramSuggestion]:
        if not self.llm_service:
            return suggest_improvements(diagram)
        summary = summarize_diagram(diagram)
        messages = [
            {
                "role": "system",
                "content": "Suggest practical improvements for the system design diagram.",
            },
            {"role": "user", "content": f"Diagram summary: {summary}"},
        ]
        try:
            return self.llm_service.structured(messages, DiagramSuggestionSet).items
        except Exception:
            return suggest_improvements(diagram)

    def evaluate_design(self, diagram: ExcalidrawData) -> DiagramEvaluation:
        if not self.llm_service:
            return evaluate_design(diagram)
        summary = summarize_diagram(diagram)
        messages = [
            {
                "role": "system",
                "content": "Score the system design diagram on completeness and scalability.",
            },
            {"role": "user", "content": f"Diagram summary: {summary}"},
        ]
        try:
            return self.llm_service.structured(messages, DiagramEvaluation)
        except Exception:
            return evaluate_design(diagram)

    def knowledge_draft(self, session: SystemDesignSession) -> SystemDesignKnowledgeDraft:
        diagram = session.diagram
        if not self.llm_service:
            return knowledge_draft(diagram, problem_statement=session.problem_statement)
        summary = summarize_diagram(diagram)
        messages = [
            {
                "role": "system",
                "content": (
                    "Draft learning topics, zettel cards, and interview prep prompts "
                    "for a system design session."
                ),
            },
            {
                "role": "user",
                "content": f"Problem: {session.problem_statement}\nDiagram summary: {summary}",
            },
        ]
        try:
            return self.llm_service.structured(messages, SystemDesignKnowledgeDraft)
        except Exception:
            return knowledge_draft(diagram, problem_statement=session.problem_statement)
