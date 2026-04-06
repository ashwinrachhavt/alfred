"""Dictionary REST API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlmodel import Session

from alfred.core.database import engine
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
