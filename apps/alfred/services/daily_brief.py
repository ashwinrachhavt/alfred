"""Service helpers for generating the Bruce Wayne Daily Brief."""

from __future__ import annotations

from datetime import date
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from alfred.services.agentic_rag import make_llm


class DailyBriefSections(BaseModel):
    """Structured payload returned by the LLM."""

    summary: str = Field(..., description="A concise summary of the user's current situation and focus.")
    recent_highlights: List[str] = Field(..., description="Positive, specific highlights from recent days.")
    top_priorities: List[str] = Field(..., description="The top three priorities for today.")
    content_idea: str = Field(..., description="One specific content idea the user could publish today.")
    reflection_question: str = Field(..., description="A single reflection question for the user.")


class DailyBrief(BaseModel):
    """Full daily brief returned to the API layer."""

    date: date
    summary: str
    recent_highlights: List[str]
    top_priorities: List[str]
    content_idea: str
    reflection_question: str


SYSTEM_PROMPT = """
You are Alfred, Bruce Wayne's AI assistant.

You are talking to a highly capable, ambitious user who juggles multiple projects.
Your job is to generate a concise "Daily Brief" in 4 parts:

1) Recent Highlights – things the user did or learned, phrased positively.
2) Top 3 Priorities – the 3 most important things to focus on today.
3) Content Seed – one specific idea for a public post (tweet/LinkedIn/Medium).
4) Reflection Question – one honest, non-cheesy question for self-reflection.

Tone Guidelines:
- Calm, precise, not dramatic.
- No generic productivity advice; be concrete and grounded.
- Do not invent detailed facts about the user's life; keep it high-level if you lack data.

You MUST respond in valid JSON with keys:
["summary", "recent_highlights", "top_priorities", "content_idea", "reflection_question"].
""".strip()


def _build_user_context(user_id: str) -> str:
    """Return lightweight context for the brief (placeholder for future memories)."""

    return (
        "The user id is {user_id}. You currently have limited explicit memory for this user, "
        "so keep the brief realistic, motivating, and forward-looking without inventing specific names or metrics. "
        "Lean on common high-leverage themes for an ambitious builder balancing research, product, and storytelling."
    ).format(user_id=user_id)


def generate_daily_brief(user_id: str) -> DailyBrief:
    """Generate a structured daily brief for the requested user."""

    llm = make_llm(temperature=0.4)
    structured_llm = llm.with_structured_output(DailyBriefSections)

    sections = structured_llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=_build_user_context(user_id)),
        ]
    )

    return DailyBrief(date=date.today(), **sections.dict())
