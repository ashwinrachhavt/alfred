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
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from langchain.chat_models import init_chat_model
from sqlmodel import Session, select

from alfred.core.settings import settings
from alfred.core.utils import utcnow as _utcnow
from alfred.models.company import ResearchReportRow
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
        model_name: str | None = None,
    ) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        """Stream a research run as (event_name, data, sse_string) tuples."""
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        final_files: dict[str, str] = {}
        last_todos: list[dict[str, Any]] = []
        main_tokens: list[str] = []
        had_error = False
        # deepagents namespaces each sub-agent with a UUID (`tools:<uuid>`).
        # We learn the human name from messages tagged with `name=` on the
        # sub-agent's model output, then decorate subsequent events.
        subagent_names: dict[str, str] = {}

        try:
            inputs = {"messages": [{"role": "user", "content": topic}]}

            async for chunk in agent.astream(
                inputs,
                stream_mode=["updates", "messages", "custom"],
                subgraphs=True,
                version="v2",
            ):
                async for translated in self._translate_chunk(
                    chunk, last_todos, final_files, subagent_names
                ):
                    event_name, data, _sse_str = translated
                    if event_name == "token":
                        content = data.get("content")
                        if isinstance(content, str):
                            main_tokens.append(content)
                    yield translated

        except Exception as exc:
            had_error = True
            logger.exception("DeepResearchService.stream_run failed")
            err = {"message": f"{type(exc).__name__}: {exc!s}"}
            yield ("error", err, _sse("error", err))

        if not had_error:
            self._ensure_final_report_file(final_files, "".join(main_tokens))

        report_id = self._persist_final_report(
            topic=topic,
            final_files=final_files,
            model_name=model_name,
        )
        done = {
            "run_id": run_id,
            "thread_id": str(thread_id or ""),
            "final_files": final_files,
            "report_id": report_id,
        }
        yield ("done", done, _sse("done", done))

    def _ensure_final_report_file(
        self,
        final_files: dict[str, str],
        fallback_markdown: str,
    ) -> None:
        """Guarantee a persistable final report when the model streamed text directly."""
        if self._final_report_markdown(final_files):
            return
        markdown = fallback_markdown.strip()
        if not markdown:
            return
        final_files["/final_report.md"] = markdown

    def _final_report_markdown(self, final_files: dict[str, str]) -> str:
        return (
            final_files.get("/final_report.md")
            or final_files.get("final_report.md")
            or ""
        ).strip()

    def _persist_final_report(
        self,
        *,
        topic: str,
        final_files: dict[str, str],
        model_name: str | None = None,
    ) -> str | None:
        """Persist the streamed `/final_report.md` into the research reports table."""
        report_markdown = self._final_report_markdown(final_files)
        topic = (topic or "").strip()
        if not topic or not report_markdown or not isinstance(self.db, Session):
            return None

        payload = self._markdown_report_payload(
            topic=topic,
            markdown=report_markdown,
            final_files=final_files,
        )
        key = topic.lower()
        now = _utcnow()

        try:
            row = self.db.exec(
                select(ResearchReportRow).where(ResearchReportRow.topic_key == key)
            ).first()

            if row is None:
                row = ResearchReportRow(
                    topic_key=key,
                    topic=topic,
                    payload=payload,
                    model_name=model_name,
                    generated_at=now,
                    created_at=now,
                    updated_at=now,
                )
                self.db.add(row)
            else:
                row.topic = topic
                row.payload = payload
                row.model_name = model_name
                row.generated_at = now
                row.updated_at = now
                self.db.add(row)

            try:
                self.db.commit()
            except sa.exc.IntegrityError:
                self.db.rollback()
                row = self.db.exec(
                    select(ResearchReportRow).where(ResearchReportRow.topic_key == key)
                ).first()
                if row is None:
                    raise
                row.topic = topic
                row.payload = payload
                row.model_name = model_name
                row.generated_at = now
                row.updated_at = now
                self.db.add(row)
                self.db.commit()

            self.db.refresh(row)
            return str(row.id)
        except Exception:
            logger.exception("Failed to persist streamed deep research report")
            try:
                self.db.rollback()
            except Exception:
                logger.debug("Rollback failed after research report persist error", exc_info=True)
            return None

    def _markdown_report_payload(
        self,
        *,
        topic: str,
        markdown: str,
        final_files: dict[str, str],
    ) -> dict[str, Any]:
        now = datetime.now().astimezone().isoformat()
        summary = self._extract_markdown_summary(markdown)
        return {
            "topic": topic,
            "model": "deep-research-agent",
            "generated_at": now,
            "report": {
                "topic": topic,
                "executive_summary": summary,
                "sections": [],
                "risks": [],
                "opportunities": [],
                "recommended_actions": [],
                "references": [],
            },
            "sources": [],
            "markdown": markdown,
            "final_files": final_files,
            "source": "deep_research_stream",
        }

    def _extract_markdown_summary(self, markdown: str) -> str:
        lines = [line.strip() for line in markdown.splitlines()]
        paragraphs: list[str] = []
        current: list[str] = []
        for line in lines:
            if not line:
                if current:
                    paragraphs.append(" ".join(current).strip())
                    current = []
                continue
            if line.startswith(("#", "-", "*", "|", ">")):
                continue
            current.append(line)
            if len(" ".join(current)) > 240:
                break
        if current:
            paragraphs.append(" ".join(current).strip())
        return paragraphs[0][:700] if paragraphs else markdown[:700].strip()

    async def _translate_chunk(
        self,
        chunk: dict[str, Any],
        last_todos: list[dict[str, Any]],
        final_files: dict[str, str],
        subagent_names: dict[str, str],
    ) -> AsyncIterator[tuple[str, dict[str, Any], str]]:
        """Translate one deepagents stream chunk into zero or more SSE events."""
        ctype = chunk.get("type")
        ns = chunk.get("ns") or []
        subagent_uuid = next(
            (n.split(":", 1)[1] for n in ns if isinstance(n, str) and n.startswith("tools:")),
            None,
        )
        subagent_name: str | None = (
            subagent_names.get(subagent_uuid) if subagent_uuid else None
        )
        is_subagent = subagent_uuid is not None

        if ctype == "updates":
            for node_name, update in (chunk.get("data") or {}).items():
                # Learn the human name for this sub-agent UUID. deepagents
                # tags each sub-agent's model output with msg.name == spec.name.
                if subagent_uuid and subagent_uuid not in subagent_names:
                    if isinstance(update, dict) and "messages" in update:
                        msgs = update["messages"]
                        msg_list = msgs if isinstance(msgs, list) else [msgs]
                        for msg in msg_list:
                            nm = getattr(msg, "name", None)
                            if isinstance(nm, str) and nm and nm != "tools":
                                subagent_names[subagent_uuid] = nm
                                subagent_name = nm
                                break

                if isinstance(update, dict) and "todos" in update:
                    todos = update["todos"]
                    if isinstance(todos, list) and todos != last_todos:
                        last_todos[:] = todos
                        data = {"todos": todos}
                        yield ("plan", data, _sse("plan", data))

                if isinstance(update, dict) and "files" in update:
                    files = update["files"] or {}
                    if isinstance(files, dict):
                        for path, raw in files.items():
                            # deepagents >=0.5 stores each file as
                            # {"content": "...", "encoding": "utf-8",
                            #  "created_at": "...", "modified_at": "..."}
                            # Older versions stored the string directly.
                            if isinstance(raw, dict):
                                text = raw.get("content")
                                if not isinstance(text, str):
                                    text = ""
                            elif isinstance(raw, str):
                                text = raw
                            else:
                                text = ""
                            if final_files.get(path) != text:
                                final_files[path] = text
                                data = {"path": path, "bytes": len(text)}
                                yield ("file_write", data, _sse("file_write", data))

                # Tool execution complete: the `tools` node emits ToolMessage
                # instances whose tool_call_id matches the call_id we sent in
                # tool_start. Translate each into a tool_result event.
                if node_name == "tools" and isinstance(update, dict) and "messages" in update:
                    msgs = update["messages"]
                    msg_list = msgs if isinstance(msgs, list) else [msgs]
                    for msg in msg_list:
                        tcid = getattr(msg, "tool_call_id", None)
                        if not tcid:
                            continue
                        raw_content = getattr(msg, "content", "")
                        # Try to parse JSON results into structured data for the UI.
                        parsed: Any = raw_content
                        if isinstance(raw_content, str):
                            try:
                                parsed = json.loads(raw_content)
                            except (ValueError, TypeError):
                                parsed = raw_content
                        tr_data = {
                            "call_id": tcid,
                            "tool": getattr(msg, "name", None),
                            "result": parsed,
                            "subagent": subagent_name,
                        }
                        yield ("tool_result", tr_data, _sse("tool_result", tr_data))

                if node_name in ("model_request", "tools", "agent"):
                    data = {"node": node_name, "subagent": subagent_name}
                    yield ("task_start", data, _sse("task_start", data))

        elif ctype == "messages":
            token, _metadata = chunk.get("data", (None, None))
            if token is None:
                return
            # Suppress ToolMessage tokens — they're echoes of tool results that
            # we already surface via the `tool_result` event above. Leaking them
            # into `token`/`subagent_msg` floods the UI with raw JSON.
            token_type = type(token).__name__
            if token_type == "ToolMessage":
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
