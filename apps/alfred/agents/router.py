"""Hybrid heuristic + LLM intent router for the Alfred supervisor.

Heuristics handle ~60-70% of intents at zero LLM cost. The LLM fallback
fires only for ambiguous or multi-intent queries. Conversational messages
(questions, greetings, opinions) go to the chat node — no tools needed.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from langgraph.types import Command

from alfred.agents.state import AlfredState

logger = logging.getLogger(__name__)

DEST_NAMES = Literal["ingest_team", "knowledge_team", "synthesis_team", "chat"]


@dataclass
class IntentMatch:
    intent: str
    destination: DEST_NAMES


# ── Conversational patterns (matched FIRST — these skip tools entirely) ──

_CONVERSATIONAL_PATTERNS: list[re.Pattern] = [
    re.compile(r"^(hi|hello|hey|sup|yo|good (morning|afternoon|evening))\b", re.I),
    re.compile(r"^(thanks?|thank you|thx)\b", re.I),
    re.compile(r"^(what|who|where|when|why|how)\b.{0,80}\?$", re.I),  # short questions
    re.compile(r"\b(what do you think|your opinion|thoughts on|do you know)\b", re.I),
    re.compile(r"\b(can you|could you|tell me|help me understand|explain)\b(?!.*(create|make|write a zettel|draft a card))", re.I),
    re.compile(r"\b(what is|what are|what's|who is|who are|define)\b", re.I),
    re.compile(r"\b(recommend|suggest|advice|idea)\b(?!.*(link|connect|zettel))", re.I),
]

# ── Action patterns (these DO need tools) — order matters, first match wins ──

_ACTION_RULES: list[tuple[re.Pattern, str, DEST_NAMES]] = [
    # Explicit zettel/card creation — user must actually ask to create
    (re.compile(r"\b(create|make|add|new)\b.{0,30}\b(zettel|card|note)\b", re.I), "create", "knowledge_team"),
    # Import / ingest
    (re.compile(r"\b(import|sync|pull from|ingest)\b", re.I), "import", "ingest_team"),
    (re.compile(r"\b(summarize this|extract concepts?|classify|enrich)\b", re.I), "enrich", "ingest_team"),
    # Learning / review — "feynman" alone is a topic, needs "feynman technique/method" + action verb
    (re.compile(r"\b(review my|quiz me|spaced rep|due cards?|flashcard|start.{0,10}feynman)\b", re.I), "learn", "knowledge_team"),
    # Connections
    (re.compile(r"\b(connections? between|link these|relate these|similar cards?)\b", re.I), "connect", "knowledge_team"),
    # Explicit KB search
    (re.compile(r"\b(search|find)\b.{0,20}\b(my |the )?(knowledge|zettel|card|kb)\b", re.I), "search_kb", "knowledge_team"),
    (re.compile(r"\bwhat do i know about\b", re.I), "search_kb", "knowledge_team"),
    # Research (external)
    (re.compile(r"\b(research|look up|arxiv|find papers?|academic|scholar)\b", re.I), "research", "synthesis_team"),
    # Writing — only when explicitly asking for a written artifact
    (re.compile(r"\b(write|draft|compose)\b.{0,30}\b(essay|article|summary|brief|post|zettel|card)\b", re.I), "write", "synthesis_team"),
    (re.compile(r"\b(synthesize|compare and contrast)\b", re.I), "write", "synthesis_team"),
]


def _is_conversational(message: str) -> bool:
    """Check if the message is conversational (no tools needed)."""
    return any(p.search(message) for p in _CONVERSATIONAL_PATTERNS)


def _classify_action(message: str) -> IntentMatch | None:
    """Classify intent using regex heuristics. Returns None if ambiguous."""
    for pattern, intent, destination in _ACTION_RULES:
        if pattern.search(message):
            return IntentMatch(intent=intent, destination=destination)
    return None


def router(state: AlfredState) -> Command:
    """Route user messages to the appropriate destination.

    Priority:
    1. Action heuristics — explicit tool-needing commands
    2. Conversational patterns — questions, greetings, opinions → chat node
    3. Default → chat node (safer than routing to tools)
    """
    last_msg = state["messages"][-1]
    user_msg = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    # 1. Check for explicit action intent first (these DO need tools)
    action = _classify_action(user_msg)
    if action:
        logger.info("Router: action match -> %s (%s)", action.intent, action.destination)
        return Command(
            update={"intent": action.intent, "phase": "executing", "active_agents": [action.destination]},
            goto=action.destination,
        )

    # 2. Conversational or unmatched → chat (no tools, just answer)
    if _is_conversational(user_msg):
        logger.info("Router: conversational -> chat")
    else:
        logger.info("Router: no action match, defaulting to chat")

    return Command(
        update={"intent": "chat", "phase": "executing", "active_agents": ["chat"]},
        goto="chat",
    )
