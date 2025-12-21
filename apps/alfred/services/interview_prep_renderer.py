from __future__ import annotations

from dataclasses import dataclass

from alfred.schemas.interview_prep import PrepDoc


@dataclass
class InterviewPrepRenderer:
    """Render a structured PrepDoc into a readable Markdown document."""

    def render(self, *, company: str, role: str, doc: PrepDoc) -> str:
        lines: list[str] = [f"# Interview Prep — {company} ({role})", ""]

        lines += [
            "## Company Intelligence",
            (doc.company_overview or "").strip() or "(missing)",
            "",
        ]
        lines += ["## Role Analysis", (doc.role_analysis or "").strip() or "(missing)", ""]

        lines.append("## Story Bank (STAR)")
        if doc.star_stories:
            for idx, s in enumerate(doc.star_stories, start=1):
                title = f" — {s.title}" if s.title else ""
                lines += [
                    f"### Story {idx}{title}",
                    f"- Situation: {s.situation}",
                    f"- Task: {s.task}",
                    f"- Action: {s.action}",
                    f"- Result: {s.result}",
                ]
                if s.skills:
                    lines.append(f"- Skills: {', '.join(s.skills)}")
                lines.append("")
        else:
            lines += ["(none)", ""]

        lines.append("## Likely Questions")
        if doc.likely_questions:
            for q in doc.likely_questions:
                lines.append(f"- **Q:** {q.question}")
                lines.append(f"  - Suggested: {q.suggested_answer}")
                if q.focus_areas:
                    lines.append(f"  - Focus: {', '.join(q.focus_areas)}")
            lines.append("")
        else:
            lines += ["(none)", ""]

        lines.append("## Technical Topics (Prioritized)")
        if doc.technical_topics:
            for t in doc.technical_topics:
                lines.append(f"- (P{t.priority}) {t.topic}")
                if t.notes:
                    lines.append(f"  - Notes: {t.notes}")
                if t.resources:
                    lines.append(f"  - Resources: {', '.join(t.resources)}")
            lines.append("")
        else:
            lines += ["(none)", ""]

        return "\n".join(lines).strip() + "\n"


__all__ = ["InterviewPrepRenderer"]
