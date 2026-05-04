"""Seed default system-owned ResearchAgentSpec rows.

Idempotent: upserts by slug.
"""

from __future__ import annotations

import logging

from sqlmodel import Session, select

from alfred.models.research_agent import ResearchAgentSpecRow

logger = logging.getLogger(__name__)


DEFAULT_SPECS: list[dict] = [
    {
        "slug": "general-research",
        "name": "General Research",
        "description": "Broad topic research across web, papers, and your knowledge base.",
        "instructions": (
            "You are Alfred's general research orchestrator.\n\n"
            "For each request:\n"
            "1. Call write_todos with 3-6 focused research questions.\n"
            "2. Delegate each question to the appropriate sub-agent via the task tool. "
            "Run independent questions in parallel.\n"
            "3. After sub-agents return, synthesize findings with consolidated citations.\n"
            "4. Write the final report to /final_report.md. Use [1], [2] format for inline citations.\n"
            "Be rigorous. Prefer primary sources. Flag uncertainty explicitly."
        ),
        "model_name": None,
        "tool_allowlist": ["search_kb"],
        "subagents": [
            {
                "name": "web-researcher",
                "description": "Delegate topics needing current web information. Give one question at a time.",
                "system_prompt": (
                    "You research topics using web search. Use search_web to find current sources, "
                    "then scrape_url to pull full content from the most promising 2-3 pages. "
                    "Return a concise synthesis with inline URLs as citations."
                ),
                "tools": ["search_web", "scrape_url"],
            },
            {
                "name": "paper-researcher",
                "description": "Delegate questions requiring academic rigor. One question at a time.",
                "system_prompt": (
                    "You research topics using academic papers. Use search_papers (default arxiv; "
                    "try semantic_scholar for cross-disciplinary topics). Return a synthesis that "
                    "foregrounds the most-cited / most-recent works. Include DOIs or arxiv ids."
                ),
                "tools": ["search_papers"],
            },
            {
                "name": "kb-researcher",
                "description": "Delegate questions where the user may already have relevant notes.",
                "system_prompt": (
                    "You search the user's personal zettelkasten. Use search_kb to find relevant "
                    "cards. Quote card ids and titles when citing. If nothing relevant exists, say so."
                ),
                "tools": ["search_kb"],
            },
        ],
    },
    {
        "slug": "paper-research",
        "name": "Academic Paper Research",
        "description": "Deep survey of academic literature on a topic.",
        "instructions": (
            "You are a literature-review orchestrator. For each request:\n"
            "1. Use write_todos to plan 4-8 sub-queries covering different angles "
            "(foundational papers, recent work, competing methods, critiques, applications).\n"
            "2. Delegate each to the paper-surveyor sub-agent.\n"
            "3. Synthesize into /final_report.md with a citation list, grouped by theme."
        ),
        "model_name": None,
        "tool_allowlist": [],
        "subagents": [
            {
                "name": "paper-surveyor",
                "description": "Survey academic literature on a single sub-question. One question per call.",
                "system_prompt": (
                    "You survey academic papers. For each question, use search_papers with both arxiv "
                    "and semantic_scholar. Prioritize citation count and recency. Return a structured "
                    "summary: paper title, authors, year, key claim, relevance to the question."
                ),
                "tools": ["search_papers"],
            },
        ],
    },
    {
        "slug": "web-research",
        "name": "Web Research",
        "description": "Fast, web-only research. No academic sources, no KB lookups.",
        "instructions": (
            "You are a web research orchestrator. Plan 3-5 focused queries via write_todos, "
            "delegate each to the web-scout sub-agent, then synthesize findings to /final_report.md. "
            "Cite every claim with a URL."
        ),
        "model_name": None,
        "tool_allowlist": [],
        "subagents": [
            {
                "name": "web-scout",
                "description": "Research a single focused web query. One query per call.",
                "system_prompt": (
                    "You research a single web query. Start with search_web (max 8 results). Pick the "
                    "2-3 most promising URLs and use scrape_url to get full content. Return a concise "
                    "synthesis with inline URL citations."
                ),
                "tools": ["search_web", "scrape_url"],
            },
        ],
    },
]


def seed_research_agents(db: Session) -> int:
    """Upsert default system specs. Returns count of rows created or updated."""
    count = 0
    for spec in DEFAULT_SPECS:
        existing = db.exec(
            select(ResearchAgentSpecRow).where(ResearchAgentSpecRow.slug == spec["slug"])
        ).first()
        if existing is None:
            row = ResearchAgentSpecRow(
                slug=spec["slug"],
                name=spec["name"],
                description=spec["description"],
                instructions=spec["instructions"],
                model_name=spec["model_name"],
                tool_allowlist=list(spec["tool_allowlist"]),
                connector_bindings={},
                subagents=list(spec["subagents"]),
                is_system=True,
            )
            db.add(row)
            count += 1
        else:
            existing.name = spec["name"]
            existing.description = spec["description"]
            existing.instructions = spec["instructions"]
            existing.model_name = spec["model_name"]
            existing.tool_allowlist = list(spec["tool_allowlist"])
            existing.subagents = list(spec["subagents"])
            existing.is_system = True
            db.add(existing)
            count += 1
    db.commit()
    logger.info("Seeded %d research agent specs", count)
    return count


def main() -> None:
    """CLI entry point."""
    from alfred.core.database import SessionLocal

    with SessionLocal() as db:
        seed_research_agents(db)


if __name__ == "__main__":
    main()
