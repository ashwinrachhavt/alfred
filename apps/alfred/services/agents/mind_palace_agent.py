"""Mind Palace Knowledge Agent service.

Provides a natural-language interface to converse with MongoDB-backed
documents and notes, optionally via a MongoDB Lens MCP server and LangGraph.

Design:
- Optional deps: LangGraph/LangChain are imported at runtime; if unavailable,
  the service falls back to a deterministic heuristic over DocStorageService.
- MongoDB Lens MCP is accessed via HTTP (see connectors.mongolens_client).
  If MCP is disabled or unreachable, the fallback is used.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime, timezone
from time import perf_counter

from alfred.core.config import settings
from alfred.schemas import AgentResponse, ChatMessage
from alfred.services.doc_storage import DocStorageService

try:  # Optional MCP client
    from alfred.connectors.mongolens_client import MongoLensMCPClient  # type: ignore
except Exception:  # pragma: no cover - optional
    MongoLensMCPClient = None  # type: ignore

logger = logging.getLogger(__name__)


def _summarize_items(items: List[Dict[str, Any]], *, limit: int = 5) -> str:
    lines = []
    for i, it in enumerate(items[:limit], start=1):
        title = it.get("title") or (it.get("text") or "").split("\n", 1)[0]
        src = it.get("source_url") or it.get("canonical_url") or ""
        lines.append(f"{i}. {title[:120]}{' — ' + src if src else ''}")
    if not lines:
        return "I couldn’t find anything relevant."
    return "Here’s what I found:\n" + "\n".join(lines)


@dataclass
class KnowledgeAgentService:
    """Coordinates tools to answer natural-language questions.

    If LangGraph and MCP are available, uses them. Otherwise, performs a
    lightweight search over notes/documents with the DocStorageService.
    """

    doc_service: DocStorageService | None = None
    mcp_client: Any | None = None

    def __post_init__(self) -> None:
        if self.doc_service is None:
            self.doc_service = DocStorageService()

        if self.mcp_client is None and settings.mcp_server_url:
            try:
                if MongoLensMCPClient is not None:
                    self.mcp_client = MongoLensMCPClient()
            except Exception as exc:  # pragma: no cover - optional path
                logger.info("MCP client initialization skipped: %s", exc)

    async def ask(
        self,
        *,
        question: str,
        history: Optional[List[ChatMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        # Prefer LangGraph + MCP if available and healthy
        if settings.enable_mcp and self.mcp_client is not None:
            lg_answer = await self._langgraph_answer(question=question, history=history or [], context=context or {})
            if lg_answer is not None:
                return lg_answer

        # Prefer MCP if configured and healthy (non-LangGraph path)
        if self.mcp_client is not None and settings.enable_mcp:
            healthy = False
            try:
                healthy = await self.mcp_client.health()
            except Exception:  # pragma: no cover - network
                healthy = False
            if healthy:
                try:
                    res = await self.mcp_client.query(
                        question, context={"history": [m.model_dump() for m in (history or [])], **(context or {})}
                    )
                    sources = res.get("results") if isinstance(res, dict) else []
                    if not isinstance(sources, list):
                        sources = [sources]
                    if sources:
                        answer = self._format_mcp_results({"results": sources})
                        return AgentResponse(answer=answer, sources=sources, meta={"mode": "mcp"})
                    # Empty results -> fall back
                    logger.info("MCP returned no results; falling back to documents search")
                except Exception as exc:  # pragma: no cover - network
                    logger.warning("MCP query failed, falling back: %s", exc)

        # Fallback: semantic-lite search over documents only
        return await self._fallback_answer(question)

    async def _fallback_answer(self, question: str) -> AgentResponse:
        # Lightweight search over documents collection only
        q = question.strip().split(" ")[0] if question.strip() else ""
        docs = self.doc_service.list_documents(q=q, skip=0, limit=5)
        items = docs.get("items", [])
        summary = _summarize_items(items)
        return AgentResponse(answer=summary, sources=items, meta={"mode": "fallback"})

    @staticmethod
    def _format_mcp_results(data: Dict[str, Any]) -> str:
        res = data.get("results") if isinstance(data, dict) else data
        if isinstance(res, list):
            return _summarize_items(res)
        return str(res)

    # -----------------
    # LangGraph workflow
    # -----------------
    async def _langgraph_answer(
        self,
        *,
        question: str,
        history: List[ChatMessage],
        context: Dict[str, Any],
    ) -> Optional[AgentResponse]:
        if self.mcp_client is None:
            return None
        try:
            from langgraph.graph import END, StateGraph  # type: ignore
        except Exception:
            return None

        class AgentState(TypedDict, total=False):
            question: str
            plan: str
            results: List[Dict[str, Any]]
            answer: str
            history: List[Dict[str, Any]]
            context: Dict[str, Any]
            _trace: List[Dict[str, Any]]

        async def planner_node(state: AgentState) -> AgentState:
            trace_enabled = bool(settings.enable_agent_trace)
            if trace_enabled:
                t0 = perf_counter()
                started_at = datetime.now(timezone.utc)
            q = state.get("question", "")
            plan = (
                "1) Identify key terms\n"
                "2) Query knowledge base via MCP\n"
                "3) Summarize top matches concisely"
            )
            if len(q.split()) > 12:
                plan += "\nNote: The question is long; prefer broader matching."
            out: AgentState = {"plan": plan}
            if trace_enabled:
                ended_at = datetime.now(timezone.utc)
                t1 = perf_counter()
                tr = state.get("_trace", []) or []
                tr.append(
                    {
                        "node": "planner",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": int((t1 - t0) * 1000),
                    }
                )
                out["_trace"] = tr
            return out

        async def retriever_node(state: AgentState) -> AgentState:
            trace_enabled = bool(settings.enable_agent_trace)
            if trace_enabled:
                t0 = perf_counter()
                started_at = datetime.now(timezone.utc)
            q = state.get("question", "")
            ctx = state.get("context", {})
            try:
                data = await self.mcp_client.query(q, context=ctx)
                results = data.get("results") if isinstance(data, dict) else []
                if not isinstance(results, list):
                    results = [results]
                out: AgentState = {"results": results}
                if trace_enabled:
                    ended_at = datetime.now(timezone.utc)
                    t1 = perf_counter()
                    tr = state.get("_trace", []) or []
                    tr.append(
                        {
                            "node": "retriever",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "duration_ms": int((t1 - t0) * 1000),
                        }
                    )
                    out["_trace"] = tr
                return out
            except Exception as exc:  # pragma: no cover - network
                logger.warning("LangGraph MCP query failed: %s", exc)
                out: AgentState = {"results": []}
                if trace_enabled:
                    ended_at = datetime.now(timezone.utc)
                    t1 = perf_counter()
                    tr = state.get("_trace", []) or []
                    tr.append(
                        {
                            "node": "retriever",
                            "started_at": started_at.isoformat(),
                            "ended_at": ended_at.isoformat(),
                            "duration_ms": int((t1 - t0) * 1000),
                            "error": str(exc),
                        }
                    )
                    out["_trace"] = tr
                return out

        async def summarizer_node(state: AgentState) -> AgentState:
            trace_enabled = bool(settings.enable_agent_trace)
            if trace_enabled:
                t0 = perf_counter()
                started_at = datetime.now(timezone.utc)
            results = state.get("results", []) or []
            answer = _summarize_items(results)
            out: AgentState = {"answer": answer}
            if trace_enabled:
                ended_at = datetime.now(timezone.utc)
                t1 = perf_counter()
                tr = state.get("_trace", []) or []
                tr.append(
                    {
                        "node": "summarizer",
                        "started_at": started_at.isoformat(),
                        "ended_at": ended_at.isoformat(),
                        "duration_ms": int((t1 - t0) * 1000),
                    }
                )
                out["_trace"] = tr
            return out

        graph = StateGraph(AgentState)
        graph.add_node("planner", planner_node)
        graph.add_node("retriever", retriever_node)
        graph.add_node("summarizer", summarizer_node)
        graph.set_entry_point("planner")
        graph.add_edge("planner", "retriever")
        graph.add_edge("retriever", "summarizer")
        graph.add_edge("summarizer", END)

        app = graph.compile()
        init: AgentState = {
            "question": question,
            "history": [m.model_dump() for m in history],
            "context": context,
        }
        try:
            final: AgentState = await app.ainvoke(init)  # type: ignore[attr-defined]
        except Exception as exc:  # pragma: no cover - runtime
            logger.warning("LangGraph execution failed: %s", exc)
            return None

        # If no results, signal caller to fall back
        results_list = final.get("results", []) or []
        if not results_list:
            return None

        meta: Dict[str, Any] = {"mode": "langgraph"}
        if settings.enable_agent_trace:
            trace_nodes = final.get("_trace", []) or []
            total_ms = sum(int(node.get("duration_ms", 0)) for node in trace_nodes)
            meta.update(
                {
                    "plan": final.get("plan", ""),
                    "trace": {
                        "nodes": trace_nodes,
                        "total_duration_ms": total_ms,
                    },
                }
            )

        return AgentResponse(
            answer=final.get("answer", ""),
            sources=results_list,
            meta=meta,
        )
