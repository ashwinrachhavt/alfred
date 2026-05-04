"""DeepResearchService -- build and stream deep research agents.

Wraps deepagents.create_deep_agent with Alfred-specific plumbing:
persisted specs, tool registry, connector bindings, and event translation
into the SSE shape used by the existing /api/agent/stream route.

+-------------------------------------------------------------------+
| STREAM EVENT SHAPE (wire format for frontend research-store.ts)   |
|                                                                   |
| event: plan          {"todos": [{"content":..., "status":...}]}   |
| event: task_start    {"node":"tools","subagent":"researcher"}     |
| event: task_done     {"node":"tools","subagent":"researcher"}     |
| event: subagent_msg  {"subagent":"...","content":"..."}           |
| event: file_write    {"path":"/final_report.md","bytes":1234}     |
| event: tool_start    {"call_id":"...","tool":"search_web","args"} |
| event: tool_result   {"call_id":"...","result":{...}}             |
| event: token         {"content":"..."}                            |
| event: done          {"thread_id":"","final_files":{...}}         |
| event: error         {"message":"..."}                            |
+-------------------------------------------------------------------+
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from langchain.chat_models import init_chat_model
from sqlmodel import Session, select

from alfred.core.settings import settings
from alfred.models.research_agent import ResearchAgentSpecRow
from alfred.schemas.research_agent import (
    ResearchAgentSpecCreate,
    SubAgentSpec,
)
from alfred.services.deep_research.registry import get_tool_registry

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai:gpt-5.2"


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


class DeepResearchService:
    """Build a deepagent from a spec and stream events for a run."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._registry = get_tool_registry()

    def load_spec(self, spec_id: int) -> ResearchAgentSpecRow:
        row = self.db.get(ResearchAgentSpecRow, spec_id)
        if row is None:
            raise ValueError(f"ResearchAgentSpec id={spec_id} not found")
        return row

    def load_spec_by_slug(self, slug: str) -> ResearchAgentSpecRow:
        row = self.db.exec(
            select(ResearchAgentSpecRow).where(ResearchAgentSpecRow.slug == slug)
        ).first()
        if row is None:
            raise ValueError(f"ResearchAgentSpec slug={slug} not found")
        return row

    def build_agent(self, spec: ResearchAgentSpecRow | ResearchAgentSpecCreate) -> Any:
        """Compile a deepagent graph from a spec. Returns a runnable with .astream."""
        from deepagents import create_deep_agent

        tools = self._registry.resolve(list(spec.tool_allowlist or []))
        model_name = spec.model_name or settings.llm_model or DEFAULT_MODEL
        model = init_chat_model(model_name, temperature=0.0)

        subagent_dicts = [
            self._build_subagent(sa if isinstance(sa, SubAgentSpec) else SubAgentSpec(**sa))
            for sa in (spec.subagents or [])
        ]

        return create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=spec.instructions or self._default_orchestrator_prompt(),
            subagents=subagent_dicts,
        )

    def _build_subagent(self, sa: SubAgentSpec) -> dict[str, Any]:
        """Convert a SubAgentSpec to the dict shape deepagents expects."""
        out: dict[str, Any] = {
            "name": sa.name,
            "description": sa.description,
            "system_prompt": sa.system_prompt,
            "tools": self._registry.resolve(sa.tools),
        }
        if sa.model:
            out["model"] = init_chat_model(sa.model, temperature=0.0)
        return out

    async def stream_run(
        self,
        *,
        agent: Any,
        topic: str,
        thread_id: int | None = None,
    ) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        """Stream a research run as (event_name, data, sse_string) tuples."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        final_files: dict[str, str] = {}
        last_todos: list[dict[str, Any]] = []

        try:
            inputs = {"messages": [{"role": "user", "content": topic}]}

            async for chunk in agent.astream(
                inputs,
                stream_mode=["updates", "messages", "custom"],
                subgraphs=True,
                version="v2",
            ):
                async for translated in self._translate_chunk(chunk, last_todos, final_files):
                    yield translated

        except Exception as exc:
            logger.exception("DeepResearchService.stream_run failed")
            err = {"message": f"{type(exc).__name__}: {exc!s}"}
            yield ("error", err, _sse("error", err))

        done = {
            "run_id": run_id,
            "thread_id": str(thread_id or ""),
            "final_files": final_files,
        }
        yield ("done", done, _sse("done", done))

    async def _translate_chunk(
        self,
        chunk: dict[str, Any],
        last_todos: list[dict[str, Any]],
        final_files: dict[str, str],
    ) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        """Translate one deepagents stream chunk into zero or more SSE events."""
        ctype = chunk.get("type")
        ns = chunk.get("ns") or []
        subagent_name = next(
            (n.split(":", 1)[1] for n in ns if isinstance(n, str) and n.startswith("tools:")),
            None,
        )
        is_subagent = subagent_name is not None

        if ctype == "updates":
            for node_name, update in (chunk.get("data") or {}).items():
                if isinstance(update, dict) and "todos" in update:
                    todos = update["todos"]
                    if isinstance(todos, list) and todos != last_todos:
                        last_todos[:] = todos
                        data = {"todos": todos}
                        yield ("plan", data, _sse("plan", data))

                if isinstance(update, dict) and "files" in update:
                    files = update["files"] or {}
                    if isinstance(files, dict):
                        for path, content in files.items():
                            if final_files.get(path) != content:
                                final_files[path] = content
                                data = {
                                    "path": path,
                                    "bytes": len(content) if isinstance(content, str) else 0,
                                }
                                yield ("file_write", data, _sse("file_write", data))

                if node_name in ("model_request", "tools", "agent"):
                    data = {"node": node_name, "subagent": subagent_name}
                    yield ("task_start", data, _sse("task_start", data))

        elif ctype == "messages":
            token, _metadata = chunk.get("data", (None, None))
            if token is None:
                return
            content = getattr(token, "content", None)
            if content:
                if is_subagent:
                    data = {"subagent": subagent_name, "content": content}
                    yield ("subagent_msg", data, _sse("subagent_msg", data))
                else:
                    data = {"content": content}
                    yield ("token", data, _sse("token", data))

            tool_calls = getattr(token, "tool_calls", None) or []
            for tc in tool_calls:
                ts_data = {
                    "call_id": tc.get("id") or f"call_{uuid.uuid4().hex[:8]}",
                    "tool": tc.get("name"),
                    "args": tc.get("args") or {},
                    "subagent": subagent_name,
                }
                yield ("tool_start", ts_data, _sse("tool_start", ts_data))

        elif ctype == "custom":
            data = {"payload": chunk.get("data"), "subagent": subagent_name}
            yield ("custom", data, _sse("custom", data))

    def _default_orchestrator_prompt(self) -> str:
        return (
            "You are Alfred's deep research orchestrator.\n\n"
            "For each research request:\n"
            "1. Use write_todos to break the request into 3-6 focused research tasks.\n"
            "2. Delegate each task to the appropriate subagent via the task tool.\n"
            "3. Launch independent subagents in parallel when tasks do not depend on each other.\n"
            "4. Synthesize findings and write the final report to /final_report.md.\n"
            "5. Cite sources inline using [1], [2] format. Consolidate duplicates.\n"
            "Be rigorous. Prefer primary sources. Flag uncertainty explicitly."
        )
