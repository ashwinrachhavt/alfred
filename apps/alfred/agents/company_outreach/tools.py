from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool

from alfred.core.dependencies import get_company_research_service


def _summarize_company_report(doc: dict[str, Any]) -> str:
    report = doc.get("report") or {}
    lines: list[str] = []
    exec_summary = report.get("executive_summary")
    if exec_summary:
        lines.append(f"Executive summary:\n{exec_summary}")
    sections = report.get("sections") or []
    for section in sections:
        name = section.get("name", "Untitled section")
        summary = section.get("summary", "")
        insights = section.get("insights") or []
        lines.append(f"\n## {name}\n{summary}")
        for insight in insights:
            lines.append(f"- {insight}")
    for key, label in (
        ("risks", "Risks"),
        ("opportunities", "Opportunities"),
        ("recommended_actions", "Recommended actions"),
        ("references", "References"),
    ):
        items = report.get(key) or []
        if items:
            lines.append(f"\n{label}:")
            for item in items:
                lines.append(f"- {item}")
    return "\n".join(lines).strip() or "(empty report)"


class CompanyResearchTool(BaseTool):
    name: str = "company_research"
    description: str = (
        "Call the in-house company research agent. Input should be the exact company name. "
        "It returns a structured research report covering mission, products, GTM, funding, and risks."
    )

    def _run(self, company: str) -> str:  # type: ignore[override]
        try:
            doc = get_company_research_service().generate_report(company)
            return _summarize_company_report(doc)
        except Exception as exc:  # pragma: no cover - propagate friendly error
            return f"(error) company research failed: {exc}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)
