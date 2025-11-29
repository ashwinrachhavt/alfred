from __future__ import annotations

import json
import re
from typing import Any, Optional, TypedDict

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
        # Prefer DSPy pipeline if available
        import importlib.util
        if importlib.util.find_spec("dspy") is not None:
            try:
                return self._run_dspy(text=text, url=url, title=title)
            except Exception:
                pass
        # Avoid try/except around import: check availability first
        if importlib.util.find_spec("openai") is None:
            return self._heuristic(text, url=url, title=title)
        # Prefer a LangGraph multi-step pipeline; fallback to single-call JSON; else heuristics
        try:
            return self._run_langgraph(text=text, url=url, title=title)
        except Exception:
            try:
                return self._single_call_json(text=text, url=url, title=title)
            except Exception:
                return self._heuristic(text, url=url, title=title)

    # -----------------
    # LangGraph pipeline
    # -----------------
    def _run_langgraph(self, *, text: str, url: Optional[str], title: Optional[str]) -> EnrichmentResult:
        from langgraph.graph import StateGraph

        class GState(TypedDict, total=False):
            title: str
            url: str
            text: str
            summary: str
            topic_category: str
            highlights: list[dict[str, Any]]
            insights: list[dict[str, Any]]
            tags: list[str]
            topic_graph: dict[str, Any]
            domain_summary: str

        def _summary_node(state: GState) -> dict[str, Any]:
            sys = load_prompt("mind_palace", "system.md")
            prm = load_prompt("mind_palace", "summary.md").format(
                title=state.get("title", "Untitled"), url=state.get("url", "N/A"), text=state.get("text", "")
            )
            data = self._openai_json(system=sys, user=prm)
            return {
                "summary": data.get("summary") or "",
                "topic_category": data.get("topic_category") or "general",
            }

        def _highlights_node(state: GState) -> dict[str, Any]:
            sys = load_prompt("mind_palace", "system.md")
            prm = load_prompt("mind_palace", "highlights.md").format(
                title=state.get("title", "Untitled"), url=state.get("url", "N/A"), text=state.get("text", ""), summary=state.get("summary", "")
            )
            data = self._openai_json(system=sys, user=prm)
            return {"highlights": data.get("highlights") or []}

        def _insights_node(state: GState) -> dict[str, Any]:
            sys = load_prompt("mind_palace", "system.md")
            prm = load_prompt("mind_palace", "insights.md").format(
                title=state.get("title", "Untitled"), url=state.get("url", "N/A"), text=state.get("text", ""), summary=state.get("summary", "")
            )
            data = self._openai_json(system=sys, user=prm)
            return {"insights": data.get("insights") or []}

        def _tags_node(state: GState) -> dict[str, Any]:
            sys = load_prompt("mind_palace", "system.md")
            prm = load_prompt("mind_palace", "tags.md").format(
                title=state.get("title", "Untitled"), url=state.get("url", "N/A"), text=state.get("text", ""), summary=state.get("summary", "")
            )
            data = self._openai_json(system=sys, user=prm)
            return {
                "tags": data.get("tags") or [],
                "topic_graph": data.get("topic_graph") or {"primary_node": None, "related_nodes": []},
            }

        def _domain_node(state: GState) -> dict[str, Any]:
            sys = load_prompt("mind_palace", "system.md")
            prm = load_prompt("mind_palace", "domain.md").format(
                title=state.get("title", "Untitled"), url=state.get("url", "N/A"), text=state.get("text", ""), summary=state.get("summary", "")
            )
            data = self._openai_json(system=sys, user=prm)
            return {"domain_summary": data.get("domain_summary") or ""}

        g = StateGraph(GState)
        g.add_node("summary", _summary_node)
        g.add_node("highlights", _highlights_node)
        g.add_node("insights", _insights_node)
        g.add_node("tags", _tags_node)
        g.add_node("domain", _domain_node)
        g.set_entry_point("summary")
        g.add_edge("summary", "highlights")
        g.add_edge("highlights", "insights")
        g.add_edge("insights", "tags")
        g.add_edge("tags", "domain")
        graph = g.compile()
        state: GState = {
            "title": title or "Untitled",
            "url": url or "N/A",
            "text": text,
        }
        result = graph.invoke(state)
        # Pull values with defaults
        topic_graph = result.get("topic_graph") or {"primary_node": None, "related_nodes": []}
        return EnrichmentResult(
            topic_category=result.get("topic_category") or "general",
            summary=result.get("summary") or "",
            highlights=list(result.get("highlights") or []),
            insights=list(result.get("insights") or []),
            domain_summary=result.get("domain_summary") or None,
            tags=list(result.get("tags") or []),
            topic_graph=topic_graph,
            model_name=settings.openai_model,
            prompt_version="v2-langgraph",
            temperature=0.2,
        )

    # -----------------
    # Single-call JSON (fallback)
    # -----------------
    def _single_call_json(self, *, text: str, url: Optional[str], title: Optional[str]) -> EnrichmentResult:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        system = load_prompt("mind_palace", "system.md")
        enrich = load_prompt("mind_palace", "enrich.md").format(title=title or "Untitled", url=url or "N/A", text=text[:12000])
        resp = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": enrich}],
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

    # -----------------
    # OpenAI JSON helper
    # -----------------
    def _openai_json(self, *, system: str, user: str) -> dict[str, Any]:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model or "gpt-4o-mini",
            temperature=0.2,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
        )
        content = (resp.choices[0].message.content or "").strip()
        return json.loads(content)

    # -----------------
    # DSPy pipeline (optional)
    # -----------------
    def _run_dspy(self, *, text: str, url: Optional[str], title: Optional[str]) -> EnrichmentResult:
        import dspy

        # Configure DSPy LM with OpenAI
        dspy.settings.configure(lm=dspy.OpenAI(model=settings.openai_model or "gpt-4o-mini", api_key=settings.openai_api_key))

        class SummSig(dspy.Signature):
            """Summarize page and pick topic_category."""
            title = dspy.InputField(desc="page title")
            url = dspy.InputField(desc="page url")
            text = dspy.InputField(desc="page text")
            summary = dspy.OutputField(desc="5-10 sentences summary")
            topic_category = dspy.OutputField(desc="short topic label")

        class HighlightsSig(dspy.Signature):
            """Return JSON array of highlights objects with bullet, importance, section_hint."""
            title = dspy.InputField()
            url = dspy.InputField()
            text = dspy.InputField()
            summary = dspy.InputField()
            highlights_json = dspy.OutputField(desc="JSON array as string")

        class InsightsSig(dspy.Signature):
            """Return JSON array of insights objects with statement, type, est_novelty."""
            title = dspy.InputField()
            url = dspy.InputField()
            text = dspy.InputField()
            summary = dspy.InputField()
            insights_json = dspy.OutputField(desc="JSON array as string")

        class TagsSig(dspy.Signature):
            """Return JSON with tags array and topic_graph object."""
            title = dspy.InputField()
            url = dspy.InputField()
            text = dspy.InputField()
            summary = dspy.InputField()
            tags_topic_graph_json = dspy.OutputField(desc="JSON object as string")

        class DomainSig(dspy.Signature):
            """Return JSON with domain_summary field."""
            title = dspy.InputField()
            url = dspy.InputField()
            text = dspy.InputField()
            summary = dspy.InputField()
            domain_json = dspy.OutputField(desc="JSON object as string")

        summarize = dspy.Predict(SummSig)
        highlights = dspy.Predict(HighlightsSig)
        insights = dspy.Predict(InsightsSig)
        tags = dspy.Predict(TagsSig)
        domain = dspy.Predict(DomainSig)

        # Run pipeline
        s = summarize(title=title or "Untitled", url=url or "N/A", text=text[:12000])
        summary = (s.summary or "").strip()
        topic_category = (s.topic_category or "general").strip()

        h = highlights(title=title or "Untitled", url=url or "N/A", text=text[:12000], summary=summary)
        i = insights(title=title or "Untitled", url=url or "N/A", text=text[:12000], summary=summary)
        t = tags(title=title or "Untitled", url=url or "N/A", text=text[:12000], summary=summary)
        d = domain(title=title or "Untitled", url=url or "N/A", text=text[:12000], summary=summary)

        def _safe_json(s: Any, default: Any) -> Any:
            try:
                return json.loads(str(s))
            except Exception:
                return default

        highlights_arr = _safe_json(getattr(h, "highlights_json", "[]"), [])
        insights_arr = _safe_json(getattr(i, "insights_json", "[]"), [])
        tags_obj = _safe_json(getattr(t, "tags_topic_graph_json", "{}"), {})
        domain_obj = _safe_json(getattr(d, "domain_json", "{}"), {})

        return EnrichmentResult(
            topic_category=topic_category or "general",
            summary=summary,
            highlights=list(highlights_arr or []),
            insights=list(insights_arr or []),
            domain_summary=domain_obj.get("domain_summary"),
            tags=list((tags_obj.get("tags") or [])),
            topic_graph=tags_obj.get("topic_graph") or {"primary_node": None, "related_nodes": []},
            model_name=settings.openai_model,
            prompt_version="v3-dspy",
            temperature=0.2,
        )

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
