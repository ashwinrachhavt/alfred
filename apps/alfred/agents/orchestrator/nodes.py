"""Node implementations for Alfred's orchestration graph."""

from __future__ import annotations

import re
import uuid
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.types import Send

from alfred.agents.orchestrator.state import (
    AgentKind,
    AlfredAgentState,
    ProposedAction,
    TaskMode,
    TaskResult,
    TaskSpec,
)
from alfred.agents.orchestrator.workers import run_worker_task
from alfred.core.llm_factory import get_chat_model
from alfred.core.settings import LLMProvider, settings

_KNOWLEDGE_PATTERNS = [
    re.compile(r"\bwhat do i know\b", re.I),
    re.compile(r"\bsearch\b.{0,20}\b(notes?|knowledge|zettels?|cards?)\b", re.I),
    re.compile(r"\bmy (notes|knowledge|zettels?|cards?)\b", re.I),
    re.compile(r"\b(note|zettel|card)\b", re.I),
]

_RESEARCH_PATTERNS = [
    re.compile(r"\b(latest|current|today|recent)\b", re.I),
    re.compile(r"\b(research|web|paper|papers|arxiv|scholar|external)\b", re.I),
    re.compile(r"\b(news|trend|market)\b", re.I),
]

_CONNECTION_PATTERNS = [
    re.compile(r"\b(connect|connection|relate|related|similar|pattern|link)\b", re.I),
    re.compile(r"\bcompare\b", re.I),
]

_DIRECT_CHAT_PATTERNS = [
    re.compile(r"^(hi|hello|hey|thanks?|thank you)\b", re.I),
    re.compile(r"^(what|who|where|when|why|how)\b.{0,80}\?$", re.I),
]

_LENS_PROMPTS: dict[str, str] = {
    "socratic": "Use probing questions to surface assumptions and sharpen the user's thinking.",
    "stoic": "Frame trade-offs around control, agency, and disciplined action.",
    "existentialist": "Emphasize responsibility, authentic choice, and uncertainty.",
    "utilitarian": "Evaluate options by consequences, trade-offs, and expected impact.",
    "kantian": "Favor principle-driven reasoning and consistency.",
    "virtue_ethics": "Focus on character, habit formation, and practical wisdom.",
    "eastern": "Emphasize balance, non-attachment, and interconnectedness.",
}


def _latest_user_message(state: AlfredAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "")).strip()
    return ""


def _should_stub_llm() -> bool:
    if settings.app_env in {"test", "ci"}:
        return True
    return settings.llm_provider == LLMProvider.openai and not settings.openai_api_key


def _make_task(
    *,
    agent: AgentKind,
    objective: str,
    context_refs: list[str] | None = None,
    mode: TaskMode = "read",
) -> TaskSpec:
    return TaskSpec(
        id=f"task_{uuid.uuid4().hex[:8]}",
        agent=agent,
        objective=objective,
        context_refs=context_refs or [],
        mode=mode,
        status="queued",
    )


def _matches_any(patterns: list[re.Pattern[str]], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _should_run_knowledge(text: str, *, note_context: dict[str, Any] | None, intent: str | None) -> bool:
    if intent in {"search_kb", "create", "learn"}:
        return True
    if note_context:
        return True
    return _matches_any(_KNOWLEDGE_PATTERNS, text)


def _should_run_research(text: str, *, intent: str | None) -> bool:
    if intent == "research":
        return True
    return _matches_any(_RESEARCH_PATTERNS, text)


def _should_run_connection(text: str, *, intent: str | None) -> bool:
    if intent == "connect":
        return True
    return _matches_any(_CONNECTION_PATTERNS, text)


def _is_direct_chat(text: str, *, note_context: dict[str, Any] | None) -> bool:
    if note_context:
        return False
    return _matches_any(_DIRECT_CHAT_PATTERNS, text)


def planner(state: AlfredAgentState) -> dict[str, Any]:
    """Plan specialist work for the current turn."""

    user_text = _latest_user_message(state)
    intent = state.get("intent")
    note_context = state.get("note_context")

    tasks: list[TaskSpec] = []
    if _should_run_knowledge(user_text, note_context=note_context, intent=intent):
        tasks.append(
            _make_task(
                agent="knowledge",
                objective=f"Search Alfred's knowledge base for evidence relevant to: {user_text}",
                context_refs=["messages", "note_context"] if note_context else ["messages"],
            )
        )

    if _should_run_research(user_text, intent=intent):
        tasks.append(
            _make_task(
                agent="research",
                objective=f"Research current and external sources relevant to: {user_text}",
                context_refs=["messages"],
            )
        )

    if _should_run_connection(user_text, intent=intent):
        tasks.append(
            _make_task(
                agent="connection",
                objective=f"Find related ideas, cards, or graph links relevant to: {user_text}",
                context_refs=["messages", "task_results"],
            )
        )

    if not tasks and not _is_direct_chat(user_text, note_context=note_context):
        tasks.append(
            _make_task(
                agent="knowledge",
                objective=f"Find the strongest internal Alfred context relevant to: {user_text}",
                context_refs=["messages", "note_context"] if note_context else ["messages"],
            )
        )

    return {
        "plan": tasks,
        "phase": "planning",
        "active_agents": [task["agent"] for task in tasks] or ["chat"],
    }


def route_after_planner(state: AlfredAgentState) -> str | list[Send]:
    """Either answer directly or fan out to worker nodes."""

    plan = state.get("plan") or []
    if not plan:
        return "direct_chat"

    shared = {
        "messages": state.get("messages", []),
        "thread_id": state.get("thread_id", ""),
        "user_id": state.get("user_id", ""),
        "model": state.get("model", ""),
        "lens": state.get("lens"),
        "note_context": state.get("note_context"),
        "intent": state.get("intent"),
        "intent_args": state.get("intent_args"),
    }
    return [Send("execute_task", {**shared, "current_task": task}) for task in plan]


def _build_chat_messages(
    *,
    state: AlfredAgentState,
    system_prompt: str,
) -> list[BaseMessage]:
    messages = list(state.get("messages", []))
    lens = state.get("lens")
    if lens and lens in _LENS_PROMPTS:
        system_prompt = f"{system_prompt}\n\nActive lens: {_LENS_PROMPTS[lens]}"
    note_context = state.get("note_context") or {}
    title = str(note_context.get("title") or "").strip()
    preview = str(note_context.get("content_preview") or "").strip()
    if title or preview:
        system_prompt = (
            f"{system_prompt}\n\nCurrent note context:\n"
            f"- Title: {title}\n"
            f"- Preview: {preview[:500]}"
        )
    return [SystemMessage(content=system_prompt), *messages]


def _fallback_chat_content(state: AlfredAgentState) -> str:
    text = _latest_user_message(state)
    return f"Alfred heard: {text}"


def _dedupe_list(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        value = str(item.get(key) or "")
        if value in seen:
            continue
        seen.add(value)
        deduped.append(item)
    return deduped


async def direct_chat(state: AlfredAgentState) -> dict[str, Any]:
    """Answer simple turns without delegating to specialist workers."""

    if _should_stub_llm():
        content = _fallback_chat_content(state)
    else:
        llm = get_chat_model(model=state.get("model") or "gpt-5.4")
        messages = _build_chat_messages(
            state=state,
            system_prompt=(
                "You are Alfred, a sharp knowledge companion. Answer directly, stay concise, "
                "and make the response useful without narrating your process."
            ),
        )
        response = await llm.ainvoke(messages)
        content = str(response.content).strip()

    return {
        "messages": [AIMessage(content=content)],
        "final_response": content,
        "phase": "done",
        "active_agents": ["chat"],
    }


async def execute_task(state: AlfredAgentState) -> dict[str, Any]:
    """Run one specialist task and normalize its output."""

    task = state.get("current_task")
    if not task:
        return {}

    result = await run_worker_task(task=task, state=state)
    return {
        "task_results": [result],
        "artifacts": result.get("artifacts", []),
        "related_cards": result.get("related_cards", []),
        "gaps": result.get("gaps", []),
    }


def gather_results(state: AlfredAgentState) -> dict[str, Any]:
    """Consolidate worker outputs and detect any proposed side effects."""

    proposed: list[ProposedAction] = []
    for result in state.get("task_results", []):
        proposed.extend(result.get("proposed_actions", []))

    return {
        "phase": "awaiting_approval" if proposed else "writing",
        "pending_approvals": proposed,
    }


def approval_gate(state: AlfredAgentState) -> dict[str, Any]:
    """Placeholder approval node for future interrupt-based write actions."""

    pending = state.get("pending_approvals", [])
    return {"phase": "awaiting_approval" if pending else "writing"}


def _render_result_markdown(result: TaskResult) -> str:
    header = result["agent"].title()
    summary = result.get("summary") or "No grounded result returned."
    return f"### {header}\n{summary.strip()}"


def _fallback_writer_content(state: AlfredAgentState) -> str:
    results = state.get("task_results", [])
    pending = state.get("pending_approvals", [])

    if not results and not pending:
        return "I processed your request, but I do not have a grounded result yet."

    blocks = [_render_result_markdown(result) for result in results]
    if pending:
        action_lines = [
            f"- `{action['action']}`: {action['reason']}"
            for action in pending
        ]
        blocks.append("### Proposed Actions\n" + "\n".join(action_lines))
    return "\n\n".join(blocks)


async def writer(state: AlfredAgentState) -> dict[str, Any]:
    """Turn worker outputs into the final assistant response."""

    if _should_stub_llm():
        content = _fallback_writer_content(state)
    else:
        llm = get_chat_model(model=state.get("model") or "gpt-5.4")
        results = "\n\n".join(_render_result_markdown(result) for result in state.get("task_results", []))
        pending = state.get("pending_approvals", [])
        pending_text = ""
        if pending:
            pending_text = "\n\nProposed actions requiring user approval:\n" + "\n".join(
                f"- {item['action']}: {item['reason']}" for item in pending
            )
        prompt = _build_chat_messages(
            state=state,
            system_prompt=(
                "You are Alfred's synthesizer. Combine specialist outputs into one crisp answer. "
                "Lead with the answer, surface useful distinctions, and mention any proposed side "
                "effects separately."
            ),
        )
        prompt.append(
            HumanMessage(
                content=(
                    "Synthesize the following specialist outputs into a single answer for the user.\n\n"
                    f"{results or 'No worker outputs were returned.'}{pending_text}"
                )
            )
        )
        response = await llm.ainvoke(prompt)
        content = str(response.content).strip()

    return {
        "messages": [AIMessage(content=content)],
        "final_response": content,
        "phase": "done",
        "artifacts": _dedupe_list(state.get("artifacts", []), "id"),
        "related_cards": _dedupe_list(state.get("related_cards", []), "zettel_id"),
        "gaps": _dedupe_list(state.get("gaps", []), "concept"),
    }


def finalizer(state: AlfredAgentState) -> dict[str, Any]:
    """Mark the turn complete and ensure a final response exists."""

    final_response = state.get("final_response")
    if not final_response:
        for message in reversed(state.get("messages", [])):
            if isinstance(message, AIMessage) and message.content:
                final_response = str(message.content)
                break

    return {
        "phase": "done",
        "final_response": final_response,
    }


__all__ = [
    "approval_gate",
    "direct_chat",
    "execute_task",
    "finalizer",
    "gather_results",
    "planner",
    "route_after_planner",
    "writer",
]
