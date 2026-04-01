"""Zettel decomposition service.

Decomposes document enrichments into multiple atomic zettel cards using LLM.
"""

from __future__ import annotations

import json
import logging

logger = logging.getLogger(__name__)

MAX_CARDS = 10
TEXT_TRUNCATE_LIMIT = 8000


def build_decomposition_prompt(
    title: str,
    summary: str | None,
    cleaned_text: str,
    topics: dict | None = None,
) -> str:
    """Build an LLM prompt that asks the model to decompose a document into 2-10 atomic zettel cards.

    Args:
        title: Document title
        summary: Document summary (short form preferred)
        cleaned_text: Full document text (will be truncated to ~8000 chars)
        topics: Topics dict with 'primary' and 'secondary' keys

    Returns:
        Prompt string for the LLM
    """
    # Truncate cleaned_text
    text = (cleaned_text or "").strip()[:TEXT_TRUNCATE_LIMIT]

    # Extract topic context
    topic_context = ""
    if topics:
        if isinstance(topics, dict):
            primary = topics.get("primary", "")
            secondary = topics.get("secondary", [])
            if primary:
                topic_context += f"\nPrimary topic: {primary}"
            if secondary and isinstance(secondary, list):
                topic_context += f"\nSecondary topics: {', '.join(secondary)}"

    summary_context = ""
    if summary:
        summary_context = f"\nSummary: {summary}"

    prompt = f"""TASK: Decompose the following document into 2-{MAX_CARDS} atomic knowledge cards (zettels).

DOCUMENT CONTEXT:
Title: {title}{topic_context}{summary_context}

FULL TEXT:
{text}

INSTRUCTIONS:
- Each card should capture ONE core concept, insight, or piece of knowledge
- Cards should be atomic (self-contained, can stand alone)
- Aim for 2-{MAX_CARDS} cards depending on document complexity
- Each card needs: title (max 80 chars), content (2-4 sentences), tags (2-5 lowercase tags)

OUTPUT FORMAT (JSON array):
[
  {{
    "title": "Concept Name",
    "content": "Detailed explanation in 2-4 sentences.",
    "tags": ["tag1", "tag2", "tag3"]
  }},
  ...
]

Return ONLY the JSON array, no additional text."""

    return prompt


def parse_decomposition_response(response: str) -> list[dict]:
    """Parse the LLM JSON response into a list of card dicts.

    Handles markdown code fences, invalid JSON, and caps at MAX_CARDS.

    Args:
        response: Raw LLM response (JSON or markdown-wrapped JSON)

    Returns:
        List of card dicts with keys: title, content, tags
        Returns empty list on parse failure
    """
    raw = (response or "").strip()
    if not raw:
        return []

    # Strip markdown code fences if present
    if raw.startswith("```"):
        lines = raw.split("\n")
        # Remove first line (```json or ```)
        lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()

    # Try parsing as JSON
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse decomposition response as JSON: %s", exc)
        return []

    # Validate structure
    if not isinstance(data, list):
        logger.warning("Decomposition response is not a JSON array")
        return []

    # Cap at MAX_CARDS
    cards = data[:MAX_CARDS]

    # Validate each card has required fields
    valid_cards = []
    for card in cards:
        if not isinstance(card, dict):
            continue
        if not card.get("title") or not card.get("content"):
            continue
        # Ensure tags is a list
        if "tags" not in card:
            card["tags"] = []
        elif not isinstance(card["tags"], list):
            card["tags"] = []

        valid_cards.append({
            "title": str(card["title"]).strip(),
            "content": str(card["content"]).strip(),
            "tags": [str(t).strip() for t in card["tags"] if t],
        })

    return valid_cards
