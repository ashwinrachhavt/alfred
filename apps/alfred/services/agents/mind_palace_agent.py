"""Mind Palace Knowledge Agent service.

Provides a natural-language interface to converse with MongoDB-backed
documents and notes using a lightweight search over DocStorageService.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from alfred.schemas import AgentResponse, ChatMessage
from alfred.services.doc_storage import DocStorageService


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

    Currently performs a lightweight search over notes/documents with
    the DocStorageService.
    """

    doc_service: DocStorageService | None = None
    # Back-compat parameter; ignored now that MCP is removed
    mcp_client: Any | None = None

    def __post_init__(self) -> None:
        if self.doc_service is None:
            self.doc_service = DocStorageService()

    async def ask(
        self,
        *,
        question: str,
        history: Optional[List[ChatMessage]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentResponse:
        # Lightweight search over documents only
        return await self._fallback_answer(question)

    async def _fallback_answer(self, question: str) -> AgentResponse:
        # Lightweight search over documents collection only
        q = question.strip().split(" ")[0] if question.strip() else ""
        docs = self.doc_service.list_documents(q=q, skip=0, limit=5)
        items = docs.get("items", [])
        summary = _summarize_items(items)
        return AgentResponse(answer=summary, sources=items, meta={"mode": "fallback"})

    # MCP/LangGraph paths removed.
