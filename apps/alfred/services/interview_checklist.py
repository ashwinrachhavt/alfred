from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from alfred.schemas.interview_prep import InterviewChecklist


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def _extract_meeting_links(source: dict[str, Any] | None) -> list[str]:
    if not isinstance(source, dict):
        return []
    detected = source.get("detected")
    if isinstance(detected, dict):
        links = detected.get("meeting_links") or []
        if isinstance(links, list):
            return [str(x) for x in links if x]
    return []


def _fmt_interview_time(dt: Optional[datetime]) -> str:
    if dt is None:
        return "Unknown time"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass
class InterviewChecklistService:
    """Generate a day-of checklist from an interview prep record."""

    def generate(
        self,
        *,
        company: str,
        role: str,
        interview_type: str | None,
        interview_date: datetime | None,
        prep_doc: dict[str, Any] | None = None,
        source: dict[str, Any] | None = None,
    ) -> InterviewChecklist:
        company = (company or "").strip() or "Unknown Company"
        role = (role or "").strip() or "Unknown Role"
        i_type = (interview_type or "").strip().lower() or "unknown"

        meeting_links = _extract_meeting_links(source)
        when = _fmt_interview_time(interview_date)

        timeline = [
            f"T-60m: Setup + environment check ({i_type})",
            "T-30m: Review top talking points + STAR stories",
            "T-10m: Open notes + questions-to-ask; breathe",
            "T-0m: Start strong: clarify agenda + expectations",
        ]
        if i_type in {"onsite", "on-site"}:
            timeline.insert(0, "T-120m: Travel buffer + arrival plan")

        talking_points = [
            "2-sentence intro (role fit + motivation)",
            "1-2 relevant wins (impact + metrics)",
            "1 current deep-dive story (technical + collaboration)",
            "Why this company / why now",
            "Close: excitement + next steps",
        ]

        questions_to_ask = [
            "What does success look like in the first 30/60/90 days?",
            "What are the biggest technical risks for this team right now?",
            "How do you make architectural decisions and manage tradeoffs?",
            "How do you evaluate and grow engineers here?",
        ]

        setup = [
            "Laptop charged + backup power",
            "Stable internet + quiet room (for video/phone)",
            "Camera/mic test + screen sharing ready",
            "Resume + role description + prep doc accessible",
        ]
        if meeting_links:
            setup.append(f"Meeting link ready: {meeting_links[0]}")

        mindset = [
            "Be curious. Ask clarifying questions early.",
            "Narrate tradeoffs. Communicate assumptions.",
            "If stuck: state approach, simplify, and iterate.",
            "End with a clean recap of decisions and next steps.",
        ]

        md_lines: list[str] = [
            f"# Day-of Checklist — {company} ({role})",
            "",
            f"- Interview time: {when}",
            f"- Type: {i_type}",
        ]
        if meeting_links:
            md_lines.append(f"- Meeting link: {meeting_links[0]}")
        md_lines += [
            "",
            "## Timeline",
            *[f"- {item}" for item in timeline],
            "",
            "## Top talking points",
            *[f"- {item}" for item in talking_points],
            "",
            "## Questions to ask",
            *[f"- {item}" for item in questions_to_ask],
            "",
            "## Setup",
            *[f"- {item}" for item in setup],
            "",
            "## Mindset",
            *[f"- {item}" for item in mindset],
        ]

        markdown = "\n".join(md_lines).strip() + "\n"
        return InterviewChecklist(
            markdown=markdown,
            timeline=timeline,
            talking_points=talking_points,
            questions_to_ask=questions_to_ask,
            setup=setup,
            mindset=mindset,
        )


__all__ = ["InterviewChecklistService"]
