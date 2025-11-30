from __future__ import annotations

import logging
import re

from alfred.core.config import settings

logger = logging.getLogger(__name__)


class TextCleaningService:
    """Normalize raw text prior to chunking or ingestion.

    Strategy is controlled by `TEXT_CLEANING_STRATEGY` (basic | langextract | llm).
    - basic: regex + optional HTML sanitize; no external calls.
    - langextract: if `langextract` is installed, use it with OpenAI/Gemini models
      to extract content paragraphs/headings and reassemble cleaned text.
    - llm: use OpenAI to rewrite into cleaned markdown/text.

    Falls back to basic if deps/keys are missing or errors occur.
    """

    _collapse_ws = re.compile(r"[ \t]+")
    _collapse_newlines = re.compile(r"\n{3,}")
    _zero_width = re.compile(r"[\u200B\u200C\u200D\uFEFF]")
    _control_chars = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")

    def clean(self, text: str, *, strategy: str | None = None) -> str:
        mode = (strategy or settings.text_cleaning_strategy or "basic").lower()
        # Always run light normalization first
        payload = self._basic_normalize(text or "")

        if mode == "langextract":
            try:
                cleaned = self._clean_with_langextract(payload)
                if cleaned:
                    return cleaned
            except Exception as exc:  # pragma: no cover - optional path
                logger.debug("langextract cleaning failed; falling back: %s", exc)
        elif mode == "llm":
            try:
                cleaned = self._clean_with_llm(payload)
                if cleaned:
                    return cleaned
            except Exception as exc:  # pragma: no cover - optional path
                logger.debug("LLM cleaning failed; falling back: %s", exc)

        return payload

    # -----------------
    # Basic path
    # -----------------
    def _basic_normalize(self, text: str) -> str:
        s = text.replace("\r\n", "\n").replace("\r", "\n")
        # Strip zero-width and control chars
        s = self._zero_width.sub("", s)
        s = self._control_chars.sub("", s)
        # Collapse spaces and long blank runs, but preserve paragraph breaks
        s = self._collapse_ws.sub(" ", s)
        s = self._collapse_newlines.sub("\n\n", s)
        s = s.strip()
        # Light HTML sanitize when content appears HTML-like
        if (
            "<" in s
            and ">" in s
            and any(tag in s.lower() for tag in ("<html", "<body", "<div", "<p"))
        ):
            import importlib.util

            if (
                importlib.util.find_spec("lxml") is not None
                and importlib.util.find_spec("lxml.html.clean") is not None
            ):
                try:
                    from lxml import html  # type: ignore
                    from lxml.html.clean import Cleaner  # type: ignore

                    cleaner = Cleaner(scripts=True, javascript=True, style=True, links=False)
                    frag = html.fromstring(s)
                    cleaner.clean_html(frag)
                    s = frag.text_content()
                    # Re-run whitespace normalization
                    s = self._collapse_ws.sub(" ", s)
                    s = self._collapse_newlines.sub("\n\n", s)
                    s = s.strip()
                except Exception:  # pragma: no cover - optional path
                    pass
        return s

    # -----------------
    # LangExtract path
    # -----------------
    def _clean_with_langextract(self, text: str) -> str | None:
        # Defer import; library is optional
        try:
            import importlib.util

            if importlib.util.find_spec("langextract") is None:
                return None
            import langextract as lx  # type: ignore
        except Exception:
            return None

        model_id = settings.text_cleaning_langextract_model or "gpt-4o-mini"
        model_url = settings.text_cleaning_model_url
        prompt = (
            "Extract content paragraphs and section headings in order of appearance.\n"
            "- Use exact text spans; do not paraphrase.\n"
            "- Ignore navigation, cookie banners, ads, and boilerplate.\n"
            "- Keep markdown headings if present.\n"
        )
        # With OpenAI models, ensure proper flags per LangExtract docs
        fence_output = model_id.startswith("gpt-")
        use_schema_constraints = False if fence_output else True

        # Provide a minimal example to steer extraction classes
        examples = [
            lx.data.ExampleData(
                text="# Title\n\nIntro paragraph about the topic.\nFooter links and cookies banner.",
                extractions=[
                    lx.data.Extraction(
                        extraction_class="heading",
                        extraction_text="# Title",
                        attributes={},
                    ),
                    lx.data.Extraction(
                        extraction_class="paragraph",
                        extraction_text="Intro paragraph about the topic.",
                        attributes={},
                    ),
                ],
            )
        ]

        kwargs: dict[str, object] = {
            "text_or_documents": text,
            "prompt_description": prompt,
            "examples": examples,
            "model_id": model_id,
            "fence_output": fence_output,
            "use_schema_constraints": use_schema_constraints,
        }
        if model_url:
            kwargs["model_url"] = model_url
        # Per docs, pass OpenAI API key explicitly when using gpt-* provider
        if model_id.startswith("gpt-") and settings.openai_api_key:
            kwargs["api_key"] = settings.openai_api_key
        # Scaling parameters
        if (
            settings.text_cleaning_langextract_passes
            and settings.text_cleaning_langextract_passes > 1
        ):
            kwargs["extraction_passes"] = settings.text_cleaning_langextract_passes
        if (
            settings.text_cleaning_langextract_workers
            and settings.text_cleaning_langextract_workers > 0
        ):
            kwargs["max_workers"] = settings.text_cleaning_langextract_workers
        if (
            settings.text_cleaning_langextract_char_buffer
            and settings.text_cleaning_langextract_char_buffer > 0
        ):
            kwargs["max_char_buffer"] = settings.text_cleaning_langextract_char_buffer

        annotated = lx.extract(**kwargs)

        # Reassemble content by extraction order; prefer headings then paragraphs
        blocks: list[str] = []
        try:
            extractions = getattr(annotated, "extractions", None)
            if extractions is None and hasattr(annotated, "__iter__"):
                # Iterator (batch API). Take first item if provided as single text.
                annotated = next(iter(annotated), None)
                extractions = getattr(annotated, "extractions", [])
            for e in extractions or []:
                cls = getattr(e, "extraction_class", "paragraph") or "paragraph"
                txt = (getattr(e, "extraction_text", "") or "").strip()
                if not txt:
                    continue
                if cls.lower() in ("heading", "header", "title", "h1", "h2"):
                    blocks.append(txt)
                else:
                    blocks.append(txt)
            joined = "\n\n".join(blocks).strip()
            return joined or None
        except Exception:  # pragma: no cover - optional path
            return None

    # -----------------
    # LLM path (OpenAI)
    # -----------------
    def _clean_with_llm(self, text: str) -> str | None:
        if not settings.openai_api_key:
            return None
        try:
            # Lazy import openai SDK
            from openai import OpenAI  # type: ignore

            client = OpenAI(api_key=settings.openai_api_key)
            model = settings.openai_model or "gpt-4o-mini"
            if not model.startswith("gpt-"):
                model = "gpt-4o-mini"
            sys_prompt = (
                "You clean text for downstream NLP.\n"
                "- Preserve paragraph breaks.\n"
                "- Remove boilerplate (nav, ads, cookie notices).\n"
                "- Normalize whitespace and fix common OCR artifacts.\n"
                "- Return plain text or markdown only."
            )
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text[:100_000]},
                ],
                temperature=0,
            )
            out = resp.choices[0].message.content if resp.choices else None
            if not out:
                return None
            return self._basic_normalize(out)
        except Exception:  # pragma: no cover - optional path
            return None
