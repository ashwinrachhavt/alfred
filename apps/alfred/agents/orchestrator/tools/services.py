"""Phase 2 service tools — wrap existing Alfred services as LangChain tools.

Each factory function returns a LangChain tool backed by an existing service.
Services are instantiated via the cached dependency getters in core/dependencies.py,
so no DB session is needed for these tools.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool as lc_tool

logger = logging.getLogger(__name__)


def make_summarize_tool():
    """Create a summarize_content tool backed by SummarizationService."""

    @lc_tool
    def summarize_content(text: str, title: str = "", source_url: str = "") -> str:
        """Summarize text content. Returns JSON with short summary, bullets, and key points."""
        from alfred.core.dependencies import get_summarization_service

        svc = get_summarization_service()
        payload, doc_id = svc.summarize_text(
            text=text,
            title=title or None,
            source_url=source_url or None,
            store=False,
        )
        return json.dumps({
            "action": "summarized",
            "title": payload.title or title,
            "short": payload.short,
            "bullets": payload.bullets,
            "key_points": payload.key_points,
        })

    return summarize_content


def make_generate_diagram_tool():
    """Create a generate_diagram tool backed by ExcalidrawAgent."""

    @lc_tool
    def generate_diagram(prompt: str, canvas_context: str = "") -> str:
        """Generate an Excalidraw diagram from a natural language description. Returns JSON with elements."""
        from alfred.core.llm_factory import get_chat_model
        from alfred.services.excalidraw_agent import build_diagram_prompt, parse_diagram_response

        diagram_prompt = build_diagram_prompt(prompt, canvas_context or None)
        model = get_chat_model()
        response = model.invoke(diagram_prompt)
        content = response.content if hasattr(response, "content") else str(response)
        result = parse_diagram_response(content)
        return json.dumps({
            "action": "diagram_generated",
            "element_count": len(result.get("elements", [])),
            "description": result.get("description", ""),
            "elements": result.get("elements", []),
        })

    return generate_diagram


def make_create_plan_tool():
    """Create a create_plan tool backed by PlanningService."""

    @lc_tool
    def create_plan(goal: str, context: str = "", max_steps: int = 6) -> str:
        """Create a step-by-step execution plan for a goal. Returns JSON with steps."""
        from alfred.core.dependencies import get_planning_service

        svc = get_planning_service()
        plan = svc.create_plan(goal=goal, context=context or None, max_steps=max_steps)
        return json.dumps({
            "action": "plan_created",
            "goal": plan.goal,
            "steps": [{"step": s.step, "status": s.status} for s in plan.steps],
        })

    return create_plan


def make_edit_text_tool():
    """Create an edit_text tool backed by TextAssistService."""

    @lc_tool
    def edit_text(text: str, instruction: str, tone: str = "") -> str:
        """Edit text according to an instruction (e.g. 'make it more concise'). Returns the edited text."""
        from alfred.core.dependencies import get_text_assist_service

        svc = get_text_assist_service()
        result = svc.edit(text=text, instruction=instruction, tone=tone or None)
        return json.dumps({
            "action": "text_edited",
            "output": result.output,
            "language": result.language,
        })

    return edit_text


def make_autocomplete_tool():
    """Create an autocomplete tool backed by TextAssistService."""

    @lc_tool
    def autocomplete(text: str, tone: str = "", max_chars: int = 600) -> str:
        """Generate an autocomplete suggestion for the given text. Returns the completion."""
        from alfred.core.dependencies import get_text_assist_service

        svc = get_text_assist_service()
        result = svc.autocomplete(text=text, tone=tone or None, max_chars=max_chars)
        return json.dumps({
            "action": "autocompleted",
            "completion": result.completion,
            "language": result.language,
        })

    return autocomplete
