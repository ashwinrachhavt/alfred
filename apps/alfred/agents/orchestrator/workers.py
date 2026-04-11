"""Worker wrappers for Alfred's orchestrator graph."""

from __future__ import annotations

from functools import lru_cache

from langchain_core.messages import BaseMessage, HumanMessage

from alfred.agents.orchestrator.state import AlfredAgentState, TaskResult, TaskSpec
from alfred.agents.teams.knowledge_team import build_knowledge_team
from alfred.agents.teams.synthesis_team import build_synthesis_team
from alfred.core.settings import LLMProvider, settings


def _latest_user_text(state: AlfredAgentState) -> str:
    for message in reversed(state.get("messages", [])):
        if getattr(message, "type", None) == "human":
            return str(getattr(message, "content", "")).strip()
    return ""


def _build_worker_prompt(task: TaskSpec, state: AlfredAgentState) -> str:
    user_text = _latest_user_text(state)
    note_context = state.get("note_context") or {}

    parts = [
        f"You are Alfred's {task['agent']} worker.",
        f"Task objective: {task['objective']}",
        f"Original user request: {user_text}",
        "Work only within your specialty. If you cannot find grounded evidence, say so clearly.",
        "Return a concise answer with the strongest evidence you found.",
    ]

    lens = state.get("lens")
    if lens:
        parts.append(f"Active lens: {lens}. Respect that framing where it helps.")

    title = str(note_context.get("title") or "").strip()
    preview = str(note_context.get("content_preview") or "").strip()
    if title or preview:
        parts.append(f"Current note title: {title}")
        if preview:
            parts.append(f"Current note preview: {preview[:500]}")

    return "\n\n".join(part for part in parts if part)


@lru_cache(maxsize=8)
def _knowledge_graph(model_name: str) -> object:
    return build_knowledge_team(model=model_name)


@lru_cache(maxsize=8)
def _synthesis_graph(model_name: str) -> object:
    return build_synthesis_team(model=model_name)


def _extract_summary(result: dict) -> str:
    messages = result.get("messages") or []
    for message in reversed(messages):
        if isinstance(message, BaseMessage) and getattr(message, "content", None):
            return str(message.content).strip()
        if isinstance(message, dict) and message.get("content"):
            return str(message["content"]).strip()
    final_response = result.get("final_response")
    if final_response:
        return str(final_response).strip()
    return "No grounded result returned."


async def run_worker_task(*, task: TaskSpec, state: AlfredAgentState) -> TaskResult:
    """Invoke a specialist subgraph with an isolated context window."""

    model_name = state.get("model") or "gpt-5.4"
    prompt = _build_worker_prompt(task, state)
    if settings.app_env in {"test", "ci"} or (
        settings.llm_provider == LLMProvider.openai and not settings.openai_api_key
    ):
        return TaskResult(
            task_id=task["id"],
            agent=task["agent"],
            objective=task["objective"],
            summary=f"[stub:{task['agent']}] {prompt[:160]}",
            evidence=[],
            artifacts=[],
            related_cards=[],
            gaps=[],
            proposed_actions=[],
        )

    worker_input = {"messages": [HumanMessage(content=prompt)]}

    if task["agent"] in {"knowledge", "connection"}:
        graph = _knowledge_graph(model_name)
    else:
        graph = _synthesis_graph(model_name)

    result = await graph.ainvoke(worker_input)
    return TaskResult(
        task_id=task["id"],
        agent=task["agent"],
        objective=task["objective"],
        summary=_extract_summary(result),
        evidence=[],
        artifacts=[],
        related_cards=[],
        gaps=[],
        proposed_actions=[],
    )


__all__ = ["run_worker_task"]
