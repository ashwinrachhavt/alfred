"""Synchronous single-card enrichment (Track B equivalent).

Used by POST /api/zettels/cards/{id}/resume-enrichment to re-run the
Track B enrichment pass on a card that was either never enriched (the
creation stream aborted) or where the prior enrichment attempt failed.

This is deliberately non-streaming: the caller is a plain JSON POST, so
we build the prompt, make a single synchronous LLM call, parse the JSON,
and persist the results. Track A (embedding + auto-links) is NOT re-run;
that is a separate concern and has its own entry points.

The key invariant this module preserves is the updated-at-corruption
learning: persisting enrichment metadata must NOT mutate the card's
updated_at timestamp. We use Core UPDATE with synchronize_session=False
so only the columns we explicitly pass land in the SET clause.
bloom_history append-only audit trail is handled the same way as in
ZettelCreationStream._persist_bloom_inference.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update as sa_update
from sqlmodel import Session, select

from alfred.core.llm_factory import get_chat_model
from alfred.core.settings import settings
from alfred.core.utils import clamp_int, utcnow_naive
from alfred.models.zettel import ZettelCard
from alfred.services.sse_base import SSEStreamOrchestrator

log = logging.getLogger(__name__)


def _build_enrichment_prompt(card: ZettelCard) -> list[dict[str, str]]:
    """Single-card enrichment prompt.

    Mirrors Track B's shape but omits the KB context and sibling-title
    block (this is a resume flow; we don't need fresh KB statistics to
    fix one card's enrichment).
    """
    content_str = card.content or ""
    tags_str = ", ".join(card.tags or [])
    system = (
        "You are a knowledge analyst for a Zettelkasten system. "
        "The user has an existing knowledge card whose enrichment either "
        "never completed or failed. Re-run enrichment and return the same "
        "JSON structure Track B uses.\n\n"
        "Classify the card on Bloom's Taxonomy. "
        "Level 1 (Remember): bare facts or definitions. "
        "Level 2 (Understand): explanation in the user's own words. "
        "Level 3 (Apply): use in context. "
        "Level 4 (Analyze): decomposition or comparison. "
        "Level 5 (Evaluate): judgment or critique. "
        "Level 6 (Create): synthesis or new framing. "
        "Pick the LOWEST level that fits (err conservative).\n\n"
        "Respond ONLY with valid JSON (no markdown fences, no commentary):\n"
        "{\n"
        '  "enrichment": {\n'
        '    "suggested_title": "..." or null (only if meaningfully better),\n'
        '    "summary": "one-sentence distillation",\n'
        '    "suggested_tags": ["tag1", "tag2"],\n'
        '    "suggested_topic": "..." or null\n'
        "  },\n"
        '  "bloom_assessment": {\n'
        '    "inferred_level": 1-6,\n'
        '    "rationale": "one sentence",\n'
        '    "evidence_phrases": ["...", "..."]\n'
        "  }\n"
        "}"
    )
    user = (
        f"Existing card to re-enrich:\n"
        f"Title: {card.title}\n"
        f"Content: {content_str}\n"
        f"Tags: {tags_str}\n"
        f"Topic: {card.topic or 'not set'}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


@dataclass
class EnrichmentService:
    """Run Track B-equivalent enrichment synchronously on a single card."""

    session: Session

    # ------------------------------------------------------------------
    # Idempotency / state checks
    # ------------------------------------------------------------------
    def _is_successfully_enriched(self, card: ZettelCard) -> bool:
        return (
            card.enrichment_last_error is None
            and card.enrichment_attempted_at is not None
            and card.bloom_source == "ai_inferred"
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_sync(self, card_id: int) -> dict[str, Any] | None:
        """Run enrichment for card_id.

        Returns:
            - None if the card does not exist (route layer returns 404).
            - {"status": "already_complete", "card_id": id} if the card
              was already successfully enriched.
            - {"status": "complete", "card_id": id, "bloom_level": N}
              on success (bloom_level may be unchanged if the LLM did
              not return a bloom_assessment).
            - {"status": "failed", "error": "..."} if the LLM call or
              parse failed. enrichment_last_error is set on the card.
        """
        card = self.session.get(ZettelCard, card_id)
        if card is None:
            return None

        if self._is_successfully_enriched(card):
            return {"status": "already_complete", "card_id": card.id}

        try:
            messages = _build_enrichment_prompt(card)
            llm = get_chat_model(model=settings.zettel_analysis_model)
            response = llm.invoke(messages)
            raw = response.content if hasattr(response, "content") else str(response)
            if isinstance(raw, list):  # some providers return content parts
                raw = "".join(
                    part.get("text", "") if isinstance(part, dict) else str(part) for part in raw
                )
            data = SSEStreamOrchestrator._parse_structured_json(str(raw or ""))
            if data is None:
                raise ValueError("Failed to parse AI enrichment response")
        except Exception as exc:
            self._persist_failure(card_id, exc)
            return {"status": "failed", "error": str(exc)[:500]}

        bloom_level = self._persist_success(card_id, data)
        return {"status": "complete", "card_id": card_id, "bloom_level": bloom_level}

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _persist_failure(self, card_id: int, exc: BaseException) -> None:
        """Record an enrichment failure without mutating updated_at."""
        stmt = (
            sa_update(ZettelCard)
            .where(ZettelCard.id == card_id)
            .values(
                enrichment_attempted_at=utcnow_naive(),
                enrichment_last_error=str(exc)[:500],
            )
            .execution_options(synchronize_session=False)
        )
        self.session.exec(stmt)
        self.session.commit()

    def _persist_success(self, card_id: int, data: dict[str, Any]) -> int:
        """Apply enrichment + Bloom data to the card.

        Returns the card's bloom_level after persistence (either the
        newly inferred level, or the pre-existing level if the LLM did
        not include a valid bloom_assessment).
        """
        values: dict[str, Any] = {
            "enrichment_attempted_at": utcnow_naive(),
            "enrichment_last_error": None,
        }

        # Read current Bloom history + level once so we can decide whether
        # to append a new entry.
        row = self.session.exec(
            select(ZettelCard.bloom_history, ZettelCard.bloom_level).where(ZettelCard.id == card_id)
        ).one_or_none()
        if row is None:
            # Shouldn't happen - run_sync already checked existence, but be
            # defensive for concurrent deletes.
            return 0
        existing_history, current_level = (row[0], row[1]) if isinstance(row, tuple) else (None, 1)

        enrichment = data.get("enrichment") or {}
        if isinstance(enrichment, dict):
            summary = enrichment.get("summary")
            if isinstance(summary, str) and summary.strip():
                values["summary"] = summary.strip()
            suggested_topic = enrichment.get("suggested_topic")
            if isinstance(suggested_topic, str) and suggested_topic.strip():
                values["topic"] = suggested_topic.strip()
            suggested_tags = enrichment.get("suggested_tags")
            if isinstance(suggested_tags, list):
                cleaned_tags = [
                    t.strip() for t in suggested_tags if isinstance(t, str) and t.strip()
                ]
                if cleaned_tags:
                    values["tags"] = cleaned_tags
            suggested_title = enrichment.get("suggested_title")
            if isinstance(suggested_title, str) and suggested_title.strip():
                values["title"] = suggested_title.strip()

        new_bloom_level = int(current_level or 1)
        bloom = data.get("bloom_assessment")
        if isinstance(bloom, dict):
            level = bloom.get("inferred_level")
            rationale = bloom.get("rationale") or ""
            if isinstance(level, int) and 1 <= level <= 6:
                clamped = clamp_int(level, lo=1, hi=6)
                values["bloom_level"] = clamped
                values["bloom_source"] = "ai_inferred"
                new_entry = {
                    "level": clamped,
                    "source": "ai_inferred",
                    "at": utcnow_naive().isoformat(),
                    "rationale": rationale,
                }
                values["bloom_history"] = [*(existing_history or []), new_entry]
                new_bloom_level = clamped

        stmt = (
            sa_update(ZettelCard)
            .where(ZettelCard.id == card_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )
        self.session.exec(stmt)
        self.session.commit()
        return new_bloom_level


__all__ = ["EnrichmentService"]
