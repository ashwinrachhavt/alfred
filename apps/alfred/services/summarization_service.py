from __future__ import annotations

import importlib.util
import io
import logging
import re
import uuid
from dataclasses import dataclass

from pydantic import BaseModel, Field

from alfred.core.settings import LLMProvider, settings
from alfred.schemas.documents import DocSummary, DocumentIngest
from alfred.schemas.intelligence import QaResponse, SummaryPayload
from alfred.services.chunking import ChunkingService
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.language_service import LanguageService
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)

_PYPDF_AVAILABLE = importlib.util.find_spec("pypdf") is not None
if _PYPDF_AVAILABLE:  # pragma: no cover - environment dependent
    from pypdf import PdfReader  # type: ignore[import-not-found]
else:  # pragma: no cover - environment dependent
    PdfReader = None  # type: ignore[assignment]

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


class _SummaryDraft(BaseModel):
    title: str | None = None
    language: str | None = None
    short: str = Field(..., min_length=1)
    bullets: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)


def _is_llm_configured() -> bool:
    if settings.llm_provider == LLMProvider.ollama:
        return True
    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else ""
    return bool(api_key or settings.openai_base_url)


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall((text or "").lower()))


def _select_relevant_chunks(*, chunks: list[str], question: str, k: int = 6) -> list[str]:
    q_tokens = _tokenize(question)
    if not q_tokens:
        return chunks[:k]

    scored: list[tuple[float, str]] = []
    for ch in chunks:
        overlap = len(q_tokens.intersection(_tokenize(ch)))
        if overlap <= 0:
            continue
        score = overlap / max(1, len(q_tokens))
        scored.append((score, ch))
    scored.sort(key=lambda p: p[0], reverse=True)
    return [ch for _score, ch in scored[:k]] or chunks[:k]


@dataclass(slots=True)
class SummarizationService:
    """Summarize content from multiple sources and support lightweight Q&A."""

    doc_storage: DocStorageService
    llm_service: LLMService | None = None
    language_service: LanguageService | None = None
    chunking_service: ChunkingService | None = None

    def _llm(self) -> LLMService:
        return self.llm_service or LLMService()

    def _lang(self) -> LanguageService:
        return self.language_service or LanguageService()

    def _chunker(self) -> ChunkingService:
        return self.chunking_service or ChunkingService()

    def summarize_text(
        self,
        *,
        text: str,
        title: str | None = None,
        source_url: str | None = None,
        content_type: str = "text",
        store: bool = True,
    ) -> tuple[SummaryPayload, str | None]:
        cleaned = (text or "").strip()
        if not cleaned:
            raise ValueError("text is required")

        summary = self._summarize(cleaned_text=cleaned, title_hint=title)
        doc_id: str | None = None
        if store:
            doc_id = self._store_document(
                cleaned_text=cleaned,
                title=title or summary.title,
                source_url=source_url,
                content_type=content_type,
                summary=summary,
            )
        return summary, doc_id

    def summarize_url(
        self,
        *,
        url: str,
        title: str | None = None,
        render_js: bool = False,
        store: bool = True,
    ) -> tuple[SummaryPayload, str | None]:
        url_norm = (url or "").strip()
        if not url_norm:
            raise ValueError("url is required")
        extracted = self._extract_url_text(url_norm, render_js=render_js)
        return self.summarize_text(
            text=extracted,
            title=title,
            source_url=url_norm,
            content_type="web",
            store=store,
        )

    def summarize_pdf_bytes(
        self,
        *,
        pdf_bytes: bytes,
        title: str | None = None,
        source_url: str | None = None,
        store: bool = True,
    ) -> tuple[SummaryPayload, str | None]:
        text = self._extract_pdf_text(pdf_bytes)
        return self.summarize_text(
            text=text,
            title=title,
            source_url=source_url,
            content_type="pdf",
            store=store,
        )

    def summarize_audio_bytes(
        self,
        *,
        audio_bytes: bytes,
        filename: str | None = None,
        title: str | None = None,
        source_url: str | None = None,
        content_type: str = "audio",
        store: bool = True,
        model: str = "whisper-1",
    ) -> tuple[SummaryPayload, str | None]:
        transcript = self._transcribe_audio(audio_bytes=audio_bytes, filename=filename, model=model)
        return self.summarize_text(
            text=transcript,
            title=title or (filename or None),
            source_url=source_url,
            content_type=content_type,
            store=store,
        )

    def answer_question(self, *, question: str, text: str) -> QaResponse:
        q = (question or "").strip()
        if not q:
            raise ValueError("question is required")
        src = (text or "").strip()
        if not src:
            raise ValueError("text is required")

        if not _is_llm_configured():
            raise RuntimeError(
                "LLM is not configured (set OPENAI_API_KEY or use ALFRED_LLM_PROVIDER=ollama)."
            )

        detected_q = self._lang().detect(text=q)
        language = detected_q.language

        chunks = self._chunker().chunk(
            src,
            max_tokens=500,
            overlap=80,
            mode="token",
        )
        chunk_texts = [c.text for c in chunks if (c.text or "").strip()]
        selected = _select_relevant_chunks(chunks=chunk_texts, question=q, k=6)
        context = "\n\n---\n\n".join(selected)[:12000]

        lang_clause = (
            f"Write in {language}." if language else "Write in the same language as the question."
        )
        sys = (
            "You answer questions using ONLY the provided context.\n"
            "If the answer is not present, say you can't find it in the provided material.\n"
            f"{lang_clause}\n"
            "Be concise and precise.\n"
        )

        model = settings.writer_model if settings.llm_provider == LLMProvider.openai else None
        answer = self._llm().chat(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": f"Question: {q}\n\nContext:\n{context}"},
            ],
            model=model,
            temperature=0.2,
        )
        return QaResponse(answer=(answer or "").strip(), language=language)

    def answer_question_for_doc(self, *, question: str, doc_id: str) -> QaResponse:
        details = self.doc_storage.get_document_details(doc_id)
        if not details:
            raise ValueError("Document not found")
        text = (details.get("raw_markdown") or details.get("cleaned_text") or "").strip()
        if not text:
            raise ValueError("Document has no text content")
        return self.answer_question(question=question, text=text)

    # ----------------- internals -----------------
    def _summarize(self, *, cleaned_text: str, title_hint: str | None) -> SummaryPayload:
        if not _is_llm_configured():
            raise RuntimeError(
                "LLM is not configured (set OPENAI_API_KEY or use ALFRED_LLM_PROVIDER=ollama)."
            )

        excerpt = cleaned_text[:12000]
        detected = self._lang().detect(text=excerpt[:4000])
        language = detected.language

        lang_clause = (
            f"Write in {language}." if language else "Write in the same language as the input."
        )
        title_clause = f"Title hint: {title_hint.strip()}" if (title_hint or "").strip() else ""

        sys = (
            "You are a summarization engine.\n"
            "Return JSON only.\n"
            "Schema:\n"
            "- title: optional string\n"
            "- language: optional ISO 639-1 code\n"
            "- short: 3-6 sentence paragraph\n"
            "- bullets: 2-6 bullets\n"
            "- key_points: 2-6 bullets\n"
            f"{lang_clause}\n"
            "Do not invent facts.\n"
        )

        if settings.llm_provider == LLMProvider.openai:
            model = settings.writer_model
            try:
                out = self._llm().structured(
                    [
                        {"role": "system", "content": sys},
                        {
                            "role": "user",
                            "content": "\n\n".join([p for p in (title_clause, excerpt) if p]),
                        },
                    ],
                    schema=_SummaryDraft,
                    model=model,
                )
                return SummaryPayload(
                    title=(out.title or None),
                    language=(out.language or language),
                    short=out.short.strip(),
                    bullets=[b for b in out.bullets if isinstance(b, str) and b.strip()],
                    key_points=[k for k in out.key_points if isinstance(k, str) and k.strip()],
                )
            except Exception as exc:  # pragma: no cover - network/provider dependent
                logger.debug("Structured summary failed; falling back to chat: %s", exc)

        # Fallback: best-effort JSON via chat (works for ollama or when structured fails).
        model = settings.writer_model if settings.llm_provider == LLMProvider.openai else None
        raw = self._llm().chat(
            [
                {"role": "system", "content": sys},
                {"role": "user", "content": "\n\n".join([p for p in (title_clause, excerpt) if p])},
            ],
            model=model,
            temperature=0.2,
        )
        # Best effort: if the model didn't return JSON, treat it as the short summary.
        try:
            parsed = _SummaryDraft.model_validate_json(raw or "{}")
            return SummaryPayload(
                title=parsed.title,
                language=(parsed.language or language),
                short=(parsed.short or "").strip() or (raw or "").strip(),
                bullets=[b for b in parsed.bullets if isinstance(b, str) and b.strip()],
                key_points=[k for k in parsed.key_points if isinstance(k, str) and k.strip()],
            )
        except Exception:
            return SummaryPayload(title=title_hint, language=language, short=(raw or "").strip())

    def _store_document(
        self,
        *,
        cleaned_text: str,
        title: str | None,
        source_url: str | None,
        content_type: str,
        summary: SummaryPayload,
    ) -> str:
        src = (source_url or "").strip() or f"alfred://summaries/{uuid.uuid4()}"
        ingest = DocumentIngest(
            source_url=src,
            title=(title or summary.title),
            content_type=content_type,
            lang=summary.language,
            cleaned_text=cleaned_text,
            summary=DocSummary(
                short=summary.short,
                bullets=summary.bullets or None,
                key_points=summary.key_points or None,
            ),
            metadata={"summarized_by": "intelligence"},
        )
        res = self.doc_storage.ingest_document_basic(ingest)
        return str(res.get("id"))

    def _extract_pdf_text(self, pdf_bytes: bytes) -> str:
        if not _PYPDF_AVAILABLE or PdfReader is None:
            raise RuntimeError("PDF support requires the optional dependency 'pypdf'.")
        try:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            parts: list[str] = []
            for page in reader.pages:
                try:
                    txt = page.extract_text() or ""
                except Exception:
                    txt = ""
                if txt.strip():
                    parts.append(txt)
            out = "\n\n".join(parts).strip()
            if not out:
                raise RuntimeError("No text could be extracted from the PDF")
            return out
        except Exception as exc:
            raise RuntimeError(f"Failed to extract PDF text: {exc}") from exc

    def _extract_url_text(self, url: str, *, render_js: bool) -> str:
        # Try Firecrawl first (best extraction quality) if a local server is available.
        try:
            from alfred.connectors.firecrawl_connector import FirecrawlClient

            client = FirecrawlClient(
                base_url=settings.firecrawl_base_url, timeout=settings.firecrawl_timeout
            )
            resp = client.scrape(url, render_js=bool(render_js))
            if resp.success and (resp.markdown or resp.html):
                return (resp.markdown or resp.html or "").strip()
        except Exception:
            pass

        # Fallback: direct fetch + trafilatura extraction
        try:
            import httpx  # type: ignore

            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                html = client.get(url).text
        except Exception as exc:
            raise RuntimeError(f"Failed to fetch URL: {exc}") from exc

        try:
            import trafilatura  # type: ignore

            extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
            out = (extracted or "").strip()
            if out:
                return out
        except Exception:
            pass

        # Last resort: return raw HTML (the summarizer will handle it poorly but safely).
        return html[:12000]

    def _transcribe_audio(self, *, audio_bytes: bytes, filename: str | None, model: str) -> str:
        if settings.llm_provider != LLMProvider.openai:
            raise RuntimeError("Audio transcription currently requires ALFRED_LLM_PROVIDER=openai.")
        if not _is_llm_configured():
            raise RuntimeError("OpenAI is not configured (set OPENAI_API_KEY).")

        buf = io.BytesIO(audio_bytes)
        buf.name = (filename or "audio").strip() or "audio"  # type: ignore[attr-defined]

        try:
            client = self._llm().openai_client
            resp = client.audio.transcriptions.create(model=model, file=buf)
            text = getattr(resp, "text", None)
            out = (text if isinstance(text, str) else str(resp)).strip()
            if not out:
                raise RuntimeError("Empty transcript")
            return out
        except Exception as exc:  # pragma: no cover - network
            raise RuntimeError(f"Audio transcription failed: {exc}") from exc


__all__ = ["SummarizationService"]
