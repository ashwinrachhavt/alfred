"""Writing agent tools -- content synthesis and zettel creation.

Tools for drafting zettels, progressive summarization, Feynman explanations,
comparing perspectives, and creating synthesized zettels from multiple sources.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool

from alfred.core.database import SessionLocal
from alfred.services.zettelkasten_service import ZettelkastenService

logger = logging.getLogger(__name__)


def _get_zettel_service() -> ZettelkastenService:
    """Create a ZettelkastenService with a fresh DB session."""
    session = SessionLocal()
    return ZettelkastenService(session=session)


@tool
def draft_zettel(title: str, context: str | None = None, related_cards: list[int] | None = None) -> str:
    """Generate a draft zettel using LLM. Returns instructions for the agent to synthesize."""
    svc = _get_zettel_service()
    try:
        # Gather related context
        context_parts = [f"Title: {title}"]
        if context:
            context_parts.append(f"Context: {context}")

        if related_cards:
            for card_id in related_cards[:5]:
                card = svc.get_card(card_id)
                if card:
                    context_parts.append(f"Related: {card.title} - {card.summary or card.content or ''}")

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()
        system_prompt = (
            "You are a knowledge synthesizer. Create a concise, atomic zettel card. "
            "Return ONLY valid JSON: {\"title\": \"...\", \"content\": \"2-4 sentences\", "
            "\"summary\": \"one sentence\", \"tags\": [...], \"topic\": \"...\"}"
        )
        user_prompt = "\n\n".join(context_parts)

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            draft = json.loads(json_match.group())
        else:
            draft = {"error": "Failed to generate draft"}

        return json.dumps({
            "ok": True,
            "draft": draft,
            "message": "Review and edit before creating the card",
        })
    except Exception as exc:
        logger.error("draft_zettel failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def progressive_summary(zettel_id: int, level: int = 1) -> str:
    """Create a progressive summary at different detail levels. Level 1-5, higher = more detail."""
    svc = _get_zettel_service()
    try:
        card = svc.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()

        # Define detail levels
        level_instructions = {
            1: "1 sentence, extreme compression",
            2: "2-3 sentences, key insight only",
            3: "1 paragraph, main concept + context",
            4: "2 paragraphs, concept + implications",
            5: "Full detail, concept + examples + connections",
        }

        instruction = level_instructions.get(level, level_instructions[3])
        system_prompt = f"Summarize this knowledge card at detail level {level}: {instruction}"
        user_prompt = f"Title: {card.title}\n\nContent: {card.content or card.summary or ''}"

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        summary = response.content if hasattr(response, "content") else str(response)

        return json.dumps({
            "zettel_id": zettel_id,
            "title": card.title,
            "level": level,
            "summary": summary,
        })
    except Exception as exc:
        logger.error("progressive_summary failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def feynman_explain(zettel_id: int, audience: str = "beginner") -> str:
    """Generate a Feynman-style simple explanation. Audience: beginner, intermediate, advanced."""
    svc = _get_zettel_service()
    try:
        card = svc.get_card(zettel_id)
        if not card:
            return json.dumps({"error": f"Zettel {zettel_id} not found"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()

        audience_context = {
            "beginner": "Explain like I'm 5. Use everyday analogies, no jargon.",
            "intermediate": "Explain to a college student. Use clear examples.",
            "advanced": "Explain to an expert. Include nuance and edge cases.",
        }

        context = audience_context.get(audience, audience_context["beginner"])
        system_prompt = f"Use the Feynman technique. {context}"
        user_prompt = f"Concept: {card.title}\n\nDetails: {card.content or card.summary or ''}"

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        explanation = response.content if hasattr(response, "content") else str(response)

        return json.dumps({
            "zettel_id": zettel_id,
            "title": card.title,
            "audience": audience,
            "explanation": explanation,
        })
    except Exception as exc:
        logger.error("feynman_explain failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def compare_perspectives(zettel_ids: list[int]) -> str:
    """Compare multiple zettels to find similarities, differences, and contradictions."""
    svc = _get_zettel_service()
    try:
        if len(zettel_ids) < 2:
            return json.dumps({"error": "Need at least 2 zettels to compare"})

        cards = []
        for zid in zettel_ids[:5]:  # Limit to 5 cards
            card = svc.get_card(zid)
            if card:
                cards.append(card)

        if len(cards) < 2:
            return json.dumps({"error": "Could not load enough cards for comparison"})

        from alfred.core.llm_factory import get_chat_model

        model = get_chat_model()

        # Build comparison context
        card_texts = [
            f"Card {i+1} ({card.title}):\n{card.content or card.summary or ''}"
            for i, card in enumerate(cards)
        ]

        system_prompt = (
            "Compare these perspectives. Return JSON: "
            "{\"similarities\": [...], \"differences\": [...], \"contradictions\": [...], "
            "\"synthesis\": \"unified insight\"}"
        )
        user_prompt = "\n\n".join(card_texts)

        response = model.invoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])
        result_text = response.content if hasattr(response, "content") else str(response)

        # Parse JSON
        import re
        json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
        if json_match:
            comparison = json.loads(json_match.group())
        else:
            comparison = {"error": "Failed to parse comparison"}

        return json.dumps({
            "compared_cards": [{"id": c.id, "title": c.title} for c in cards],
            "comparison": comparison,
        })
    except Exception as exc:
        logger.error("compare_perspectives failed: %s", exc)
        return json.dumps({"error": str(exc)})


@tool
def create_zettel_from_synthesis(title: str, content: str, tags: list[str], topic: str | None = None, source_cards: list[int] | None = None) -> str:
    """Create a new zettel from synthesized content. Links to source cards if provided."""
    svc = _get_zettel_service()
    try:
        # Create the card
        card = svc.create_card(
            title=title,
            content=content,
            tags=tags,
            topic=topic,
            status="active",
        )

        # Link to source cards
        links_created = 0
        if source_cards:
            for source_id in source_cards:
                try:
                    svc.create_link(
                        from_card_id=card.id or 0,
                        to_card_id=source_id,
                        type="synthesis",
                        context="Synthesized from multiple sources",
                        bidirectional=True,
                    )
                    links_created += 1
                except Exception as link_exc:
                    logger.debug("Failed to link to source %d: %s", source_id, link_exc)

        return json.dumps({
            "ok": True,
            "card_id": card.id,
            "title": card.title,
            "links_created": links_created,
            "status": "created",
        })
    except Exception as exc:
        logger.error("create_zettel_from_synthesis failed: %s", exc)
        return json.dumps({"error": str(exc)})


# List of all writing tools for agent registration
WRITING_TOOLS = [
    draft_zettel,
    progressive_summary,
    feynman_explain,
    compare_perspectives,
    create_zettel_from_synthesis,
]
