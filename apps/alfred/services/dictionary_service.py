"""Dictionary service -- aggregates Wiktionary, Wikipedia, and LLM sources."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from alfred.services.llm_service import LLMService
from alfred.services.wikipedia import retrieve_wikipedia

logger = logging.getLogger(__name__)

WIKTIONARY_API = "https://en.wiktionary.org/api/rest_v1/page/definition"
WIKTIONARY_TIMEOUT_SECONDS = 4.0
_STREAM_END = object()


@dataclass
class DefinitionSense:
    definition: str
    examples: list[str] = field(default_factory=list)


@dataclass
class DefinitionGroup:
    part_of_speech: str
    senses: list[DefinitionSense] = field(default_factory=list)


@dataclass
class DictionaryResult:
    word: str
    pronunciation_ipa: str | None = None
    pronunciation_audio_url: str | None = None
    definitions: list[DefinitionGroup] = field(default_factory=list)
    etymology: str | None = None
    synonyms: list[dict[str, Any]] | None = None
    antonyms: list[dict[str, Any]] | None = None
    usage_notes: str | None = None
    wikipedia_summary: str | None = None
    ai_explanation: str | None = None
    source_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "word": self.word,
            "pronunciation_ipa": self.pronunciation_ipa,
            "pronunciation_audio_url": self.pronunciation_audio_url,
            "definitions": [
                {
                    "part_of_speech": g.part_of_speech,
                    "senses": [
                        {"definition": s.definition, "examples": s.examples} for s in g.senses
                    ],
                }
                for g in self.definitions
            ],
            "etymology": self.etymology,
            "synonyms": self.synonyms,
            "antonyms": self.antonyms,
            "usage_notes": self.usage_notes,
            "wikipedia_summary": self.wikipedia_summary,
            "ai_explanation": self.ai_explanation,
            "source_urls": self.source_urls,
        }


_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _parse_wiktionary_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse Wiktionary REST API response into structured definitions."""
    definitions: list[dict[str, Any]] = []
    pronunciation_ipa: str | None = None
    etymology: str | None = None

    entries = data.get("en", [])
    for entry in entries:
        if entry.get("language", "English") != "English":
            continue

        pos = entry.get("partOfSpeech", "Unknown")
        senses: list[dict[str, Any]] = []

        for defn in entry.get("definitions", []):
            raw_def = defn.get("definition", "")
            clean_def = _strip_html(raw_def)
            if not clean_def:
                continue

            examples = [_strip_html(ex) for ex in defn.get("examples", []) if isinstance(ex, str)]
            senses.append({"definition": clean_def, "examples": examples})

        if senses:
            definitions.append({"part_of_speech": pos, "senses": senses})

    return {
        "definitions": definitions,
        "pronunciation_ipa": pronunciation_ipa,
        "etymology": etymology,
    }


def _merge_results(
    *,
    word: str,
    wiktionary: dict[str, Any],
    wikipedia_summary: str | None,
    ai_explanation: str | None,
) -> DictionaryResult:
    """Merge results from all sources into a single DictionaryResult."""
    groups = []
    for defn in wiktionary.get("definitions", []):
        senses = [
            DefinitionSense(definition=s["definition"], examples=s.get("examples", []))
            for s in defn.get("senses", [])
        ]
        groups.append(DefinitionGroup(part_of_speech=defn["part_of_speech"], senses=senses))

    source_urls: list[str] = []
    if wiktionary.get("definitions"):
        source_urls.append(f"https://en.wiktionary.org/wiki/{word}")
    if wikipedia_summary:
        source_urls.append(f"https://en.wikipedia.org/wiki/{word}")

    return DictionaryResult(
        word=word,
        pronunciation_ipa=wiktionary.get("pronunciation_ipa"),
        etymology=wiktionary.get("etymology"),
        definitions=groups,
        wikipedia_summary=wikipedia_summary,
        ai_explanation=ai_explanation,
        source_urls=source_urls,
    )


async def _fetch_wiktionary(word: str) -> dict[str, Any]:
    """Fetch and parse Wiktionary definition."""
    try:
        async with httpx.AsyncClient(timeout=WIKTIONARY_TIMEOUT_SECONDS) as client:
            resp = await client.get(f"{WIKTIONARY_API}/{word}")
            if resp.status_code == 404:
                return {
                    "definitions": [],
                    "pronunciation_ipa": None,
                    "etymology": None,
                }
            resp.raise_for_status()
            return _parse_wiktionary_response(resp.json())
    except Exception:
        logger.exception("Wiktionary lookup failed for '%s'", word)
        return {"definitions": [], "pronunciation_ipa": None, "etymology": None}


async def _fetch_wikipedia(word: str) -> str | None:
    """Fetch Wikipedia summary using existing service."""
    try:
        result = await asyncio.to_thread(
            retrieve_wikipedia,
            query=word,
            top_k_results=1,
            doc_content_chars_max=1500,
        )
        items = result.get("items", [])
        if items:
            return items[0].get("content")
    except Exception:
        logger.exception("Wikipedia lookup failed for '%s'", word)
    return None


def _definitions_text(wiktionary_data: dict[str, Any]) -> str:
    definitions_text = ""
    for defn in wiktionary_data.get("definitions", []):
        for sense in defn.get("senses", []):
            definitions_text += f"({defn['part_of_speech']}) {sense['definition']}; "
    return definitions_text


def _build_ai_explanation_messages(
    word: str,
    definitions_text: str,
    domains: list[str],
) -> list[dict[str, str]]:
    if not definitions_text:
        definitions_text = f"The word '{word}'"

    domain_str = ", ".join(domains) if domains else "general knowledge"
    return [
        {
            "role": "system",
            "content": (
                "You are a knowledgeable tutor. Given a word and its definitions, "
                "provide a clear, contextual explanation tailored to the user's "
                "domains of interest. Include: 1) A plain English explanation, "
                "2) How the word is used in each relevant domain, "
                "3) One memorable example. Keep it concise (150-200 words)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Word: {word}\n"
                f"Definitions: {definitions_text}\n"
                f"My domains: {domain_str}\n\n"
                "Explain this word in context."
            ),
        },
    ]


def _next_stream_chunk(iterator: Iterator[str]) -> str | object:
    try:
        return next(iterator)
    except StopIteration:
        return _STREAM_END


async def _stream_ai_explanation(
    word: str,
    definitions_text: str,
    domains: list[str],
    llm: LLMService,
) -> AsyncGenerator[str, None]:
    messages = _build_ai_explanation_messages(word, definitions_text, domains)
    iterator = iter(llm.chat_stream(messages, temperature=0.3))

    while True:
        chunk = await asyncio.to_thread(_next_stream_chunk, iterator)
        if chunk is _STREAM_END:
            return
        if isinstance(chunk, str) and chunk:
            yield chunk


async def _generate_ai_explanation(
    word: str,
    definitions_text: str,
    domains: list[str],
    llm: LLMService,
) -> str | None:
    """Generate contextual AI explanation."""
    messages = _build_ai_explanation_messages(word, definitions_text, domains)
    try:
        return await llm.chat_async(messages, temperature=0.3)
    except Exception:
        logger.exception("AI explanation generation failed for '%s'", word)
        return None


async def lookup(
    word: str,
    *,
    user_domains: list[str] | None = None,
    llm: LLMService | None = None,
) -> DictionaryResult:
    """Look up a word from all sources in parallel, merge into DictionaryResult."""
    domains = user_domains or []

    wiktionary_task = asyncio.create_task(_fetch_wiktionary(word))
    wikipedia_task = asyncio.create_task(_fetch_wikipedia(word))

    wiktionary_data = await wiktionary_task
    wikipedia_summary = await wikipedia_task

    definitions_text = _definitions_text(wiktionary_data)

    ai_explanation = None
    if llm:
        ai_explanation = await _generate_ai_explanation(word, definitions_text, domains, llm)

    return _merge_results(
        word=word,
        wiktionary=wiktionary_data,
        wikipedia_summary=wikipedia_summary,
        ai_explanation=ai_explanation,
    )


async def lookup_stream_events(
    word: str,
    *,
    user_domains: list[str] | None = None,
    llm: LLMService | None = None,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Stream dictionary lookup phases as event/data pairs."""
    domains = user_domains or []

    yield (
        "status",
        {"phase": "lexicon", "message": "Checking dictionary sources"},
    )

    wikipedia_task = asyncio.create_task(_fetch_wikipedia(word))
    wiktionary_data = await _fetch_wiktionary(word)
    definitions_text = _definitions_text(wiktionary_data)

    lexical_result = _merge_results(
        word=word,
        wiktionary=wiktionary_data,
        wikipedia_summary=None,
        ai_explanation=None,
    )
    yield ("lookup", lexical_result.to_dict())

    ai_explanation: str | None = None
    if llm:
        yield (
            "status",
            {"phase": "ai", "message": "Streaming contextual explanation"},
        )
        yield ("ai_start", {"word": word})
        chunks: list[str] = []
        try:
            async for chunk in _stream_ai_explanation(word, definitions_text, domains, llm):
                chunks.append(chunk)
                yield ("ai_delta", {"content": chunk})
        except Exception:
            logger.exception("AI explanation stream failed for '%s'", word)
            yield (
                "error",
                {
                    "step": "ai",
                    "message": "AI explanation could not be generated.",
                },
            )

        ai_explanation = "".join(chunks).strip() or None
        if ai_explanation:
            yield ("ai_done", {"content": ai_explanation})

    yield (
        "status",
        {"phase": "encyclopedia", "message": "Checking encyclopedia context"},
    )
    wikipedia_summary = await wikipedia_task
    if wikipedia_summary:
        yield (
            "wikipedia",
            {
                "summary": wikipedia_summary,
                "source_url": f"https://en.wikipedia.org/wiki/{word}",
            },
        )

    final_result = _merge_results(
        word=word,
        wiktionary=wiktionary_data,
        wikipedia_summary=wikipedia_summary,
        ai_explanation=ai_explanation,
    )
    yield ("done", final_result.to_dict())
