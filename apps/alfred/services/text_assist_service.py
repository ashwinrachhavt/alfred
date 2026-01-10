from __future__ import annotations

import logging
from dataclasses import dataclass

from alfred.core.settings import LLMProvider, settings
from alfred.schemas.intelligence import AutocompleteResponse, TextEditResponse
from alfred.services.language_service import LanguageService
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def _is_llm_configured() -> bool:
    if settings.llm_provider == LLMProvider.ollama:
        return True
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return bool(api_key or settings.openai_base_url)


def _clip_tail(text: str, *, max_chars: int) -> str:
    s = text or ""
    if len(s) <= max_chars:
        return s
    return s[-max_chars:]


@dataclass(slots=True)
class TextAssistService:
    """Lightweight text helpers: autocomplete + editing, with tone + language awareness."""

    llm_service: LLMService | None = None
    language_service: LanguageService | None = None

    def _llm(self) -> LLMService:
        return self.llm_service or LLMService()

    def _lang(self) -> LanguageService:
        return self.language_service or LanguageService()

    def autocomplete(
        self, *, text: str, tone: str | None = None, max_chars: int = 600
    ) -> AutocompleteResponse:
        if not _is_llm_configured():
            raise RuntimeError(
                "LLM is not configured (set OPENAI_API_KEY or use ALFRED_LLM_PROVIDER=ollama)."
            )

        base = text or ""
        tail = _clip_tail(base, max_chars=4000)
        detected = self._lang().detect(text=tail)
        language = detected.language

        tone_hint = (tone or "").strip()
        tone_clause = f"Tone: {tone_hint}." if tone_hint else "Tone: match the existing text."
        lang_clause = (
            f"Write in {language}." if language else "Write in the same language as the input."
        )

        sys = (
            "You are an autocomplete engine.\n"
            "Continue the user's text seamlessly.\n"
            "Rules:\n"
            "- Output ONLY the continuation (do not repeat any of the input).\n"
            "- Keep formatting consistent with the input.\n"
            f"- {tone_clause}\n"
            f"- {lang_clause}\n"
            "- If the text already feels complete, output an empty string.\n"
        )

        user = f"Text:\n{tail}"
        model = settings.writer_model if settings.llm_provider == LLMProvider.openai else None
        out = self._llm().chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            model=model,
            temperature=0.2,
        )
        completion = out or ""
        if len(completion) > int(max_chars):
            completion = completion[: int(max_chars)]
        return AutocompleteResponse(completion=completion, language=language)

    def edit(self, *, text: str, instruction: str, tone: str | None = None) -> TextEditResponse:
        if not _is_llm_configured():
            raise RuntimeError(
                "LLM is not configured (set OPENAI_API_KEY or use ALFRED_LLM_PROVIDER=ollama)."
            )

        base = text or ""
        instr = (instruction or "").strip()
        if not instr:
            raise ValueError("instruction is required")

        detected = self._lang().detect(text=base)
        language = detected.language

        tone_hint = (tone or "").strip()
        tone_clause = f"Tone: {tone_hint}." if tone_hint else "Tone: preserve the author's tone."
        lang_clause = (
            f"Write in {language}." if language else "Write in the same language as the input."
        )

        sys = (
            "You are a meticulous editor.\n"
            "Apply the instruction to the text.\n"
            "Rules:\n"
            "- Preserve meaning and facts; do not invent details.\n"
            "- Output ONLY the final revised text.\n"
            f"- {tone_clause}\n"
            f"- {lang_clause}\n"
        )
        user = f"Instruction: {instr}\n\nText:\n{_clip_tail(base, max_chars=8000)}"
        model = settings.writer_model if settings.llm_provider == LLMProvider.openai else None
        out = self._llm().chat(
            [{"role": "system", "content": sys}, {"role": "user", "content": user}],
            model=model,
            temperature=0.2,
        )
        return TextEditResponse(output=(out or "").strip(), language=language)


__all__ = ["TextAssistService"]
