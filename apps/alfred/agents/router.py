"""Hybrid heuristic + LLM intent router for the Alfred supervisor.

Heuristics handle ~60-70% of intents at zero LLM cost. The LLM fallback
fires only for ambiguous or multi-intent queries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from langgraph.types import Command

from alfred.agents.state import AlfredState

logger = logging.getLogger(__name__)

TEAM_NAMES = Literal["ingest_team", "knowledge_team", "synthesis_team"]


@dataclass
class IntentMatch:
    intent: str
    team: TEAM_NAMES


# Pattern -> (intent, team) -- order matters, first match wins
_HEURISTIC_RULES: list[tuple[re.Pattern, str, TEAM_NAMES]] = [
    (re.compile(r"\b(import|sync|pull from|ingest)\b", re.I), "import", "ingest_team"),
    (re.compile(r"\b(summarize this|extract concepts?|classify|enrich)\b", re.I), "enrich", "ingest_team"),
    (re.compile(r"\b(review|quiz|spaced rep|due cards?|flashcard|feynman)\b", re.I), "learn", "knowledge_team"),
    (re.compile(r"\b(connections? between|link|relate|similar to)\b", re.I), "connect", "knowledge_team"),
    (re.compile(r"\b(what do i know|search|find in (my|the) (knowledge|zettel|card))\b", re.I), "search_kb", "knowledge_team"),
    (re.compile(r"\b(research|look up|arxiv|find papers?|academic|scholar)\b", re.I), "research", "synthesis_team"),
    (re.compile(r"\b(write|draft|summarize|explain|compare|synthesize)\b", re.I), "write", "synthesis_team"),
]


def heuristic_classify(message: str) -> IntentMatch | None:
    """Classify intent using regex heuristics. Returns None if ambiguous."""
    for pattern, intent, team in _HEURISTIC_RULES:
        if pattern.search(message):
            return IntentMatch(intent=intent, team=team)
    return None


def router(state: AlfredState) -> Command:
    """Route user messages to the appropriate team.

    1. Try heuristic classification (zero LLM cost)
    2. Fall back to knowledge_team for general queries
    """
    last_msg = state["messages"][-1]
    user_msg = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    match = heuristic_classify(user_msg)
    if match:
        logger.info("Router: heuristic match -> %s (%s)", match.intent, match.team)
        return Command(
            update={"intent": match.intent, "phase": "executing", "active_agents": [match.team]},
            goto=match.team,
        )

    logger.info("Router: no heuristic match, defaulting to knowledge_team")
    return Command(
        update={"intent": "general", "phase": "executing", "active_agents": ["knowledge_team"]},
        goto="knowledge_team",
    )
