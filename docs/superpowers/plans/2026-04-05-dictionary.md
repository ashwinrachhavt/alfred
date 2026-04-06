# Alfred Dictionary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a beautiful, iBooks-style dictionary with search-first standalone page, personal vocabulary journal with save-with-intent, and multi-source lookup (Wiktionary + Wikipedia + LLM).

**Architecture:** Layered approach — Phase 1 builds a standalone `/dictionary` page with backend service aggregating Wiktionary + Wikipedia + LLM, a `VocabularyEntry` SQLModel, and React Query data layer. The frontend uses the editorial design system (Source Serif 4 headwords, Berkeley Mono metadata, DM Sans body).

**Tech Stack:** FastAPI, SQLModel/Alembic, OpenAI (via LLMService), Wiktionary REST API, Wikipedia service (existing), Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, React Query, Zustand.

---

## File Structure

### Backend (new files)

| File | Responsibility |
|------|---------------|
| `apps/alfred/models/vocabulary.py` | `VocabularyEntry` SQLModel table |
| `apps/alfred/services/dictionary_service.py` | Wiktionary/Wikipedia/LLM aggregation + CRUD |
| `apps/alfred/api/dictionary/__init__.py` | Router export |
| `apps/alfred/api/dictionary/routes.py` | REST endpoints |
| `apps/alfred/migrations/versions/e6f7a8b9c0d1_add_vocabulary_entries.py` | Alembic migration |
| `tests/alfred/services/test_dictionary_service.py` | Service unit tests |
| `tests/alfred/api/test_dictionary_routes.py` | Route unit tests |

### Backend (modified files)

| File | Change |
|------|--------|
| `apps/alfred/api/__init__.py` | Register dictionary router |

### Frontend (new files)

| File | Responsibility |
|------|---------------|
| `web/lib/api/dictionary.ts` | API wrapper functions + types |
| `web/features/dictionary/queries.ts` | React Query hooks |
| `web/features/dictionary/mutations.ts` | Mutation hooks |
| `web/lib/stores/dictionary-store.ts` | Zustand store |
| `web/app/(app)/dictionary/page.tsx` | Page entry point |
| `web/components/dictionary/dictionary-search-bar.tsx` | Search input with dropdown |
| `web/components/dictionary/dictionary-entry.tsx` | Full entry layout |
| `web/components/dictionary/dictionary-entry-skeleton.tsx` | Loading skeleton |
| `web/components/dictionary/definition-section.tsx` | POS + definitions |
| `web/components/dictionary/etymology-section.tsx` | Collapsible etymology |
| `web/components/dictionary/synonyms-section.tsx` | Clickable synonym/antonym chips |
| `web/components/dictionary/ai-explanation-section.tsx` | LLM contextual panel |
| `web/components/dictionary/encyclopedia-section.tsx` | Wikipedia summary |
| `web/components/dictionary/usage-notes-section.tsx` | Register + collocations |
| `web/components/dictionary/personal-annotations.tsx` | Editable notes (saved entries) |
| `web/components/dictionary/save-bar.tsx` | Sticky save/edit bar |
| `web/components/dictionary/vocabulary-collection.tsx` | Saved words grid |

### Frontend (modified files)

| File | Change |
|------|--------|
| `web/lib/api/routes.ts` | Add `dictionary` route group |
| `web/app/(app)/_components/app-sidebar.tsx` | Add Dictionary nav item |

---

### Task 1: VocabularyEntry Model

**Files:**
- Create: `apps/alfred/models/vocabulary.py`
- Test: `tests/alfred/models/test_vocabulary_model.py`

- [ ] **Step 1: Write the failing test**

Create `tests/alfred/models/test_vocabulary_model.py`:

```python
"""Tests for VocabularyEntry model."""

from __future__ import annotations


class TestVocabularyEntryModel:
    """Verify VocabularyEntry field defaults and constraints."""

    def test_import(self):
        from alfred.models.vocabulary import SaveIntent, VocabularyEntry

        assert VocabularyEntry is not None
        assert SaveIntent is not None

    def test_default_fields(self):
        from alfred.models.vocabulary import SaveIntent, VocabularyEntry

        entry = VocabularyEntry(word="ephemeral", save_intent=SaveIntent.learning)
        assert entry.word == "ephemeral"
        assert entry.save_intent == SaveIntent.learning
        assert entry.language == "en"
        assert entry.bloom_level == 1
        assert entry.definitions is None
        assert entry.etymology is None
        assert entry.pronunciation_ipa is None
        assert entry.zettel_id is None
        assert entry.domain_tags is None

    def test_save_intent_enum_values(self):
        from alfred.models.vocabulary import SaveIntent

        assert SaveIntent.learning.value == "learning"
        assert SaveIntent.reference.value == "reference"
        assert SaveIntent.encountered.value == "encountered"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/models/test_vocabulary_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfred.models.vocabulary'`

- [ ] **Step 3: Write the VocabularyEntry model**

Create `apps/alfred/models/vocabulary.py`:

```python
"""Vocabulary / dictionary domain model."""

from __future__ import annotations

import enum

from sqlalchemy import Column, ForeignKey, Index, Integer, JSON, SmallInteger, String, Text
from sqlmodel import Field

from alfred.models.base import Model


class SaveIntent(str, enum.Enum):
    """Why the user saved this word."""

    learning = "learning"
    reference = "reference"
    encountered = "encountered"


class VocabularyEntry(Model, table=True):
    """A personal dictionary entry combining external definitions with user annotations."""

    __tablename__ = "vocabulary_entries"
    __table_args__ = (
        Index("ix_vocabulary_entries_word", "word"),
        Index("ix_vocabulary_entries_user_id", "user_id"),
        Index("ix_vocabulary_entries_save_intent", "save_intent"),
    )

    user_id: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    word: str = Field(sa_column=Column(String(255), nullable=False))
    language: str = Field(default="en", sa_column=Column(String(10), nullable=False))

    # Pronunciation
    pronunciation_ipa: str | None = Field(default=None, sa_column=Column(String(512), nullable=True))
    pronunciation_audio_url: str | None = Field(
        default=None, sa_column=Column(String(2048), nullable=True)
    )

    # Structured data from external sources
    definitions: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    etymology: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    synonyms: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    antonyms: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    usage_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))

    # External content
    wikipedia_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_explanation: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    ai_explanation_domains: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    source_urls: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    # Personal
    personal_notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    domain_tags: list | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    save_intent: str = Field(
        default=SaveIntent.learning.value, sa_column=Column(String(32), nullable=False)
    )
    bloom_level: int = Field(default=1, sa_column=Column(SmallInteger, nullable=False))

    # Phase 2: knowledge graph link
    zettel_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("zettel_cards.id"), nullable=True),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/models/test_vocabulary_model.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/models/vocabulary.py tests/alfred/models/test_vocabulary_model.py
git commit -m "feat(dictionary): add VocabularyEntry model with SaveIntent enum"
```

---

### Task 2: Alembic Migration

**Files:**
- Create: `apps/alfred/migrations/versions/e6f7a8b9c0d1_add_vocabulary_entries.py`

- [ ] **Step 1: Write the migration**

Create `apps/alfred/migrations/versions/e6f7a8b9c0d1_add_vocabulary_entries.py`:

```python
"""add vocabulary_entries table

Revision ID: e6f7a8b9c0d1
Revises: d4e5f6a7b8c9
Create Date: 2026-04-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e6f7a8b9c0d1"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vocabulary_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer, nullable=True),
        sa.Column("word", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), nullable=False, server_default=sa.text("'en'")),
        sa.Column("pronunciation_ipa", sa.String(length=512), nullable=True),
        sa.Column("pronunciation_audio_url", sa.String(length=2048), nullable=True),
        sa.Column("definitions", sa.JSON, nullable=True),
        sa.Column("etymology", sa.Text, nullable=True),
        sa.Column("synonyms", sa.JSON, nullable=True),
        sa.Column("antonyms", sa.JSON, nullable=True),
        sa.Column("usage_notes", sa.Text, nullable=True),
        sa.Column("wikipedia_summary", sa.Text, nullable=True),
        sa.Column("ai_explanation", sa.Text, nullable=True),
        sa.Column("ai_explanation_domains", sa.JSON, nullable=True),
        sa.Column("source_urls", sa.JSON, nullable=True),
        sa.Column("personal_notes", sa.Text, nullable=True),
        sa.Column("domain_tags", sa.JSON, nullable=True),
        sa.Column("save_intent", sa.String(length=32), nullable=False, server_default=sa.text("'learning'")),
        sa.Column("bloom_level", sa.SmallInteger, nullable=False, server_default=sa.text("1")),
        sa.Column(
            "zettel_id",
            sa.Integer,
            sa.ForeignKey("zettel_cards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_index("ix_vocabulary_entries_word", "vocabulary_entries", ["word"])
    op.create_index("ix_vocabulary_entries_user_id", "vocabulary_entries", ["user_id"])
    op.create_index("ix_vocabulary_entries_save_intent", "vocabulary_entries", ["save_intent"])


def downgrade() -> None:
    op.drop_index("ix_vocabulary_entries_save_intent", table_name="vocabulary_entries")
    op.drop_index("ix_vocabulary_entries_user_id", table_name="vocabulary_entries")
    op.drop_index("ix_vocabulary_entries_word", table_name="vocabulary_entries")
    op.drop_table("vocabulary_entries")
```

- [ ] **Step 2: Verify migration syntax**

Run: `cd /Users/ashwinrachha/coding/alfred && python -c "exec(open('apps/alfred/migrations/versions/e6f7a8b9c0d1_add_vocabulary_entries.py').read()); print('ok')"`

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add apps/alfred/migrations/versions/e6f7a8b9c0d1_add_vocabulary_entries.py
git commit -m "feat(dictionary): add vocabulary_entries migration"
```

---

### Task 3: Dictionary Service — Wiktionary Client

**Files:**
- Create: `apps/alfred/services/dictionary_service.py`
- Test: `tests/alfred/services/test_dictionary_service.py`

- [ ] **Step 1: Write failing tests for Wiktionary parsing**

Create `tests/alfred/services/test_dictionary_service.py`:

```python
"""Tests for dictionary service."""

from __future__ import annotations


# Sample Wiktionary REST API response for "ephemeral"
WIKTIONARY_RESPONSE = {
    "en": [
        {
            "partOfSpeech": "Adjective",
            "language": "English",
            "definitions": [
                {
                    "definition": "Lasting for a short period of time.",
                    "examples": ["Ephemeral pleasures are soon forgotten."],
                },
                {
                    "definition": "Existing for only one day, as with certain insects.",
                    "examples": [],
                },
            ],
        },
        {
            "partOfSpeech": "Noun",
            "language": "English",
            "definitions": [
                {
                    "definition": "Something that is ephemeral.",
                    "examples": [],
                },
            ],
        },
    ]
}


class TestParseWiktionaryResponse:
    """Test parsing of Wiktionary REST API responses."""

    def test_parse_definitions(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        result = _parse_wiktionary_response(WIKTIONARY_RESPONSE)
        assert len(result["definitions"]) == 2

        adj = result["definitions"][0]
        assert adj["part_of_speech"] == "Adjective"
        assert len(adj["senses"]) == 2
        assert adj["senses"][0]["definition"] == "Lasting for a short period of time."
        assert adj["senses"][0]["examples"] == ["Ephemeral pleasures are soon forgotten."]

        noun = result["definitions"][1]
        assert noun["part_of_speech"] == "Noun"
        assert len(noun["senses"]) == 1

    def test_parse_empty_response(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        result = _parse_wiktionary_response({})
        assert result["definitions"] == []

    def test_parse_non_english_filtered(self):
        from alfred.services.dictionary_service import _parse_wiktionary_response

        response = {
            "en": [
                {
                    "partOfSpeech": "Adjective",
                    "language": "English",
                    "definitions": [
                        {"definition": "English def", "examples": []},
                    ],
                },
            ],
            "fr": [
                {
                    "partOfSpeech": "Adjectif",
                    "language": "French",
                    "definitions": [
                        {"definition": "French def", "examples": []},
                    ],
                },
            ],
        }
        result = _parse_wiktionary_response(response)
        # Should only parse English entries
        assert len(result["definitions"]) == 1
        assert result["definitions"][0]["part_of_speech"] == "Adjective"


class TestMergeLookupResult:
    """Test merging of multiple source results into DictionaryResult."""

    def test_merge_builds_complete_result(self):
        from alfred.services.dictionary_service import DictionaryResult, _merge_results

        wiktionary_data = {
            "definitions": [
                {
                    "part_of_speech": "Adjective",
                    "senses": [
                        {"definition": "Lasting briefly", "examples": ["An ephemeral joy."]},
                    ],
                },
            ],
            "pronunciation_ipa": "/ephemeral/",
            "etymology": "From Greek ephemeros",
        }
        wikipedia_summary = "In philosophy, the ephemeral is..."
        ai_explanation = "In system design, ephemeral means short-lived..."

        result = _merge_results(
            word="ephemeral",
            wiktionary=wiktionary_data,
            wikipedia_summary=wikipedia_summary,
            ai_explanation=ai_explanation,
        )

        assert isinstance(result, DictionaryResult)
        assert result.word == "ephemeral"
        assert result.pronunciation_ipa == "/ephemeral/"
        assert result.etymology == "From Greek ephemeros"
        assert result.wikipedia_summary == "In philosophy, the ephemeral is..."
        assert result.ai_explanation == "In system design, ephemeral means short-lived..."
        assert len(result.definitions) == 1

    def test_merge_handles_missing_sources(self):
        from alfred.services.dictionary_service import DictionaryResult, _merge_results

        result = _merge_results(
            word="test",
            wiktionary={"definitions": [], "pronunciation_ipa": None, "etymology": None},
            wikipedia_summary=None,
            ai_explanation=None,
        )

        assert isinstance(result, DictionaryResult)
        assert result.word == "test"
        assert result.definitions == []
        assert result.wikipedia_summary is None
        assert result.ai_explanation is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_dictionary_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfred.services.dictionary_service'`

- [ ] **Step 3: Implement dictionary_service.py**

Create `apps/alfred/services/dictionary_service.py`:

```python
"""Dictionary service -- aggregates Wiktionary, Wikipedia, and LLM sources."""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from alfred.services.llm_service import LLMService
from alfred.services.wikipedia import retrieve_wikipedia

logger = logging.getLogger(__name__)

WIKTIONARY_API = "https://en.wiktionary.org/api/rest_v1/page/definition"


# --------------- Data structures ---------------


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


# --------------- Wiktionary parsing ---------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text).strip()


def _parse_wiktionary_response(data: dict[str, Any]) -> dict[str, Any]:
    """Parse Wiktionary REST API response into structured definitions."""
    definitions: list[dict[str, Any]] = []
    pronunciation_ipa: str | None = None
    etymology: str | None = None

    # Only process English entries
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

            examples = [
                _strip_html(ex)
                for ex in defn.get("examples", [])
                if isinstance(ex, str)
            ]
            senses.append({"definition": clean_def, "examples": examples})

        if senses:
            definitions.append({"part_of_speech": pos, "senses": senses})

    return {
        "definitions": definitions,
        "pronunciation_ipa": pronunciation_ipa,
        "etymology": etymology,
    }


# --------------- Result merging ---------------


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
            DefinitionSense(
                definition=s["definition"], examples=s.get("examples", [])
            )
            for s in defn.get("senses", [])
        ]
        groups.append(
            DefinitionGroup(part_of_speech=defn["part_of_speech"], senses=senses)
        )

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


# --------------- External API calls ---------------


async def _fetch_wiktionary(word: str) -> dict[str, Any]:
    """Fetch and parse Wiktionary definition."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
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


async def _generate_ai_explanation(
    word: str,
    definitions_text: str,
    domains: list[str],
    llm: LLMService,
) -> str | None:
    """Generate contextual AI explanation."""
    if not definitions_text:
        definitions_text = f"The word '{word}'"

    domain_str = ", ".join(domains) if domains else "general knowledge"
    messages = [
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
    try:
        return await llm.chat_async(messages, temperature=0.3)
    except Exception:
        logger.exception("AI explanation generation failed for '%s'", word)
        return None


# --------------- Public API ---------------


async def lookup(
    word: str,
    *,
    user_domains: list[str] | None = None,
    llm: LLMService | None = None,
) -> DictionaryResult:
    """Look up a word from all sources in parallel, merge into DictionaryResult."""
    domains = user_domains or []

    # Fire Wiktionary and Wikipedia in parallel
    wiktionary_task = asyncio.create_task(_fetch_wiktionary(word))
    wikipedia_task = asyncio.create_task(_fetch_wikipedia(word))

    wiktionary_data = await wiktionary_task
    wikipedia_summary = await wikipedia_task

    # Build definitions text for AI prompt
    definitions_text = ""
    for defn in wiktionary_data.get("definitions", []):
        for sense in defn.get("senses", []):
            definitions_text += (
                f"({defn['part_of_speech']}) {sense['definition']}; "
            )

    # Generate AI explanation (needs definitions first)
    ai_explanation = None
    if llm:
        ai_explanation = await _generate_ai_explanation(
            word, definitions_text, domains, llm
        )

    return _merge_results(
        word=word,
        wiktionary=wiktionary_data,
        wikipedia_summary=wikipedia_summary,
        ai_explanation=ai_explanation,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_dictionary_service.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/services/dictionary_service.py tests/alfred/services/test_dictionary_service.py
git commit -m "feat(dictionary): add dictionary service with Wiktionary parsing and result merging"
```

---

### Task 4: Dictionary API Routes

**Files:**
- Create: `apps/alfred/api/dictionary/__init__.py`
- Create: `apps/alfred/api/dictionary/routes.py`
- Modify: `apps/alfred/api/__init__.py`
- Test: `tests/alfred/api/test_dictionary_routes.py`

- [ ] **Step 1: Write failing test for lookup endpoint**

Create `tests/alfred/api/test_dictionary_routes.py`:

```python
"""Tests for dictionary API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from alfred.services.dictionary_service import (
    DictionaryResult,
    DefinitionGroup,
    DefinitionSense,
)


MOCK_RESULT = DictionaryResult(
    word="ephemeral",
    pronunciation_ipa="/ephemeral/",
    definitions=[
        DefinitionGroup(
            part_of_speech="Adjective",
            senses=[
                DefinitionSense(
                    definition="Lasting briefly", examples=["An ephemeral joy."]
                )
            ],
        )
    ],
    etymology="From Greek ephemeros",
    wikipedia_summary="In philosophy...",
    ai_explanation="In system design...",
    source_urls=["https://en.wiktionary.org/wiki/ephemeral"],
)


class TestLookupEndpoint:
    def test_lookup_returns_result(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        from alfred.api.dictionary.routes import router

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with patch(
            "alfred.api.dictionary.routes.lookup", new_callable=AsyncMock
        ) as mock_lookup:
            mock_lookup.return_value = MOCK_RESULT
            resp = client.get("/api/dictionary/lookup?word=ephemeral")

        assert resp.status_code == 200
        data = resp.json()
        assert data["word"] == "ephemeral"
        assert data["pronunciation_ipa"] == "/ephemeral/"
        assert len(data["definitions"]) == 1
        assert data["definitions"][0]["part_of_speech"] == "Adjective"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/test_dictionary_routes.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Create the route files**

Create `apps/alfred/api/dictionary/__init__.py`:

```python
from alfred.api.dictionary.routes import router

__all__ = ["router"]
```

Create `apps/alfred/api/dictionary/routes.py`:

```python
"""Dictionary REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlmodel import Session

from alfred.core.db import engine
from alfred.models.vocabulary import SaveIntent, VocabularyEntry
from alfred.services.dictionary_service import (
    DictionaryResult,
    _generate_ai_explanation,
    lookup,
)
from alfred.services.llm_service import LLMService

router = APIRouter(prefix="/api/dictionary", tags=["dictionary"])

_llm = LLMService()


@router.get("/lookup")
async def lookup_word(
    word: str = Query(..., min_length=1, max_length=255),
    lang: str = Query("en"),
) -> dict:
    """Look up a word from external sources (Wiktionary + Wikipedia + AI)."""
    result = await lookup(word.strip().lower(), llm=_llm)
    return result.to_dict()


@router.post("/entries")
def save_entry(payload: dict) -> dict:
    """Save a looked-up word to the vocabulary journal."""
    entry = VocabularyEntry(
        word=payload["word"],
        language=payload.get("language", "en"),
        pronunciation_ipa=payload.get("pronunciation_ipa"),
        pronunciation_audio_url=payload.get("pronunciation_audio_url"),
        definitions=payload.get("definitions"),
        etymology=payload.get("etymology"),
        synonyms=payload.get("synonyms"),
        antonyms=payload.get("antonyms"),
        usage_notes=payload.get("usage_notes"),
        wikipedia_summary=payload.get("wikipedia_summary"),
        ai_explanation=payload.get("ai_explanation"),
        ai_explanation_domains=payload.get("ai_explanation_domains"),
        source_urls=payload.get("source_urls"),
        personal_notes=payload.get("personal_notes"),
        domain_tags=payload.get("domain_tags"),
        save_intent=payload.get("save_intent", SaveIntent.learning.value),
        bloom_level=payload.get("bloom_level", 1),
    )
    with Session(engine) as session:
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return {
            "id": entry.id,
            "word": entry.word,
            "save_intent": entry.save_intent,
            "created_at": str(entry.created_at),
        }


@router.get("/entries")
def list_entries(
    save_intent: str | None = Query(None),
    domain: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[dict]:
    """List saved vocabulary entries with optional filters."""
    with Session(engine) as session:
        stmt = select(VocabularyEntry).order_by(
            VocabularyEntry.created_at.desc()
        )
        if save_intent:
            stmt = stmt.where(VocabularyEntry.save_intent == save_intent)
        stmt = stmt.offset(offset).limit(limit)
        entries = session.exec(stmt).all()
        return [
            {
                "id": e.id,
                "word": e.word,
                "language": e.language,
                "pronunciation_ipa": e.pronunciation_ipa,
                "definitions": e.definitions,
                "domain_tags": e.domain_tags,
                "save_intent": e.save_intent,
                "bloom_level": e.bloom_level,
                "created_at": str(e.created_at),
                "updated_at": str(e.updated_at),
            }
            for e in entries
        ]


@router.get("/entries/{entry_id}")
def get_entry(entry_id: int) -> dict:
    """Get a single vocabulary entry by ID."""
    with Session(engine) as session:
        entry = session.get(VocabularyEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return {
            "id": entry.id,
            "word": entry.word,
            "language": entry.language,
            "pronunciation_ipa": entry.pronunciation_ipa,
            "pronunciation_audio_url": entry.pronunciation_audio_url,
            "definitions": entry.definitions,
            "etymology": entry.etymology,
            "synonyms": entry.synonyms,
            "antonyms": entry.antonyms,
            "usage_notes": entry.usage_notes,
            "wikipedia_summary": entry.wikipedia_summary,
            "ai_explanation": entry.ai_explanation,
            "ai_explanation_domains": entry.ai_explanation_domains,
            "source_urls": entry.source_urls,
            "personal_notes": entry.personal_notes,
            "domain_tags": entry.domain_tags,
            "save_intent": entry.save_intent,
            "bloom_level": entry.bloom_level,
            "zettel_id": entry.zettel_id,
            "created_at": str(entry.created_at),
            "updated_at": str(entry.updated_at),
        }


@router.patch("/entries/{entry_id}")
def update_entry(entry_id: int, payload: dict) -> dict:
    """Update personal notes, domain tags, bloom level, or save intent."""
    with Session(engine) as session:
        entry = session.get(VocabularyEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        allowed = {"personal_notes", "domain_tags", "bloom_level", "save_intent"}
        for key in allowed:
            if key in payload:
                setattr(entry, key, payload[key])

        session.add(entry)
        session.commit()
        session.refresh(entry)
        return {
            "id": entry.id,
            "word": entry.word,
            "updated_at": str(entry.updated_at),
        }


@router.delete("/entries/{entry_id}")
def delete_entry(entry_id: int) -> dict:
    """Remove a vocabulary entry."""
    with Session(engine) as session:
        entry = session.get(VocabularyEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        session.delete(entry)
        session.commit()
        return {"deleted": True}


@router.get("/search")
async def search_dictionary(q: str = Query(..., min_length=1)) -> dict:
    """Search saved vocabulary first, then fall back to external lookup."""
    query = q.strip().lower()

    # Search saved entries
    with Session(engine) as session:
        stmt = (
            select(VocabularyEntry)
            .where(VocabularyEntry.word.ilike(f"%{query}%"))
            .order_by(VocabularyEntry.created_at.desc())
            .limit(10)
        )
        saved = session.exec(stmt).all()
        saved_results = [
            {
                "id": e.id,
                "word": e.word,
                "save_intent": e.save_intent,
                "domain_tags": e.domain_tags,
            }
            for e in saved
        ]

    # Also do external lookup
    external = await lookup(query, llm=_llm)

    return {
        "query": query,
        "saved": saved_results,
        "lookup": external.to_dict(),
    }


@router.post("/entries/{entry_id}/regenerate-ai")
async def regenerate_ai_explanation(entry_id: int) -> dict:
    """Re-generate AI explanation with current domain tags."""
    with Session(engine) as session:
        entry = session.get(VocabularyEntry, entry_id)
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        domains = entry.domain_tags or []
        definitions_text = ""
        if entry.definitions:
            for defn in entry.definitions:
                for sense in defn.get("senses", []):
                    definitions_text += (
                        f"({defn.get('part_of_speech', '')}) "
                        f"{sense.get('definition', '')}; "
                    )

        ai_text = await _generate_ai_explanation(
            entry.word, definitions_text, domains, _llm
        )
        entry.ai_explanation = ai_text
        entry.ai_explanation_domains = domains
        session.add(entry)
        session.commit()
        session.refresh(entry)

        return {"id": entry.id, "ai_explanation": entry.ai_explanation}
```

- [ ] **Step 4: Register router in app**

In `apps/alfred/api/__init__.py`, add after the existing imports (around line 18, with the other router imports):

```python
    from alfred.api.dictionary import router as dictionary_router
```

Add `dictionary_router` to the `routers` list (before the closing bracket, around line 105):

```python
        dictionary_router,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/api/test_dictionary_routes.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/api/dictionary/ apps/alfred/api/__init__.py tests/alfred/api/test_dictionary_routes.py
git commit -m "feat(dictionary): add dictionary API routes and register router"
```

---

### Task 5: Frontend API Layer

**Files:**
- Create: `web/lib/api/dictionary.ts`
- Modify: `web/lib/api/routes.ts`

- [ ] **Step 1: Add dictionary routes to the routes registry**

In `web/lib/api/routes.ts`, add a new `dictionary` section after the `thinking` block (around line 109):

```typescript
  dictionary: {
    lookup: "/api/dictionary/lookup",
    entries: "/api/dictionary/entries",
    entryById: (id: number) => `/api/dictionary/entries/${id}`,
    search: "/api/dictionary/search",
    regenerateAi: (id: number) => `/api/dictionary/entries/${id}/regenerate-ai`,
  },
```

- [ ] **Step 2: Create the API wrapper**

Create `web/lib/api/dictionary.ts`:

```typescript
import { apiFetch, apiPostJson, apiPatchJson } from "@/lib/api/client";
import { apiRoutes } from "@/lib/api/routes";

// --------------- Types ---------------

export type DefinitionSense = {
  definition: string;
  examples: string[];
};

export type DefinitionGroup = {
  part_of_speech: string;
  senses: DefinitionSense[];
};

export type DictionaryResult = {
  word: string;
  pronunciation_ipa: string | null;
  pronunciation_audio_url: string | null;
  definitions: DefinitionGroup[];
  etymology: string | null;
  synonyms: { sense: string; words: string[] }[] | null;
  antonyms: { sense: string; words: string[] }[] | null;
  usage_notes: string | null;
  wikipedia_summary: string | null;
  ai_explanation: string | null;
  source_urls: string[];
};

export type SaveIntent = "learning" | "reference" | "encountered";

export type VocabularyEntry = {
  id: number;
  word: string;
  language: string;
  pronunciation_ipa: string | null;
  pronunciation_audio_url: string | null;
  definitions: DefinitionGroup[] | null;
  etymology: string | null;
  synonyms: { sense: string; words: string[] }[] | null;
  antonyms: { sense: string; words: string[] }[] | null;
  usage_notes: string | null;
  wikipedia_summary: string | null;
  ai_explanation: string | null;
  ai_explanation_domains: string[] | null;
  source_urls: string[] | null;
  personal_notes: string | null;
  domain_tags: string[] | null;
  save_intent: SaveIntent;
  bloom_level: number;
  zettel_id: number | null;
  created_at: string;
  updated_at: string;
};

export type VocabularyListItem = {
  id: number;
  word: string;
  language: string;
  pronunciation_ipa: string | null;
  definitions: DefinitionGroup[] | null;
  domain_tags: string[] | null;
  save_intent: SaveIntent;
  bloom_level: number;
  created_at: string;
  updated_at: string;
};

export type SaveEntryPayload = {
  word: string;
  language?: string;
  pronunciation_ipa?: string | null;
  pronunciation_audio_url?: string | null;
  definitions?: DefinitionGroup[] | null;
  etymology?: string | null;
  synonyms?: { sense: string; words: string[] }[] | null;
  antonyms?: { sense: string; words: string[] }[] | null;
  usage_notes?: string | null;
  wikipedia_summary?: string | null;
  ai_explanation?: string | null;
  ai_explanation_domains?: string[] | null;
  source_urls?: string[] | null;
  personal_notes?: string | null;
  domain_tags?: string[] | null;
  save_intent: SaveIntent;
  bloom_level?: number;
};

export type UpdateEntryPayload = {
  personal_notes?: string;
  domain_tags?: string[];
  bloom_level?: number;
  save_intent?: SaveIntent;
};

export type SearchResult = {
  query: string;
  saved: {
    id: number;
    word: string;
    save_intent: SaveIntent;
    domain_tags: string[] | null;
  }[];
  lookup: DictionaryResult;
};

// --------------- API calls ---------------

export function lookupWord(word: string): Promise<DictionaryResult> {
  return apiFetch<DictionaryResult>(
    `${apiRoutes.dictionary.lookup}?word=${encodeURIComponent(word)}`,
    { cache: "no-store" },
  );
}

export function saveEntry(
  payload: SaveEntryPayload,
): Promise<{ id: number; word: string }> {
  return apiPostJson(apiRoutes.dictionary.entries, payload);
}

export function listEntries(params?: {
  save_intent?: SaveIntent;
  domain?: string;
  limit?: number;
  offset?: number;
}): Promise<VocabularyListItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.save_intent) searchParams.set("save_intent", params.save_intent);
  if (params?.domain) searchParams.set("domain", params.domain);
  if (params?.limit) searchParams.set("limit", String(params.limit));
  if (params?.offset) searchParams.set("offset", String(params.offset));

  const qs = searchParams.toString();
  const url = qs
    ? `${apiRoutes.dictionary.entries}?${qs}`
    : apiRoutes.dictionary.entries;
  return apiFetch<VocabularyListItem[]>(url, { cache: "no-store" });
}

export function getEntry(id: number): Promise<VocabularyEntry> {
  return apiFetch<VocabularyEntry>(apiRoutes.dictionary.entryById(id), {
    cache: "no-store",
  });
}

export function updateEntry(
  id: number,
  payload: UpdateEntryPayload,
): Promise<{ id: number; word: string }> {
  return apiPatchJson(apiRoutes.dictionary.entryById(id), payload);
}

export function deleteEntry(id: number): Promise<{ deleted: boolean }> {
  return apiFetch<{ deleted: boolean }>(apiRoutes.dictionary.entryById(id), {
    method: "DELETE",
  });
}

export function searchDictionary(query: string): Promise<SearchResult> {
  return apiFetch<SearchResult>(
    `${apiRoutes.dictionary.search}?q=${encodeURIComponent(query)}`,
    { cache: "no-store" },
  );
}

export function regenerateAiExplanation(
  id: number,
): Promise<{ id: number; ai_explanation: string }> {
  return apiPostJson(apiRoutes.dictionary.regenerateAi(id), {});
}
```

- [ ] **Step 3: Commit**

```bash
git add web/lib/api/dictionary.ts web/lib/api/routes.ts
git commit -m "feat(dictionary): add frontend API layer and route registry"
```

---

### Task 6: React Query Hooks

**Files:**
- Create: `web/features/dictionary/queries.ts`
- Create: `web/features/dictionary/mutations.ts`

- [ ] **Step 1: Create queries.ts**

Create `web/features/dictionary/queries.ts`:

```typescript
import { useQuery } from "@tanstack/react-query";

import {
  getEntry,
  listEntries,
  lookupWord,
  searchDictionary,
  type SaveIntent,
} from "@/lib/api/dictionary";

export function useDictionaryLookup(word: string | null) {
  return useQuery({
    queryKey: ["dictionary", "lookup", word],
    queryFn: () => lookupWord(word!),
    enabled: !!word && word.length > 0,
    staleTime: 5 * 60 * 1000,
  });
}

export function useVocabularyEntries(filters?: {
  save_intent?: SaveIntent;
  domain?: string;
  limit?: number;
  offset?: number;
}) {
  return useQuery({
    queryKey: ["dictionary", "entries", filters ?? null],
    queryFn: () => listEntries(filters),
    staleTime: 10_000,
  });
}

export function useVocabularyEntry(id: number | null) {
  return useQuery({
    queryKey: ["dictionary", "entry", id],
    queryFn: () => getEntry(id!),
    enabled: id !== null,
    staleTime: 30_000,
  });
}

export function useDictionarySearch(query: string | null) {
  return useQuery({
    queryKey: ["dictionary", "search", query],
    queryFn: () => searchDictionary(query!),
    enabled: !!query && query.length >= 2,
    staleTime: 30_000,
  });
}
```

- [ ] **Step 2: Create mutations.ts**

Create `web/features/dictionary/mutations.ts`:

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  deleteEntry,
  regenerateAiExplanation,
  saveEntry,
  updateEntry,
  type SaveEntryPayload,
  type UpdateEntryPayload,
} from "@/lib/api/dictionary";

const ENTRIES_KEY = ["dictionary", "entries"];

export function useSaveEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SaveEntryPayload) => saveEntry(payload),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
    },
  });
}

export function useUpdateEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: UpdateEntryPayload;
    }) => updateEntry(id, payload),
    onSettled: (_data, _err, variables) => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
      queryClient.invalidateQueries({
        queryKey: ["dictionary", "entry", variables.id],
      });
    },
  });
}

export function useDeleteEntry() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteEntry(id),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ENTRIES_KEY });
    },
  });
}

export function useRegenerateAiExplanation() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => regenerateAiExplanation(id),
    onSettled: (_data, _err, id) => {
      queryClient.invalidateQueries({
        queryKey: ["dictionary", "entry", id],
      });
    },
  });
}
```

- [ ] **Step 3: Commit**

```bash
git add web/features/dictionary/
git commit -m "feat(dictionary): add React Query hooks for dictionary data layer"
```

---

### Task 7: Zustand Store

**Files:**
- Create: `web/lib/stores/dictionary-store.ts`

- [ ] **Step 1: Create the store**

Create `web/lib/stores/dictionary-store.ts`:

```typescript
import { create } from "zustand";

import type { DictionaryResult, SaveIntent } from "@/lib/api/dictionary";

type DictionaryState = {
  searchQuery: string;
  currentResult: DictionaryResult | null;
  isLooking: boolean;
  activeTab: "search" | "collection";
  filterIntent: SaveIntent | null;
  filterDomain: string | null;

  setSearchQuery: (query: string) => void;
  setCurrentResult: (result: DictionaryResult | null) => void;
  setIsLooking: (loading: boolean) => void;
  setActiveTab: (tab: "search" | "collection") => void;
  setFilterIntent: (intent: SaveIntent | null) => void;
  setFilterDomain: (domain: string | null) => void;
  reset: () => void;
};

const initialState = {
  searchQuery: "",
  currentResult: null,
  isLooking: false,
  activeTab: "search" as const,
  filterIntent: null,
  filterDomain: null,
};

export const useDictionaryStore = create<DictionaryState>((set) => ({
  ...initialState,
  setSearchQuery: (query) => set({ searchQuery: query }),
  setCurrentResult: (result) => set({ currentResult: result }),
  setIsLooking: (loading) => set({ isLooking: loading }),
  setActiveTab: (tab) => set({ activeTab: tab }),
  setFilterIntent: (intent) => set({ filterIntent: intent }),
  setFilterDomain: (domain) => set({ filterDomain: domain }),
  reset: () => set(initialState),
}));
```

- [ ] **Step 2: Commit**

```bash
git add web/lib/stores/dictionary-store.ts
git commit -m "feat(dictionary): add Zustand store for dictionary UI state"
```

---

### Task 8: Entry Section Components

**Files:**
- Create: `web/components/dictionary/definition-section.tsx`
- Create: `web/components/dictionary/etymology-section.tsx`
- Create: `web/components/dictionary/synonyms-section.tsx`
- Create: `web/components/dictionary/ai-explanation-section.tsx`
- Create: `web/components/dictionary/encyclopedia-section.tsx`
- Create: `web/components/dictionary/usage-notes-section.tsx`
- Create: `web/components/dictionary/personal-annotations.tsx`
- Create: `web/components/dictionary/dictionary-entry-skeleton.tsx`

All 8 component files are listed in the spec with full code. Create each file in `web/components/dictionary/`. The components follow the DESIGN.md typography system:

- [ ] **Step 1: Create definition-section.tsx** — renders DefinitionGroup[] with POS headers in Berkeley Mono and numbered senses in DM Sans

```tsx
"use client";

import type { DefinitionGroup } from "@/lib/api/dictionary";

export function DefinitionSection({ groups }: { groups: DefinitionGroup[] }) {
  if (groups.length === 0) return null;

  return (
    <div className="space-y-6">
      {groups.map((group, gi) => (
        <div key={gi}>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            {group.part_of_speech}
          </span>
          <ol className="mt-2 list-decimal space-y-3 pl-5">
            {group.senses.map((sense, si) => (
              <li key={si} className="text-foreground leading-relaxed">
                <span>{sense.definition}</span>
                {sense.examples.length > 0 && (
                  <div className="mt-1 space-y-1">
                    {sense.examples.map((ex, ei) => (
                      <p
                        key={ei}
                        className="text-sm italic text-muted-foreground"
                      >
                        &ldquo;{ex}&rdquo;
                      </p>
                    ))}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create etymology-section.tsx** — collapsible panel with accent-muted left border

```tsx
"use client";

import { useState } from "react";
import { ChevronRight } from "lucide-react";

export function EtymologySection({ etymology }: { etymology: string }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="border-l-2 border-[var(--alfred-accent-muted)] pl-4">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors"
      >
        <ChevronRight
          className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
        />
        Etymology
      </button>
      {open && (
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          {etymology}
        </p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create synonyms-section.tsx** — clickable Badge chips for synonyms and antonyms

```tsx
"use client";

import { Badge } from "@/components/ui/badge";

type SynonymGroup = { sense: string; words: string[] };

export function SynonymsSection({
  synonyms,
  antonyms,
  onWordClick,
}: {
  synonyms: SynonymGroup[] | null;
  antonyms: SynonymGroup[] | null;
  onWordClick: (word: string) => void;
}) {
  const hasSynonyms = synonyms && synonyms.length > 0;
  const hasAntonyms = antonyms && antonyms.length > 0;
  if (!hasSynonyms && !hasAntonyms) return null;

  return (
    <div className="space-y-3">
      {hasSynonyms && (
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Synonyms
          </span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {synonyms.flatMap((g) =>
              g.words.map((w) => (
                <Badge
                  key={w}
                  variant="secondary"
                  className="cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => onWordClick(w)}
                >
                  {w}
                </Badge>
              )),
            )}
          </div>
        </div>
      )}
      {hasAntonyms && (
        <div>
          <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
            Antonyms
          </span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {antonyms.flatMap((g) =>
              g.words.map((w) => (
                <Badge
                  key={w}
                  variant="outline"
                  className="cursor-pointer hover:bg-accent transition-colors"
                  onClick={() => onWordClick(w)}
                >
                  {w}
                </Badge>
              )),
            )}
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Create ai-explanation-section.tsx** — deep orange accent border panel with regenerate button

```tsx
"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export function AiExplanationSection({
  explanation,
  domains,
  isRegenerating,
  onRegenerate,
}: {
  explanation: string;
  domains?: string[] | null;
  isRegenerating?: boolean;
  onRegenerate?: () => void;
}) {
  return (
    <div className="rounded-lg border-l-2 border-[#E8590C] bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
          AI Explanation
        </span>
        {onRegenerate && (
          <Button
            variant="ghost"
            size="sm"
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="h-7 gap-1 text-xs"
          >
            <RefreshCw
              className={`h-3 w-3 ${isRegenerating ? "animate-spin" : ""}`}
            />
            Regenerate
          </Button>
        )}
      </div>
      {domains && domains.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          {domains.map((d) => (
            <span
              key={d}
              className="rounded bg-[var(--alfred-accent-subtle)] px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider"
            >
              {d}
            </span>
          ))}
        </div>
      )}
      <p className="mt-3 text-sm leading-relaxed whitespace-pre-line">
        {explanation}
      </p>
    </div>
  );
}
```

- [ ] **Step 5: Create encyclopedia-section.tsx** — collapsible Wikipedia card with external link

```tsx
"use client";

import { useState } from "react";
import { ChevronRight, ExternalLink } from "lucide-react";

export function EncyclopediaSection({
  summary,
  word,
}: {
  summary: string;
  word: string;
}) {
  const [open, setOpen] = useState(false);
  const wikiUrl = `https://en.wikipedia.org/wiki/${encodeURIComponent(word)}`;

  return (
    <div className="rounded-md border bg-card">
      <button
        onClick={() => setOpen(!open)}
        className="flex w-full items-center justify-between px-4 py-3 text-left"
      >
        <span className="flex items-center gap-1.5 font-mono text-xs uppercase tracking-wider text-muted-foreground">
          <ChevronRight
            className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-90" : ""}`}
          />
          Encyclopedia
        </span>
      </button>
      {open && (
        <div className="border-t px-4 py-3">
          <p className="text-sm leading-relaxed text-muted-foreground">
            {summary.length > 600 ? `${summary.slice(0, 600)}...` : summary}
          </p>
          <a
            href={wikiUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-2 inline-flex items-center gap-1 text-xs text-[#E8590C] hover:underline"
          >
            Read more on Wikipedia
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: Create usage-notes-section.tsx**

```tsx
"use client";

export function UsageNotesSection({ notes }: { notes: string }) {
  return (
    <div>
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        Usage Notes
      </span>
      <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
        {notes}
      </p>
    </div>
  );
}
```

- [ ] **Step 7: Create personal-annotations.tsx** — editable textarea with save/cancel

```tsx
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

export function PersonalAnnotations({
  notes,
  onSave,
  isSaving,
}: {
  notes: string | null;
  onSave: (text: string) => void;
  isSaving?: boolean;
}) {
  const [text, setText] = useState(notes ?? "");
  const [editing, setEditing] = useState(false);
  const hasChanged = text !== (notes ?? "");

  return (
    <div>
      <span className="font-mono text-xs uppercase tracking-wider text-muted-foreground">
        Your Notes
      </span>
      {editing ? (
        <div className="mt-2 space-y-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Add your own notes, mnemonics, or connections..."
            className="min-h-[80px] resize-y"
          />
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() => {
                onSave(text);
                setEditing(false);
              }}
              disabled={!hasChanged || isSaving}
            >
              Save
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setText(notes ?? "");
                setEditing(false);
              }}
            >
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <div
          className="mt-2 cursor-pointer rounded-md border border-dashed p-3 text-sm text-muted-foreground hover:border-foreground/30 transition-colors"
          onClick={() => setEditing(true)}
        >
          {notes || "Click to add your notes..."}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: Create dictionary-entry-skeleton.tsx**

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function DictionaryEntrySkeleton() {
  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <Skeleton className="h-10 w-48" />
        <Skeleton className="mt-2 h-4 w-32" />
      </div>
      <div className="space-y-3">
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full" />
      </div>
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-32 w-full rounded-lg" />
    </div>
  );
}
```

- [ ] **Step 9: Commit**

```bash
git add web/components/dictionary/
git commit -m "feat(dictionary): add entry section components"
```

---

### Task 9: Dictionary Entry + Search Bar + Save Bar

**Files:**
- Create: `web/components/dictionary/dictionary-entry.tsx`
- Create: `web/components/dictionary/dictionary-search-bar.tsx`
- Create: `web/components/dictionary/save-bar.tsx`

- [ ] **Step 1: Create save-bar.tsx** — sticky bottom bar with intent selector + save button

```tsx
"use client";

import { useState } from "react";
import { BookMarked, GraduationCap, Eye } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { SaveIntent } from "@/lib/api/dictionary";

const intents: {
  value: SaveIntent;
  label: string;
  icon: typeof GraduationCap;
}[] = [
  { value: "learning", label: "Learning", icon: GraduationCap },
  { value: "reference", label: "Reference", icon: BookMarked },
  { value: "encountered", label: "Encountered", icon: Eye },
];

export function SaveBar({
  onSave,
  isSaving,
}: {
  onSave: (intent: SaveIntent) => void;
  isSaving?: boolean;
}) {
  const [selected, setSelected] = useState<SaveIntent>("learning");

  return (
    <div className="sticky bottom-0 z-10 flex items-center justify-between border-t bg-background/95 px-4 py-3 backdrop-blur-sm">
      <div className="flex gap-1.5">
        {intents.map(({ value, label, icon: Icon }) => (
          <button
            key={value}
            onClick={() => setSelected(value)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors ${
              selected === value
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>
      <Button
        onClick={() => onSave(selected)}
        disabled={isSaving}
        size="sm"
        className="bg-[#E8590C] text-white hover:bg-[#E8590C]/90"
      >
        {isSaving ? "Saving..." : "Save to Vocabulary"}
      </Button>
    </div>
  );
}
```

- [ ] **Step 2: Create dictionary-search-bar.tsx** — debounced search with dropdown showing saved + external results

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useDictionarySearch } from "@/features/dictionary/queries";

export function DictionarySearchBar({
  onLookup,
}: {
  onLookup: (word: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [localQuery, setLocalQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState<string | null>(null);
  const [showDropdown, setShowDropdown] = useState(false);

  const { data: searchResult } = useDictionarySearch(debouncedQuery);

  useEffect(() => {
    if (localQuery.length < 2) {
      setDebouncedQuery(null);
      return;
    }
    const timer = setTimeout(() => setDebouncedQuery(localQuery), 300);
    return () => clearTimeout(timer);
  }, [localQuery]);

  const handleSelect = useCallback(
    (word: string) => {
      setLocalQuery(word);
      setShowDropdown(false);
      onLookup(word);
    },
    [onLookup],
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && localQuery.trim()) {
      handleSelect(localQuery.trim().toLowerCase());
    }
    if (e.key === "Escape") {
      setShowDropdown(false);
    }
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  return (
    <div className="relative w-full max-w-2xl mx-auto">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
        <Input
          ref={inputRef}
          value={localQuery}
          onChange={(e) => {
            setLocalQuery(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => localQuery.length >= 2 && setShowDropdown(true)}
          onKeyDown={handleKeyDown}
          placeholder="Look up a word..."
          className="h-14 pl-12 pr-20 text-lg font-serif placeholder:text-muted-foreground/50"
        />
        <kbd className="absolute right-4 top-1/2 -translate-y-1/2 rounded border bg-muted px-2 py-0.5 font-mono text-xs text-muted-foreground">
          {"\u2318"}K
        </kbd>
      </div>

      {showDropdown && searchResult && (
        <div className="absolute top-full left-0 right-0 z-20 mt-1 rounded-md border bg-popover shadow-lg">
          {searchResult.saved.length > 0 && (
            <div className="p-2">
              <span className="px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Your Vocabulary
              </span>
              {searchResult.saved.map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleSelect(item.word)}
                  className="mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm hover:bg-accent transition-colors"
                >
                  <span className="font-medium">{item.word}</span>
                  <span className="ml-auto font-mono text-[10px] uppercase text-muted-foreground">
                    {item.save_intent}
                  </span>
                </button>
              ))}
            </div>
          )}
          {searchResult.lookup.definitions.length > 0 && (
            <div className="border-t p-2">
              <span className="px-2 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                Look Up
              </span>
              <button
                onClick={() => handleSelect(searchResult.lookup.word)}
                className="mt-1 flex w-full items-center rounded px-2 py-1.5 text-left text-sm hover:bg-accent transition-colors"
              >
                <span className="font-medium">
                  {searchResult.lookup.word}
                </span>
                <span className="ml-2 text-xs text-muted-foreground">
                  {searchResult.lookup.definitions[0]?.senses[0]?.definition.slice(
                    0,
                    60,
                  )}
                  ...
                </span>
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Create dictionary-entry.tsx** — main entry layout composing all section components

```tsx
"use client";

import { Volume2 } from "lucide-react";
import type { DictionaryResult } from "@/lib/api/dictionary";
import { AiExplanationSection } from "./ai-explanation-section";
import { DefinitionSection } from "./definition-section";
import { EncyclopediaSection } from "./encyclopedia-section";
import { EtymologySection } from "./etymology-section";
import { SynonymsSection } from "./synonyms-section";
import { UsageNotesSection } from "./usage-notes-section";

export function DictionaryEntry({
  result,
  onWordClick,
}: {
  result: DictionaryResult;
  onWordClick: (word: string) => void;
}) {
  const playAudio = () => {
    if (result.pronunciation_audio_url) {
      const audio = new Audio(result.pronunciation_audio_url);
      audio.play();
    }
  };

  return (
    <article className="mx-auto max-w-2xl space-y-8 pb-24">
      <header>
        <h1 className="font-serif text-5xl font-semibold tracking-tight">
          {result.word}
        </h1>
        {result.pronunciation_ipa && (
          <div className="mt-2 flex items-center gap-2">
            <span className="font-mono text-sm text-muted-foreground">
              {result.pronunciation_ipa}
            </span>
            {result.pronunciation_audio_url && (
              <button
                onClick={playAudio}
                className="rounded-full p-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors"
              >
                <Volume2 className="h-4 w-4" />
              </button>
            )}
          </div>
        )}
      </header>
      <DefinitionSection groups={result.definitions} />
      {result.etymology && <EtymologySection etymology={result.etymology} />}
      <SynonymsSection
        synonyms={result.synonyms}
        antonyms={result.antonyms}
        onWordClick={onWordClick}
      />
      {result.ai_explanation && (
        <AiExplanationSection explanation={result.ai_explanation} />
      )}
      {result.usage_notes && <UsageNotesSection notes={result.usage_notes} />}
      {result.wikipedia_summary && (
        <EncyclopediaSection
          summary={result.wikipedia_summary}
          word={result.word}
        />
      )}
    </article>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add web/components/dictionary/dictionary-entry.tsx web/components/dictionary/dictionary-search-bar.tsx web/components/dictionary/save-bar.tsx
git commit -m "feat(dictionary): add DictionaryEntry, SearchBar, and SaveBar components"
```

---

### Task 10: Vocabulary Collection Component

**Files:**
- Create: `web/components/dictionary/vocabulary-collection.tsx`

- [ ] **Step 1: Create vocabulary-collection.tsx** — filterable grid of saved words

```tsx
"use client";

import { Badge } from "@/components/ui/badge";
import { useVocabularyEntries } from "@/features/dictionary/queries";
import { useDictionaryStore } from "@/lib/stores/dictionary-store";
import type { SaveIntent } from "@/lib/api/dictionary";

const BLOOM_LABELS = [
  "",
  "Remember",
  "Understand",
  "Apply",
  "Analyze",
  "Evaluate",
  "Create",
];

const intentFilters: { value: SaveIntent | null; label: string }[] = [
  { value: null, label: "All" },
  { value: "learning", label: "Learning" },
  { value: "reference", label: "Reference" },
  { value: "encountered", label: "Encountered" },
];

export function VocabularyCollection({
  onSelect,
}: {
  onSelect: (word: string) => void;
}) {
  const filterIntent = useDictionaryStore((s) => s.filterIntent);
  const setFilterIntent = useDictionaryStore((s) => s.setFilterIntent);

  const { data: entries, isLoading } = useVocabularyEntries(
    filterIntent ? { save_intent: filterIntent } : undefined,
  );

  return (
    <div className="mx-auto max-w-2xl">
      <div className="flex gap-1.5 mb-6">
        {intentFilters.map(({ value, label }) => (
          <button
            key={label}
            onClick={() => setFilterIntent(value)}
            className={`rounded-md px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors ${
              filterIntent === value
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              key={i}
              className="h-24 animate-pulse rounded-md border bg-muted"
            />
          ))}
        </div>
      ) : entries && entries.length > 0 ? (
        <div className="grid grid-cols-2 gap-3">
          {entries.map((entry) => (
            <button
              key={entry.id}
              onClick={() => onSelect(entry.word)}
              className="group rounded-md border bg-card p-3 text-left hover:border-foreground/20 transition-colors"
            >
              <p className="font-serif text-lg font-medium group-hover:text-[#E8590C] transition-colors">
                {entry.word}
              </p>
              {entry.definitions?.[0]?.senses[0] && (
                <p className="mt-1 text-xs text-muted-foreground line-clamp-2">
                  {entry.definitions[0].senses[0].definition}
                </p>
              )}
              <div className="mt-2 flex items-center gap-1.5">
                {entry.domain_tags?.slice(0, 2).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-[10px]">
                    {tag}
                  </Badge>
                ))}
                <span className="ml-auto font-mono text-[10px] text-muted-foreground">
                  {BLOOM_LABELS[entry.bloom_level] ?? ""}
                </span>
              </div>
            </button>
          ))}
        </div>
      ) : (
        <div className="py-16 text-center text-sm text-muted-foreground">
          No saved words yet. Look up a word and save it to start your
          vocabulary journal.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add web/components/dictionary/vocabulary-collection.tsx
git commit -m "feat(dictionary): add VocabularyCollection grid component"
```

---

### Task 11: Dictionary Page + Sidebar Navigation

**Files:**
- Create: `web/app/(app)/dictionary/page.tsx`
- Modify: `web/app/(app)/_components/app-sidebar.tsx`

- [ ] **Step 1: Create the dictionary page** — composes SearchBar, DictionaryEntry, SaveBar, and VocabularyCollection

```tsx
"use client";

import { useCallback, useState } from "react";
import { BookOpen, Grid } from "lucide-react";

import { DictionaryEntry } from "@/components/dictionary/dictionary-entry";
import { DictionaryEntrySkeleton } from "@/components/dictionary/dictionary-entry-skeleton";
import { DictionarySearchBar } from "@/components/dictionary/dictionary-search-bar";
import { SaveBar } from "@/components/dictionary/save-bar";
import { VocabularyCollection } from "@/components/dictionary/vocabulary-collection";
import { useDictionaryLookup } from "@/features/dictionary/queries";
import { useSaveEntry } from "@/features/dictionary/mutations";
import { useDictionaryStore } from "@/lib/stores/dictionary-store";
import type { SaveIntent } from "@/lib/api/dictionary";

export default function DictionaryPage() {
  const [lookupWord, setLookupWord] = useState<string | null>(null);
  const activeTab = useDictionaryStore((s) => s.activeTab);
  const setActiveTab = useDictionaryStore((s) => s.setActiveTab);

  const { data: result, isLoading } = useDictionaryLookup(lookupWord);
  const saveMutation = useSaveEntry();

  const handleLookup = useCallback(
    (word: string) => {
      setLookupWord(word);
      setActiveTab("search");
    },
    [setActiveTab],
  );

  const handleSave = useCallback(
    (intent: SaveIntent) => {
      if (!result) return;
      saveMutation.mutate({
        word: result.word,
        pronunciation_ipa: result.pronunciation_ipa,
        pronunciation_audio_url: result.pronunciation_audio_url,
        definitions: result.definitions,
        etymology: result.etymology,
        synonyms: result.synonyms,
        antonyms: result.antonyms,
        usage_notes: result.usage_notes,
        wikipedia_summary: result.wikipedia_summary,
        ai_explanation: result.ai_explanation,
        source_urls: result.source_urls,
        save_intent: intent,
      });
    },
    [result, saveMutation],
  );

  return (
    <div className="flex h-[calc(100dvh-3.5rem)] flex-col">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="font-serif text-xl font-semibold">Dictionary</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setActiveTab("search")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "search"
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <BookOpen className="h-4 w-4" />
          </button>
          <button
            onClick={() => setActiveTab("collection")}
            className={`rounded-md p-2 transition-colors ${
              activeTab === "collection"
                ? "bg-[var(--alfred-accent-subtle)] text-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Grid className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="px-6 pt-8 pb-6">
        <DictionarySearchBar onLookup={handleLookup} />
      </div>

      <div className="flex-1 overflow-y-auto px-6">
        {activeTab === "search" ? (
          <>
            {isLoading && <DictionaryEntrySkeleton />}
            {result && !isLoading && (
              <DictionaryEntry result={result} onWordClick={handleLookup} />
            )}
            {!result && !isLoading && !lookupWord && (
              <div className="py-24 text-center">
                <p className="font-serif text-2xl text-muted-foreground/50">
                  Look up any word
                </p>
                <p className="mt-2 text-sm text-muted-foreground">
                  Search to see definitions, etymology, and AI-powered
                  explanations
                </p>
              </div>
            )}
          </>
        ) : (
          <VocabularyCollection onSelect={handleLookup} />
        )}
      </div>

      {activeTab === "search" && result && !saveMutation.isSuccess && (
        <SaveBar onSave={handleSave} isSaving={saveMutation.isPending} />
      )}

      {saveMutation.isSuccess && (
        <div className="sticky bottom-0 z-10 border-t bg-background/95 px-4 py-3 text-center backdrop-blur-sm">
          <span className="text-sm text-muted-foreground">
            Saved to vocabulary
          </span>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add Dictionary to sidebar navigation**

In `web/app/(app)/_components/app-sidebar.tsx`, add the `BookA` import alongside other lucide-react icons, then add the Dictionary nav item after the Knowledge entry (around line 56):

```typescript
{ label: "Dictionary", href: "/dictionary", icon: BookA },
```

- [ ] **Step 3: Verify the page compiles**

Run: `cd /Users/ashwinrachha/coding/alfred/web && npx next build --no-lint 2>&1 | head -30`

Fix any TypeScript compilation errors.

- [ ] **Step 4: Commit**

```bash
git add web/app/(app)/dictionary/ web/app/(app)/_components/app-sidebar.tsx
git commit -m "feat(dictionary): add dictionary page and sidebar navigation"
```

---

### Task 12: Integration Test — Full Lookup Flow

**Files:**
- Create: `tests/alfred/services/test_dictionary_integration.py`

- [ ] **Step 1: Write integration test with mocked externals**

Create `tests/alfred/services/test_dictionary_integration.py`:

```python
"""Integration test for the full dictionary lookup pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alfred.services.dictionary_service import DictionaryResult, lookup


@pytest.mark.asyncio
async def test_lookup_merges_all_sources():
    """Verify lookup() calls all three sources and merges results."""
    mock_wiktionary_response = {
        "en": [
            {
                "partOfSpeech": "Adjective",
                "language": "English",
                "definitions": [
                    {
                        "definition": "Lasting for a short period of time.",
                        "examples": [],
                    },
                ],
            },
        ]
    }

    mock_wikipedia_result = {
        "query": "ephemeral",
        "items": [
            {
                "title": "Ephemeral",
                "content": "In philosophy, the ephemeral...",
            }
        ],
    }

    mock_llm = MagicMock()
    mock_llm.chat_async = AsyncMock(
        return_value="In system design, ephemeral means..."
    )

    with (
        patch(
            "alfred.services.dictionary_service.httpx.AsyncClient"
        ) as MockClient,
        patch(
            "alfred.services.dictionary_service.retrieve_wikipedia"
        ) as mock_wiki,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_wiktionary_response

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        mock_wiki.return_value = mock_wikipedia_result

        result = await lookup(
            "ephemeral", user_domains=["system_design"], llm=mock_llm
        )

    assert isinstance(result, DictionaryResult)
    assert result.word == "ephemeral"
    assert len(result.definitions) == 1
    assert result.definitions[0].part_of_speech == "Adjective"
    assert result.wikipedia_summary == "In philosophy, the ephemeral..."
    assert result.ai_explanation == "In system design, ephemeral means..."
    assert len(result.source_urls) == 2


@pytest.mark.asyncio
async def test_lookup_graceful_degradation():
    """Verify lookup still returns a result when sources fail."""
    mock_llm = MagicMock()
    mock_llm.chat_async = AsyncMock(side_effect=Exception("LLM down"))

    with (
        patch(
            "alfred.services.dictionary_service.httpx.AsyncClient"
        ) as MockClient,
        patch(
            "alfred.services.dictionary_service.retrieve_wikipedia"
        ) as mock_wiki,
    ):
        mock_response = MagicMock()
        mock_response.status_code = 404

        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(
            return_value=mock_client_instance
        )
        mock_client_instance.__aexit__ = AsyncMock(return_value=None)
        MockClient.return_value = mock_client_instance

        mock_wiki.side_effect = Exception("Wikipedia down")

        result = await lookup("nonexistent", llm=mock_llm)

    assert isinstance(result, DictionaryResult)
    assert result.word == "nonexistent"
    assert result.definitions == []
    assert result.wikipedia_summary is None
    assert result.ai_explanation is None
```

- [ ] **Step 2: Run test**

Run: `cd /Users/ashwinrachha/coding/alfred && python -m pytest tests/alfred/services/test_dictionary_integration.py -v`
Expected: Both tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/alfred/services/test_dictionary_integration.py
git commit -m "test(dictionary): add integration tests for lookup pipeline"
```

---

## Summary

| Task | Description | Files |
|------|-------------|-------|
| 1 | VocabularyEntry model | model + test |
| 2 | Alembic migration | migration |
| 3 | Dictionary service (Wiktionary + merging) | service + test |
| 4 | API routes + router registration | routes + init + registration + test |
| 5 | Frontend API layer | api wrapper + routes registry |
| 6 | React Query hooks | queries + mutations |
| 7 | Zustand store | store |
| 8 | Entry section components (8 files) | all section components |
| 9 | DictionaryEntry + SearchBar + SaveBar | main display + search + save |
| 10 | VocabularyCollection | collection grid |
| 11 | Dictionary page + sidebar nav | page + nav update |
| 12 | Integration tests | full pipeline test |
