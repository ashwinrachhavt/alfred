from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Literal, TypedDict

from fastapi.concurrency import run_in_threadpool
from langgraph.graph import END, START, StateGraph

from alfred.core.settings import LLMProvider, settings
from alfred.schemas.interview_questions import InterviewQuestionsReport, QuestionItem
from alfred.schemas.panel_interview import PanelConfig, PanelSessionCreate, PanelTurnRequest
from alfred.schemas.unified_interview import (
    UnifiedInterviewOperation,
    UnifiedInterviewRequest,
    UnifiedInterviewResponse,
    UnifiedQuestion,
)
from alfred.services.company_researcher import CompanyResearchService

logger = logging.getLogger(__name__)


class InterviewAgentState(TypedDict):
    operation: UnifiedInterviewOperation
    company: str
    role: str
    max_sources: int
    max_questions: int
    use_firecrawl: bool
    include_deep_research: bool
    target_length_words: int
    candidate_background: str | None
    candidate_response: str | None
    session_id: str | None

    raw_questions: list[dict[str, Any]]
    validated_questions: list[dict[str, Any]]
    questions_with_solutions: list[dict[str, Any]]
    sources_scraped: int

    company_research: dict[str, Any]
    research_report: str

    practice_events: list[dict[str, Any]]
    errors: list[str]


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _append_error(state: InterviewAgentState, message: str) -> list[str]:
    errs = list(state.get("errors") or [])
    errs.append(message)
    return errs


def _normalize_question_item(item: QuestionItem) -> dict[str, Any]:
    return {
        "question": item.question,
        "categories": list(item.categories or []),
        "occurrences": item.occurrences,
        "sources": list(item.sources or []),
    }


def _extract_company_key_insights(doc: dict[str, Any], *, limit: int = 8) -> list[str]:
    report = doc.get("report") or {}
    sections = report.get("sections") or []
    insights: list[str] = []
    for section in sections:
        for item in section.get("insights") or []:
            text = _safe_text(item)
            if text:
                insights.append(text)
    # De-duplicate while preserving order
    unique = list(dict.fromkeys(insights))
    return unique[: max(0, int(limit))]


def _should_use_dspy() -> bool:
    if settings.app_env in {"test", "ci"}:
        return False
    if settings.llm_provider != LLMProvider.openai:
        return False
    if not settings.openai_api_key:
        return False
    return True


@lru_cache(maxsize=1)
def _configure_dspy_lm() -> bool:
    """Best-effort DSPy configuration. Returns True if configured; otherwise False."""

    if not _should_use_dspy():
        return False

    try:
        import dspy
    except Exception as exc:  # pragma: no cover - optional runtime guard
        logger.info("DSPy unavailable: %s", exc)
        return False

    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    if not api_key:
        return False

    model_name = _safe_text(settings.llm_model) or "gpt-4.1-mini"
    model = model_name if "/" in model_name else f"openai/{model_name}"

    # DSPy enforces constraints for OpenAI reasoning models (o1/o3/o4/gpt-5 family).
    # Keep defaults permissive to avoid runtime ValueErrors.
    lm_kwargs: dict[str, Any] = {"api_key": api_key, "cache": False}
    if settings.openai_base_url:
        lm_kwargs["base_url"] = settings.openai_base_url
    if settings.openai_organization:
        lm_kwargs["organization"] = settings.openai_organization

    try:
        lm = dspy.LM(model, temperature=None, max_tokens=None, **lm_kwargs)
        dspy.configure(lm=lm)
        return True
    except Exception as exc:  # pragma: no cover - provider misconfig
        logger.info("DSPy configure failed: %s", exc)
        return False


def _dspy_modules():
    """Create DSPy modules lazily (only when LLM is configured)."""

    if not _configure_dspy_lm():
        return None

    import dspy

    class QuestionValidator(dspy.Signature):
        """Validate whether a string is a plausible real interview question."""

        question: str = dspy.InputField(desc="Interview question to validate")
        company: str = dspy.InputField(desc="Company name for context")
        role: str = dspy.InputField(desc="Role for context")

        is_valid: bool = dspy.OutputField(desc="True if likely a legitimate interview question")
        confidence: float = dspy.OutputField(desc="Confidence score 0-1")
        reasoning: str = dspy.OutputField(desc="Brief reasoning for validity")

    class SolutionGenerator(dspy.Signature):
        """Generate a concise sample solution/answer for an interview question."""

        question: str = dspy.InputField(desc="Interview question")
        question_type: str = dspy.InputField(desc="coding | behavioral | system_design | general")
        difficulty: str = dspy.InputField(desc="easy | medium | hard")
        candidate_background: str = dspy.InputField(
            desc="Optional candidate background; use sparingly to tailor examples"
        )

        solution: str = dspy.OutputField(desc="Sample solution/answer with explanation")
        time_complexity: str = dspy.OutputField(desc="Time complexity if applicable; else 'N/A'")
        space_complexity: str = dspy.OutputField(desc="Space complexity if applicable; else 'N/A'")
        key_insights: list[str] = dspy.OutputField(desc="Key insights bullets")

    return {
        "validator": dspy.ChainOfThought(QuestionValidator),
        "solver": dspy.ChainOfThought(SolutionGenerator),
    }


def _pick_question_type(categories: list[str]) -> str:
    cats = {c.strip().lower() for c in categories if c}
    if "coding" in cats:
        return "coding"
    if "system_design" in cats:
        return "system_design"
    if "behavioral" in cats:
        return "behavioral"
    if "ml_ai" in cats:
        return "coding"
    return "general"


def _compile_report_markdown(
    *,
    company: str,
    role: str,
    company_research: dict[str, Any] | None,
    questions: list[dict[str, Any]],
    target_length_words: int,
) -> str:
    report_doc = company_research or {}
    report = report_doc.get("report") or {}

    lines: list[str] = [
        f"# Interview Preparation Report: {company} — {role}",
        "",
    ]

    exec_summary = _safe_text(report.get("executive_summary"))
    if exec_summary:
        lines.extend(["## Company Overview", exec_summary, ""])

    sections = report.get("sections") or []
    if sections:
        lines.append("## Company Insights")
        for section in sections[:6]:
            name = _safe_text(section.get("name")) or "Insights"
            summary = _safe_text(section.get("summary"))
            if not summary:
                continue
            lines.extend([f"### {name}", summary, ""])
        lines.append("")

    # Heuristic sizing: keep the report roughly within the requested length.
    # More words -> include more questions, up to a sane cap.
    base = max(6, min(25, target_length_words // 120))
    limit_questions = max(1, min(int(base), len(questions)))

    lines.append("## Interview Questions (with sample solutions)")
    for idx, q in enumerate(questions[:limit_questions], start=1):
        q_text = _safe_text(q.get("question")) or "N/A"
        cats = q.get("categories") or []
        lines.extend([f"### Q{idx}. {q_text}", f"**Category:** {', '.join(cats) or 'General'}"])

        sol = q.get("solution") or {}
        approach = _safe_text(sol.get("approach"))
        if approach:
            lines.extend(["", "#### Sample answer / solution", approach, ""])
            tc = _safe_text(sol.get("time_complexity")) or "N/A"
            sc = _safe_text(sol.get("space_complexity")) or "N/A"
            lines.extend([f"**Time complexity:** {tc}", f"**Space complexity:** {sc}", ""])

        insights = sol.get("key_insights") or []
        if isinstance(insights, list) and insights:
            lines.append("**Key insights:**")
            for item in insights[:6]:
                text = _safe_text(item)
                if text:
                    lines.append(f"- {text}")
            lines.append("")

    return "\n".join(lines).strip()


@dataclass
class UnifiedInterviewAgent:
    """Orchestrates interview question collection, deep research, and practice sessions."""

    questions_service: InterviewQuestionsService
    company_research_service: CompanyResearchService
    panel_service: Any

    def __post_init__(self) -> None:
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(InterviewAgentState)

        graph.add_node("route", self._route_node)
        graph.add_node("research_company", self._research_company_node)
        graph.add_node("collect_questions", self._collect_questions_node)
        graph.add_node("validate_questions", self._validate_questions_node)
        graph.add_node("generate_solutions", self._generate_solutions_node)
        graph.add_node("compile_report", self._compile_report_node)
        graph.add_node("practice_session", self._practice_session_node)

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            self._route_operation,
            {
                "collect_questions": "collect_questions",
                "deep_research": "research_company",
                "practice_session": "practice_session",
            },
        )

        graph.add_edge("research_company", "collect_questions")
        graph.add_edge("collect_questions", "validate_questions")
        graph.add_edge("validate_questions", "generate_solutions")
        graph.add_conditional_edges(
            "generate_solutions",
            self._route_after_solutions,
            {"compile_report": "compile_report", END: END},
        )
        graph.add_edge("compile_report", END)
        graph.add_edge("practice_session", END)

        return graph.compile()

    @staticmethod
    def _route_node(state: InterviewAgentState) -> dict[str, Any]:
        # Identity node; kept for readability and to allow conditional entry routing.
        return dict(state)

    @staticmethod
    def _route_operation(state: InterviewAgentState) -> UnifiedInterviewOperation:
        return state["operation"]

    @staticmethod
    def _route_after_solutions(state: InterviewAgentState) -> Literal["compile_report", "__end__"]:
        if state.get("operation") == "deep_research":
            return "compile_report"
        return END

    async def _research_company_node(self, state: InterviewAgentState) -> dict[str, Any]:
        if not state.get("include_deep_research", True):
            return {"company_research": {}}

        try:
            doc = await run_in_threadpool(
                self.company_research_service.generate_report,
                state["company"],
                refresh=False,
            )
            if isinstance(doc, dict):
                return {"company_research": doc}
        except Exception as exc:  # pragma: no cover - network/provider errors
            return {"errors": _append_error(state, f"Company research failed: {exc}")}

        return {"company_research": {}}

    async def _collect_questions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        try:
            report: InterviewQuestionsReport = await run_in_threadpool(
                self.questions_service.generate_report,
                state["company"],
                role=state.get("role"),
                max_sources=state.get("max_sources", 12),
                max_questions=state.get("max_questions", 60),
                use_firecrawl_search=state.get("use_firecrawl", True),
            )
            raw = [_normalize_question_item(item) for item in report.questions]
            return {"raw_questions": raw, "sources_scraped": len(report.sources)}
        except Exception as exc:  # pragma: no cover - network/provider errors
            return {"errors": _append_error(state, f"Question collection failed: {exc}")}

    async def _validate_questions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        raw = list(state.get("raw_questions") or [])
        if not raw:
            return {"validated_questions": []}

        modules = _dspy_modules()
        if modules is None:
            # Fallback: treat collected questions as already normalized and valid.
            return {"validated_questions": raw}

        validator = modules["validator"]
        validated: list[dict[str, Any]] = []
        for q in raw:
            q_text = _safe_text(q.get("question"))
            if not q_text:
                continue
            try:
                result = validator(question=q_text, company=state["company"], role=state["role"])
                is_valid = bool(getattr(result, "is_valid", False))
                confidence = float(getattr(result, "confidence", 0.0) or 0.0)
                reasoning = _safe_text(getattr(result, "reasoning", "")) or ""
                if is_valid and confidence >= 0.7:
                    validated.append(
                        {
                            **q,
                            "validation": {
                                "is_valid": True,
                                "confidence": confidence,
                                "reasoning": reasoning,
                            },
                        }
                    )
            except Exception as exc:  # pragma: no cover - provider/runtime issues
                # If validation becomes flaky, keep going and fall back to raw at the end.
                state["errors"] = _append_error(state, f"Question validation failed: {exc}")

        # If the validator filtered too aggressively, fall back to the original set.
        if not validated:
            validated = raw
        return {"validated_questions": validated, "errors": list(state.get("errors") or [])}

    async def _generate_solutions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        validated = list(state.get("validated_questions") or [])
        if not validated:
            return {"questions_with_solutions": []}

        modules = _dspy_modules()
        if modules is None:
            # Fallback: keep questions but omit solutions.
            return {"questions_with_solutions": validated}

        solver = modules["solver"]

        # Keep costs bounded; solution generation can be expensive.
        max_items = min(20, len(validated))
        with_solutions: list[dict[str, Any]] = []

        for q in validated[:max_items]:
            q_text = _safe_text(q.get("question"))
            if not q_text:
                continue
            cats = q.get("categories") or []
            q_type = _pick_question_type(cats if isinstance(cats, list) else [])

            try:
                result = solver(
                    question=q_text,
                    question_type=q_type,
                    difficulty="medium",
                    candidate_background=_safe_text(state.get("candidate_background")) or "N/A",
                )

                key_insights = getattr(result, "key_insights", []) or []
                if not isinstance(key_insights, list):
                    key_insights = [_safe_text(key_insights)] if _safe_text(key_insights) else []

                with_solutions.append(
                    {
                        **q,
                        "solution": {
                            "approach": _safe_text(getattr(result, "solution", "")),
                            "time_complexity": _safe_text(getattr(result, "time_complexity", "")),
                            "space_complexity": _safe_text(getattr(result, "space_complexity", "")),
                            "key_insights": [_safe_text(x) for x in key_insights if _safe_text(x)],
                        },
                    }
                )
            except Exception as exc:  # pragma: no cover - provider/runtime issues
                with_solutions.append(q)
                state["errors"] = _append_error(state, f"Solution generation failed: {exc}")

        # Include any validated questions beyond the capped solution generation.
        with_solutions.extend(validated[max_items:])
        return {
            "questions_with_solutions": with_solutions,
            "errors": list(state.get("errors") or []),
        }

    async def _compile_report_node(self, state: InterviewAgentState) -> dict[str, Any]:
        report = _compile_report_markdown(
            company=state["company"],
            role=state["role"],
            company_research=state.get("company_research") or {},
            questions=list(state.get("questions_with_solutions") or []),
            target_length_words=state.get("target_length_words", 1000),
        )
        return {"research_report": report}

    async def _practice_session_node(self, state: InterviewAgentState) -> dict[str, Any]:
        try:
            session_id = state.get("session_id")
            if not session_id:
                session = self.panel_service.create_session(
                    PanelSessionCreate(
                        config=PanelConfig(company=state["company"], role=state["role"]),
                        candidate_context=_safe_text(state.get("candidate_background")) or None,
                    )
                )
                session_id = session.id

            events: list[dict[str, Any]] = []
            if state.get("candidate_response"):
                resp = self.panel_service.submit_turn(
                    session_id, PanelTurnRequest(answer=_safe_text(state.get("candidate_response")))
                )
                events = [e.model_dump(mode="json") for e in resp.events]

            return {"session_id": session_id, "practice_events": events}
        except Exception as exc:  # pragma: no cover - storage/runtime issues
            return {"errors": _append_error(state, f"Practice session failed: {exc}")}

    async def process(self, request: UnifiedInterviewRequest) -> UnifiedInterviewResponse:
        """Execute the unified interview workflow and normalize the result shape."""

        company = _safe_text(request.company)
        role = _safe_text(request.role) or "Software Engineer"
        if not company:
            raise ValueError("company is required")

        initial_state: InterviewAgentState = {
            "operation": request.operation,
            "company": company,
            "role": role,
            "max_sources": request.max_sources,
            "max_questions": request.max_questions,
            "use_firecrawl": request.use_firecrawl,
            "include_deep_research": request.include_deep_research,
            "target_length_words": request.target_length_words,
            "candidate_background": request.candidate_background,
            "candidate_response": request.candidate_response,
            "session_id": request.session_id,
            "raw_questions": [],
            "validated_questions": [],
            "questions_with_solutions": [],
            "sources_scraped": 0,
            "company_research": {},
            "research_report": "",
            "practice_events": [],
            "errors": [],
        }

        final_state: InterviewAgentState = await self._graph.ainvoke(initial_state)

        questions: list[UnifiedQuestion] | None = None
        if request.operation in {"collect_questions", "deep_research"}:
            questions = []
            for q in final_state.get("questions_with_solutions") or []:
                try:
                    questions.append(UnifiedQuestion.model_validate(q))
                except Exception:
                    continue

        interviewer_response: str | None = None
        if request.operation == "practice_session":
            # The panel simulator returns events including the next question after an answer.
            for evt in reversed(final_state.get("practice_events") or []):
                if (evt.get("type") == "question") and _safe_text(evt.get("text")):
                    interviewer_response = _safe_text(evt.get("text"))
                    break

        key_insights = (
            _extract_company_key_insights(final_state.get("company_research") or {})
            if request.operation == "deep_research"
            else None
        )

        return UnifiedInterviewResponse(
            operation=request.operation,
            questions=questions,
            sources_scraped=final_state.get("sources_scraped"),
            research_report=final_state.get("research_report") or None
            if request.operation == "deep_research"
            else None,
            key_insights=key_insights,
            session_id=final_state.get("session_id"),
            interviewer_response=interviewer_response,
            feedback=None,
            metadata={
                "errors": list(final_state.get("errors") or []),
                "total_questions_collected": len(final_state.get("raw_questions") or []),
                "validated_count": len(final_state.get("validated_questions") or []),
            },
        )


__all__ = ["UnifiedInterviewAgent"]
