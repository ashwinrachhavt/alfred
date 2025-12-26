from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

from alfred.core.settings import LLMProvider, settings
from alfred.prompts import load_prompt
from alfred.schemas.writing import WritingPreset, WritingRequest
from alfred.services.llm_service import LLMService


@dataclass(frozen=True)
class WritingResult:
    preset_used: WritingPreset
    output: str


def _normalize_hostname(site_url: str) -> str:
    if not site_url.strip():
        return ""
    try:
        parsed = urlparse(site_url)
        host = (parsed.hostname or "").lower().strip()
        return host
    except Exception:  # pragma: no cover - defensive
        return ""


def _infer_preset_key(site_url: str) -> str:
    host = _normalize_hostname(site_url)
    if not host:
        return "generic"

    # Social
    if host.endswith("linkedin.com"):
        return "linkedin"
    if host.endswith("x.com") or host.endswith("twitter.com"):
        return "x"
    if host.endswith("reddit.com"):
        return "reddit"
    if host.endswith("news.ycombinator.com") or host.endswith("ycombinator.com"):
        return "hackernews"

    # Work
    if host.endswith("mail.google.com"):
        return "gmail"
    if host.endswith("github.com"):
        return "github"
    if host.endswith("notion.so"):
        return "notion"
    if host.endswith("slack.com"):
        return "slack"

    return "generic"


def list_writing_presets() -> list[WritingPreset]:
    return [
        WritingPreset(
            key="generic",
            title="General",
            description="Clean, minimal writing for most sites.",
            format="plain",
        ),
        WritingPreset(
            key="linkedin",
            title="LinkedIn",
            description="Professional, skimmable, confident; short paragraphs; no fluff.",
            format="plain",
        ),
        WritingPreset(
            key="x",
            title="X / Twitter",
            description="Punchy, direct; avoid hashtags; keep it tight.",
            max_chars=280,
            format="plain",
        ),
        WritingPreset(
            key="reddit",
            title="Reddit",
            description="Helpful and grounded; explain reasoning; be conversational, not salesy.",
            format="plain",
        ),
        WritingPreset(
            key="hackernews",
            title="Hacker News",
            description="Calm, factual, technical; minimal hype; acknowledge uncertainty.",
            format="plain",
        ),
        WritingPreset(
            key="gmail",
            title="Gmail",
            description="Professional email tone; concise; clear CTA.",
            format="plain",
        ),
        WritingPreset(
            key="github",
            title="GitHub",
            description="Concise and technical; prefer Markdown; crisp bullets when helpful.",
            format="markdown",
        ),
        WritingPreset(
            key="notion",
            title="Notion",
            description="Structured notes; concise headings and bullets; minimal verbosity.",
            format="markdown",
        ),
        WritingPreset(
            key="slack",
            title="Slack",
            description="Short, friendly, actionable; avoid long paragraphs.",
            format="plain",
        ),
    ]


def resolve_preset(*, site_url: str, preset: Optional[str]) -> WritingPreset:
    presets = {p.key: p for p in list_writing_presets()}
    key = (preset or "").strip().lower() or _infer_preset_key(site_url)
    return presets.get(key, presets["generic"])


def _preset_rules(preset: WritingPreset, *, max_chars: Optional[int]) -> str:
    budget = max_chars if max_chars is not None else preset.max_chars
    parts: list[str] = []

    if preset.key == "linkedin":
        parts.extend(
            [
                "LinkedIn style:",
                "- Start with a strong 1-line hook.",
                "- Use short paragraphs (1–2 lines).",
                "- Be confident and specific; remove filler.",
                "- Avoid hashtags unless the user explicitly asks.",
            ]
        )
    elif preset.key == "x":
        parts.extend(
            [
                "X/Twitter style:",
                "- Be punchy and specific.",
                "- Avoid hashtags unless requested.",
                "- No emojis unless the user used them first.",
            ]
        )
    elif preset.key == "reddit":
        parts.extend(
            [
                "Reddit style:",
                "- Be helpful and grounded.",
                "- Explain briefly why, not just what.",
                "- Avoid marketing language.",
            ]
        )
    elif preset.key == "hackernews":
        parts.extend(
            [
                "Hacker News style:",
                "- Be factual and technical.",
                "- Avoid hype; state assumptions.",
                "- Keep it concise; cite numbers only if known.",
            ]
        )
    elif preset.key == "gmail":
        parts.extend(
            [
                "Email style:",
                "- Short subject is not needed; output body only.",
                "- Keep it concise, polite, and direct.",
                "- End with a clear CTA.",
            ]
        )
    elif preset.key == "github":
        parts.extend(
            [
                "GitHub style:",
                "- Prefer Markdown.",
                "- Be concrete and actionable; include steps when relevant.",
                "- Avoid verbosity.",
            ]
        )
    elif preset.key == "notion":
        parts.extend(
            [
                "Notion style:",
                "- Prefer Markdown headings/bullets.",
                "- Be structured and scannable.",
            ]
        )
    elif preset.key == "slack":
        parts.extend(
            [
                "Slack style:",
                "- Keep it short and friendly.",
                "- Use bullets for multiple items.",
            ]
        )

    if budget is not None:
        parts.append(f"Hard limit: {int(budget)} characters (do not exceed).")

    if preset.format == "markdown":
        parts.append("Formatting: Markdown is allowed and preferred.")
    else:
        parts.append("Formatting: plain text (no Markdown) unless the user included Markdown.")

    return "\n".join(parts).strip()


def _use_stub_writing() -> bool:
    if os.getenv("ALFRED_WRITING_STUB") == "1":
        return True
    if settings.app_env in {"test", "ci"}:
        return True
    if settings.llm_provider == LLMProvider.openai and not settings.openai_api_key:
        return True
    return False


def _stub_output(req: WritingRequest, preset: WritingPreset) -> str:
    base = req.selection.strip() or req.draft.strip() or req.instruction.strip()
    if not base:
        base = "Write something clear and minimal."
    if preset.max_chars:
        base = base[: preset.max_chars]
    return base


def build_messages(req: WritingRequest, preset: WritingPreset) -> list[dict[str, str]]:
    system = load_prompt("writing", "system.md")
    rules = _preset_rules(preset, max_chars=req.max_chars)

    user_parts: list[str] = []
    if req.page_title.strip():
        user_parts.append(f"Page title: {req.page_title.strip()}")
    if req.site_url.strip():
        user_parts.append(f"Site URL: {req.site_url.strip()}")
    if req.page_text.strip():
        user_parts.append("Context (page excerpt):")
        user_parts.append(req.page_text.strip())
    if req.instruction.strip():
        user_parts.append("Instruction:")
        user_parts.append(req.instruction.strip())
    if req.selection.strip():
        user_parts.append("Selection:")
        user_parts.append(req.selection.strip())
    if req.draft.strip():
        user_parts.append("Draft:")
        user_parts.append(req.draft.strip())

    user_parts.append("Site rules:")
    user_parts.append(rules)

    user = "\n".join(user_parts).strip()

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def write(req: WritingRequest, *, llm: Optional[LLMService] = None) -> WritingResult:
    preset = resolve_preset(site_url=req.site_url, preset=req.preset)
    if _use_stub_writing():
        return WritingResult(preset_used=preset, output=_stub_output(req, preset))

    llm = llm or LLMService()
    messages = build_messages(req, preset)
    output = llm.chat(
        messages,
        temperature=req.temperature,
    )
    return WritingResult(preset_used=preset, output=output.strip())


def write_stream(
    req: WritingRequest, *, llm: Optional[LLMService] = None
) -> tuple[WritingPreset, Iterable[str]]:
    preset = resolve_preset(site_url=req.site_url, preset=req.preset)
    if _use_stub_writing():
        return preset, iter([_stub_output(req, preset)])

    llm = llm or LLMService()
    messages = build_messages(req, preset)
    stream = llm.chat_stream(
        messages,
        temperature=req.temperature,
    )
    return preset, stream


__all__ = [
    "WritingResult",
    "build_messages",
    "list_writing_presets",
    "resolve_preset",
    "write",
    "write_stream",
]
