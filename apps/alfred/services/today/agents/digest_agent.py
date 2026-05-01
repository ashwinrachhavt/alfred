"""LLM-backed reflect-stage agent that writes a daily digest.

Bundles the day's entries + artifact_ref items (zettels created, captures
ingested, reviews completed) into a concise markdown summary. Stores the
result at ``ctx.artifacts["digest_md"]``. Catches its own exceptions so a
model failure does not abort the pipeline - on failure, ``digest_md``
stays empty, the error is recorded in ``ctx.artifacts["digest_error"]``,
and the pipeline moves on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlmodel import Session

from alfred.core.llm_factory import get_chat_model
from alfred.services.today.pipeline import DailyContext, DailyPipeline

_SYSTEM_PROMPT = (
    "You are Alfred's daily reflection. Given the user's knowledge work "
    "on a single day, produce a 4-8 bullet markdown summary. First bullet "
    "is a 1-line overview. Subsequent bullets call out what was done, what "
    "was learned, and one or two cross-connections worth noticing. No "
    "headers, no preamble, just bullets. Use plain markdown (-)."
)


@DailyPipeline.register(stage="reflect")
@dataclass
class DigestAgent:
    """Reflect-stage agent: writes a markdown digest of the day.

    Instantiated per-run by :class:`DailyPipeline` via ``DigestAgent(session=...)``.
    """

    session: Session

    def run(self, ctx: DailyContext) -> DailyContext:
        try:
            prompt = self._build_prompt(ctx)
            model = get_chat_model()
            response = model.invoke(
                [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ]
            )
            content = _extract_text(response)
            ctx.artifacts["digest_md"] = content.strip()
        except Exception as error:
            # Defensive: do NOT raise - keep the pipeline moving.
            ctx.artifacts["digest_md"] = ""
            ctx.artifacts.setdefault("digest_error", str(error))
        return ctx

    @staticmethod
    def _build_prompt(ctx: DailyContext) -> str:
        lines: list[str] = [f"Date: {ctx.entry_date.isoformat()} ({ctx.tz_name})"]

        todos = [e for e in ctx.entries if e.kind == "todo"]
        todos_done = [e for e in todos if e.status == "done"]
        notes = [e for e in ctx.entries if e.kind == "note"]
        learnings = [e for e in ctx.entries if e.kind == "learning"]

        if todos:
            lines.append("")
            lines.append(f"Todos ({len(todos_done)}/{len(todos)} done):")
            for todo in todos:
                marker = "[x]" if todo.status == "done" else "[ ]"
                lines.append(f"  {marker} {todo.title}")

        if notes:
            lines.append("")
            lines.append("Notes:")
            for note in notes:
                lines.append(f"  - {note.title}")

        if learnings:
            lines.append("")
            lines.append("Learnings:")
            for learning in learnings:
                lines.append(f"  - {learning.title}")

        if ctx.zettels_created:
            lines.append("")
            lines.append(f"Zettels created ({len(ctx.zettels_created)}):")
            for zettel in ctx.zettels_created[:15]:
                title = _artifact_title(zettel)
                lines.append(f"  - {title}")

        if ctx.captures:
            lines.append("")
            lines.append(f"Captures ({len(ctx.captures)}):")
            for capture in ctx.captures[:15]:
                title = _artifact_title(capture)
                lines.append(f"  - {title}")

        if ctx.reviews_completed:
            lines.append("")
            lines.append(f"Reviews completed: {len(ctx.reviews_completed)}")

        return "\n".join(lines)


def _artifact_title(item: Any) -> str:
    if isinstance(item, dict):
        title = item.get("title")
        if isinstance(title, str) and title:
            return title
    return "(untitled)"


def _extract_text(response: Any) -> str:
    """LangChain-style chat models usually expose ``.content``; fall back to str().

    Handles the three common response shapes:
    - ``.content`` is a plain string (OpenAI, Ollama, most providers)
    - ``.content`` is a list of content parts (structured/multi-modal responses)
    - No ``.content`` attribute at all (defensive fallback)
    """
    content = getattr(response, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and "text" in part:
                parts.append(str(part["text"]))
        return "".join(parts)
    return str(response)


__all__ = ["DigestAgent"]
