from __future__ import annotations

import json
import re
from typing import Any, Optional

from alfred.core.config import settings
from alfred.prompts import load_prompt
from alfred.services.mind_palace.models import EnrichmentResult


class EnrichmentService:
    """Turns raw page text into structured Mind Palace fields.

    If `OPENAI_API_KEY` is set, attempts a structured JSON LLM call. Otherwise
    falls back to deterministic heuristics. This keeps the service usable in
    dev/CI without external dependencies.
    """

    def run(self, *, raw_text: str, url: Optional[str], title: Optional[str]) -> EnrichmentResult:
        text = (raw_text or "").strip()
        if not text:
            return self._empty_result()
        if not settings.openai_api_key:
            return self._heuristic(text, url=url, title=title)
        # Avoid try/except around import: check availability first
        import importlib.util
        if importlib.util.find_spec("openai") is None:
            return self._heuristic(text, url=url, title=title)
        from openai import OpenAI

        try:
            client = OpenAI(api_key=settings.openai_api_key)
            system = load_prompt("mind_palace", "system.md")
            enrich = load_prompt("mind_palace", "enrich.md").format(
                title=title or "Untitled",
                url=url or "N/A",
                text=text[:12000],
            )
            resp = client.chat.completions.create(
                model=settings.openai_model or "gpt-4o-mini",
                temperature=0.2,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": enrich},
                ],
                response_format={"type": "json_object"},
            )
            content = (resp.choices[0].message.content or "").strip()
            data = json.loads(content)
            return EnrichmentResult(
                topic_category=data.get("topic_category") or "general",
                summary=data.get("summary"),
                highlights=list(data.get("highlights") or []),
                insights=list(data.get("insights") or []),
                domain_summary=data.get("domain_summary"),
                tags=list(data.get("tags") or []),
                topic_graph=data.get("topic_graph") or {"primary_node": None, "related_nodes": []},
                model_name=settings.openai_model,
                prompt_version="v1",
                temperature=0.2,
            )
        except Exception:
            return self._heuristic(text, url=url, title=title)

    # -----------------
    # Heuristic helpers
    # -----------------
    def _empty_result(self) -> EnrichmentResult:
        return EnrichmentResult(
            topic_category="general",
            summary="(empty)",
            highlights=[],
            insights=[],
            domain_summary=None,
            tags=[],
            topic_graph={"primary_node": None, "related_nodes": []},
            model_name=None,
            prompt_version="v1",
            temperature=None,
        )

    def _first_sentences(self, text: str, n: int = 5) -> str:
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return " ".join(parts[:n]).strip()

    def _extract_bullets(self, text: str, limit: int = 8) -> list[dict[str, Any]]:
        bullets: list[dict[str, Any]] = []
        for line in text.splitlines():
            line_str = line.strip()
            if line_str.startswith("-") or line_str.startswith("*"):
                bullets.append({
                    "bullet": line_str.lstrip("-* ").strip(),
                    "importance": "medium",
                    "section_hint": None,
                })
            if len(bullets) >= limit:
                break
        return bullets

    def _heuristic(self, text: str, *, url: Optional[str], title: Optional[str]) -> EnrichmentResult:
        summary = self._first_sentences(text, 5) or (text[:400] + ("…" if len(text) > 400 else ""))
        highlights = self._extract_bullets(text)
        if not highlights:
            for s in self._first_sentences(text, 4).split(". "):
                s = s.strip().rstrip(".")
                if s:
                    highlights.append({"bullet": s, "importance": "low", "section_hint": None})
                if len(highlights) >= 5:
                    break
        primary = None
        if title:
            primary = title.split(" - ")[0][:60]
        # naive tags: derive from title words
        tags: list[str] = []
        base = (title or "") + " " + summary
        for w in re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,20}", base):
            token = w.lower().strip("-_ ")
            token = token.replace("-", "_")
            if token and token not in tags:
                tags.append(token)
            if len(tags) >= 6:
                break
        return EnrichmentResult(
            topic_category="general",
            summary=summary,
            highlights=highlights,
            insights=[],
            domain_summary=None,
            tags=tags,
            topic_graph={"primary_node": primary, "related_nodes": []},
            model_name="heuristic",
            prompt_version="v1",
            temperature=None,
        )
