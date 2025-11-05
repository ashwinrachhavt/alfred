# -*- coding: utf-8 -*-
"""
Philosophical LinkedIn & Cover Letter Assistant (CrewAI >= 0.28)
- Uses Crew.kickoff() which returns CrewOutput (not JSON/string).
- Reads per-task output via task.output after kickoff.
- Adds max_iter on agents to avoid long loops.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from dotenv import load_dotenv
from pydantic import BaseModel, Field

from alfred.connectors.crewai import (
    CrewAIUnavailable,
    CrewTools,
    load_crewai_classes,
    load_crewai_tools,
)
from alfred.prompts import load_prompt

if TYPE_CHECKING:  # pragma: no cover - import-time typing only
    from crewai import Agent as CrewAIAgent, Crew as CrewAICrew, Process as CrewAIProcess, Task as CrewAITask
else:
    CrewAIAgent = CrewAICrew = CrewAIProcess = CrewAITask = Any

__all__ = [
    "CandidateProfile",
    "JobApplicationContext",
    "LinkedInContext",
    "PhilosophicalApplicationCrew",
    "kickoff_research_writer",
]

load_dotenv()

Agent = Crew = Process = Task = None  # type: ignore[assignment]
_crew_import_error: Optional[Exception] = None
_tooling_cache: Optional[CrewTools] = None


def _ensure_crewai_loaded() -> None:
    """Load CrewAI classes on demand and surface helpful guidance when absent."""

    global Agent, Crew, Process, Task, _crew_import_error

    if Agent is not None:
        return

    if _crew_import_error is not None:
        raise RuntimeError(str(_crew_import_error)) from _crew_import_error

    try:
        Agent, Crew, Process, Task = load_crewai_classes()
    except CrewAIUnavailable as exc:
        _crew_import_error = exc
        raise RuntimeError(str(exc)) from exc


def _get_tooling() -> CrewTools:
    """Fetch optional crewai_tools integrations once."""

    global _tooling_cache
    if _tooling_cache is None:
        _tooling_cache = load_crewai_tools()
    return _tooling_cache

# ------------------ Static URL Sources ------------------

# Public profile and publications for candidate context. Used by researcher.
DEFAULT_PROFILE_URLS: List[str] = [
    "https://ashwinrachha.vercel.app/",
    "https://www.linkedin.com/in/ashwinrachha/",
    "https://medium.com/@ashwin_rachha",
    "https://medium.com/@ashwin_rachha/about",
    "https://scholar.google.com/citations?user=opsMRzEAAAAJ&hl=en",
    "https://www.kaggle.com/ashwinrachha1",
    "https://vtechworks.lib.vt.edu/items/3d08a8cd-effe-4e41-9830-0204637e53da",
    "https://arxiv.org/abs/2012.07587",
    "https://ieeexplore.ieee.org/document/10893211",
    "https://ieeexplore.ieee.org/document/10115140",
]

# ------------------ Data Models ------------------


class JobApplicationContext(BaseModel):
    company_name: str
    position: str
    job_description: str
    company_values: Optional[List[str]] = None
    company_culture: Optional[str] = None
    philosophical_approach: str = Field(
        default="blended"
    )  # stoicism|virtue_ethics|existentialism|blended


class LinkedInContext(BaseModel):
    connection_name: str
    connection_title: str
    company_name: str
    shared_interests: List[str]
    interaction_purpose: str
    philosophical_tone: str = Field(
        default="authentic_engagement"
    )  # neutral|concise|authentic_engagement


class CandidateProfile(BaseModel):
    name: str
    headline: str
    skills: List[str]
    experience: List[Dict[str, Any]]
    publications: Optional[List[str]] = None
    achievements: Optional[List[str]] = None
    voice_preferences: Dict[str, Any] = Field(
        default={
            "tone": "professional",
            "verbosity": "concise",
            "avoid": ["buzzwords", "self-aggrandizing"],
        }
    )


# ------------------ Prompt Constraints ------------------

PHILOSOPHY_RULES = load_prompt("crew", "philosophy_rules.md")
STYLE_RULES = load_prompt("crew", "style_rules.md")
ETHICS_RULES = load_prompt("crew", "ethics_rules.md")
OUTPUT_RULES = load_prompt("crew", "output_rules.md")


# ------------------ Prompt Templates ------------------

RESEARCH_PROMPT = load_prompt("crew", "research_task.md")
RESEARCH_URLS_PROMPT = load_prompt("crew", "research_urls_task.md")
PSYCH_PROMPT = load_prompt("crew", "psych_task.md")
PHILOSOPHY_PROMPT = load_prompt("crew", "philosophy_task.md")
COMPOSE_COVER_LETTER_PROMPT = load_prompt("crew", "compose_cover_letter.md")
COMPOSE_LINKEDIN_PROMPT = load_prompt("crew", "compose_linkedin.md")

# ------------------ Agents ------------------


def build_researcher() -> CrewAIAgent:
    _ensure_crewai_loaded()
    tools = list(_get_tooling().default_tools)
    return Agent(
        role="Industry & Company Researcher",
        goal="Produce concise, sourced company/role briefs a candidate can rely on.",
        backstory="Senior researcher skilled at extracting signal from public sources and employer materials.",
        tools=tools,
        allow_delegation=False,
        verbose=False,
        max_iter=8,  # cap loops that trigger “Maximum iterations…”
    )


def build_researcher_for_urls(urls: List[str]) -> CrewAIAgent:
    """Build a researcher configured with site-scoped tools for specific URLs.

    If WebsiteSearchTool is available, attach one instance per URL to enable
    targeted retrieval. Also include the generic ScrapeWebsiteTool when present
    so the agent can directly scrape arbitrary pages provided in the prompt.
    """
    _ensure_crewai_loaded()
    tooling = _get_tooling()
    tools: List[Any] = []
    if tooling.website_search_tool_cls is not None:
        tools.extend([tooling.website_search_tool_cls(website=u) for u in urls])
    if tooling.web_scrape_tool is not None:
        tools.append(tooling.web_scrape_tool)
    return Agent(
        role="You are a helpful assistant that extracts facts from provided URLs.",
        goal="Answer user questions and summarize using only the provided sources.",
        backstory="You specialize in synthesizing multi-source web content into concise briefs.",
        tools=tools,
        allow_delegation=False,
        verbose=False,
        max_iter=8,
    )


def build_psychologist() -> CrewAIAgent:
    _ensure_crewai_loaded()
    return Agent(
        role="Organizational Psychology Strategist",
        goal="Map research to likely evaluator lenses, credibility signals, and messaging risks.",
        backstory="Evidence-based org-psych practitioner with interviewing insight.",
        tools=[],
        allow_delegation=False,
        verbose=False,
        max_iter=6,
    )


def build_philosopher() -> CrewAIAgent:
    _ensure_crewai_loaded()
    return Agent(
        role="Principled Communication Architect",
        goal="Translate philosophical constraints into concrete writing rules (Do/Don't).",
        backstory="Communication specialist who operationalizes principles into wording and structure.",
        tools=[],
        allow_delegation=False,
        verbose=False,
        max_iter=4,
    )


def build_composer() -> CrewAIAgent:
    _ensure_crewai_loaded()
    return Agent(
        role="Content Strategist & Writer",
        goal="Produce polished, targeted artifacts (cover letters, outreach notes) that read human and senior.",
        backstory="Exec comms + product engineering background; writes like a hiring manager.",
        tools=[],
        allow_delegation=False,
        verbose=False,
        max_iter=6,
    )


# ------------------ Tasks ------------------


def research_task(job: JobApplicationContext) -> CrewAITask:
    _ensure_crewai_loaded()
    description = RESEARCH_PROMPT.format(
        company_name=job.company_name,
        position=job.position,
        philosophy_rules=PHILOSOPHY_RULES,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=build_researcher(),
        description=description,
        expected_output="JSON string per spec.",
    )


def research_urls_task(urls: List[str]) -> CrewAITask:
    """Task that summarizes information from a fixed set of URLs.

    Returns a compact JSON so callers can consume it deterministically.
    """
    _ensure_crewai_loaded()
    agent = build_researcher_for_urls(urls)
    url_block = "\n".join(f"- {u}" for u in urls)
    description = RESEARCH_URLS_PROMPT.format(
        sources=url_block,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=agent,
        description=description,
        expected_output="JSON with profile, roles, achievements, publications, links, evidence.",
    )


def psych_task() -> CrewAITask:
    _ensure_crewai_loaded()
    description = PSYCH_PROMPT.format(
        philosophy_rules=PHILOSOPHY_RULES,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=build_psychologist(),
        description=description,
        expected_output="JSON messaging brief.",
    )


def philosophy_task(job: JobApplicationContext) -> CrewAITask:
    _ensure_crewai_loaded()
    description = PHILOSOPHY_PROMPT.format(
        philosophical_approach=job.philosophical_approach,
        philosophy_rules=PHILOSOPHY_RULES,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=build_philosopher(),
        description=description,
        expected_output="JSON rules.",
    )


def compose_cover_letter_task(job: JobApplicationContext) -> CrewAITask:
    _ensure_crewai_loaded()
    description = COMPOSE_COVER_LETTER_PROMPT.format(
        output_rules=OUTPUT_RULES,
        philosophy_rules=PHILOSOPHY_RULES,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=build_composer(),
        description=description,
        expected_output="Final cover letter text (plain text).",
    )


def compose_linkedin_task() -> CrewAITask:
    _ensure_crewai_loaded()
    description = COMPOSE_LINKEDIN_PROMPT.format(
        output_rules=OUTPUT_RULES,
        philosophy_rules=PHILOSOPHY_RULES,
        style_rules=STYLE_RULES,
        ethics_rules=ETHICS_RULES,
    )
    return Task(
        agent=build_composer(),
        description=description,
        expected_output='JSON with "connection_note" and "follow_up".',
    )


# ------------------ Crew Runner ------------------


def _normalize_task_output(task: CrewAITask, kickoff_result) -> str:
    """
    After crew.kickoff(), prefer task.output (CrewAI exposes it).
    Fallback to properties on CrewOutput (e.g., .raw/.final_output) or str().
    """
    # Prefer the task's own output when present (recommended by CrewAI community)
    # Ref: docs/community patterns.
    out = getattr(task, "output", None)
    if out is not None:
        # Common shapes: .raw (str), .json_dict (dict), or str(out)
        if hasattr(out, "raw") and out.raw:
            return out.raw if isinstance(out.raw, str) else json.dumps(out.raw)
        if hasattr(out, "json_dict") and out.json_dict:
            return json.dumps(out.json_dict)
        try:
            return str(out)
        except Exception:
            pass

    # Fallback: try CrewOutput’s attributes
    if hasattr(kickoff_result, "raw") and kickoff_result.raw:
        return (
            kickoff_result.raw
            if isinstance(kickoff_result.raw, str)
            else json.dumps(kickoff_result.raw)
        )
    if hasattr(kickoff_result, "final_output") and kickoff_result.final_output:
        return (
            kickoff_result.final_output
            if isinstance(kickoff_result.final_output, str)
            else json.dumps(kickoff_result.final_output)
        )
    if hasattr(kickoff_result, "to_dict"):
        try:
            return json.dumps(kickoff_result.to_dict())
        except Exception:
            pass

    # Last resort
    return str(kickoff_result)


@dataclass
class PhilosophicalApplicationCrew:
    """Deterministic pipeline runner using kickoff()."""

    def _kickoff_single(self, task: CrewAITask, context_payloads: Optional[List[str]] = None) -> str:
        """Run a single task safely.

        CrewAI Task.context expects a list of Task instances whose outputs will
        be aggregated. Passing a list of strings causes CrewAI to treat them as
        tasks and fail (AttributeError: 'str' has no attribute 'output').

        To provide raw string/JSON context, we inline it into the task
        description and ensure task.context is not a list of strings.
        """
        _ensure_crewai_loaded()
        if context_payloads:
            # Inline context directly into the prompt to avoid CrewAI treating
            # raw strings as Task objects during context aggregation.
            joined = "\n\n---\n".join(str(p) for p in context_payloads)
            task.description = f"{task.description}\n\n[Context]\n{joined}"
            # Make sure we don't provide an invalid list to `task.context`.
            if hasattr(task, "context"):
                try:
                    task.context = None  # type: ignore[attr-defined]
                except Exception:
                    pass
        crew = Crew(agents=[task.agent], tasks=[task], process=Process.sequential, verbose=False)
        result = (
            crew.kickoff()
        )  # returns CrewOutput (not JSON/string) :contentReference[oaicite:3]{index=3}
        return _normalize_task_output(task, result)

    # ---- Public API ----

    def create_cover_letter(
        self, job_ctx: JobApplicationContext, candidate: CandidateProfile
    ) -> str:
        # 1) Research
        t_research = research_task(job_ctx)
        research_out = self._kickoff_single(t_research)

        # Candidate URL research (static list)
        url_profile_json: Optional[str] = None
        try:
            url_summary = self.research_urls(DEFAULT_PROFILE_URLS)
            url_profile_json = json.dumps(url_summary)
        except Exception:
            # Non-fatal; proceed without URL context
            url_profile_json = None

        # 2) Psych mapping
        t_psych = psych_task()
        psych_ctx = [research_out, candidate.json()]
        if url_profile_json:
            psych_ctx.append(url_profile_json)
        psych_out = self._kickoff_single(t_psych, psych_ctx)

        # 3) Philosophy rules
        t_phil = philosophy_task(job_ctx)
        phil_out = self._kickoff_single(t_phil)

        # 4) Compose cover letter
        t_compose = compose_cover_letter_task(job_ctx)
        compose_ctx = [research_out, psych_out, phil_out, candidate.json()]
        if url_profile_json:
            compose_ctx.append(url_profile_json)
        letter = self._kickoff_single(t_compose, compose_ctx)
        return letter.strip()

    def create_linkedin_message(
        self, li_ctx: LinkedInContext, candidate: CandidateProfile
    ) -> Dict[str, str]:
        ctx: List[str] = []
        if li_ctx.company_name:
            dummy_job = JobApplicationContext(
                company_name=li_ctx.company_name,
                position=li_ctx.connection_title,
                job_description=li_ctx.interaction_purpose,
                philosophical_approach="blended",
            )
            t_research = research_task(dummy_job)
            research_out = self._kickoff_single(t_research)
            ctx.append(research_out)

        t_phil = philosophy_task(
            JobApplicationContext(
                company_name=li_ctx.company_name,
                position=li_ctx.connection_title,
                job_description=li_ctx.interaction_purpose,
                philosophical_approach="blended",
            )
        )
        phil_out = self._kickoff_single(t_phil)
        ctx.extend([phil_out, li_ctx.json(), candidate.json()])

        t_compose = compose_linkedin_task()
        # Include candidate URL research for richer, grounded messages
        try:
            url_summary = self.research_urls(DEFAULT_PROFILE_URLS)
            ctx.append(json.dumps(url_summary))
        except Exception:
            pass

        out = self._kickoff_single(t_compose, ctx)
        # Ensure strict JSON return
        try:
            return json.loads(out)
        except Exception:
            start, end = out.find("{"), out.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(out[start : end + 1])
            raise RuntimeError("Composer did not return valid JSON.")

    def research_urls(self, urls: List[str]) -> Dict[str, Any]:
        """Summarize given URLs into a structured JSON dictionary.

        This is useful to prime downstream tasks with grounded context.
        """
        t = research_urls_task(urls)
        out = self._kickoff_single(t)
        try:
            return json.loads(out)
        except Exception:
            start, end = out.find("{"), out.rfind("}")
            if start != -1 and end != -1 and end > start:
                return json.loads(out[start : end + 1])
            raise RuntimeError("Researcher did not return valid JSON.")


# ------------------ Runtime Helpers ------------------


@lru_cache(maxsize=1)
def _get_runner() -> PhilosophicalApplicationCrew:
    """Reuse a single crew runner instance to avoid repeated model downloads."""

    return PhilosophicalApplicationCrew()


def _build_job_context(topic: str) -> JobApplicationContext:
    clean_topic = topic.strip()
    return JobApplicationContext(
        company_name=clean_topic,
        position="Research target",
        job_description=(
            f"Investigate {clean_topic}. Focus on mission, products, customer segments, "
            "recent news, and strategy signals."
        ),
        philosophical_approach="blended",
    )


async def kickoff_research_writer(topic: str) -> str:
    """Run the research crew for an arbitrary topic via asyncio-friendly wrapper."""

    if not topic or not topic.strip():
        raise ValueError("topic must be provided")

    runner = _get_runner()
    job_ctx = _build_job_context(topic)
    task = research_task(job_ctx)

    try:
        result = await asyncio.to_thread(runner._kickoff_single, task)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - surface as runtime error
        raise RuntimeError(f"Crew research failed: {exc}") from exc

    return result


# ------------------ Example CLI ------------------

if __name__ == "__main__":
    # Optionally pre-fetch candidate URL profile for local runs
    try:
        _crew = PhilosophicalApplicationCrew()
        _url_profile = _crew.research_urls(DEFAULT_PROFILE_URLS)
        print("\n=== CANDIDATE URL PROFILE (summary) ===\n")
        print(
            json.dumps(_url_profile, indent=2)[:1200]
            + ("..." if len(json.dumps(_url_profile)) > 1200 else "")
        )
    except Exception:
        pass

    candidate = CandidateProfile(
        name="Ashwin Rachha",
        headline="Tech Lead & AI Product Engineer",
        skills=[
            "Python",
            "Go",
            "PyTorch",
            "LangChain",
            "LangGraph",
            "Kubernetes",
            "AWS",
            "Django",
            "React",
            "PostgreSQL",
            "Celery",
            "Redis",
        ],
        experience=[
            {
                "company": "Finally",
                "role": "Tech Lead, AI Product Engineer",
                "highlights": [
                    "Built and led Classify AI (few-shot + retrieval) with Redis semantic caching",
                    "Architected bank aggregator infra (Plaid, Teller): OAuth, webhooks, syncing",
                    "Implemented cash-based underwriting system for corporate cards",
                ],
                "metrics": [
                    "50k+ transactions/day processed",
                    "80% reduction in manual categorization time",
                    "$3M+ credit underwritten in first 3 months",
                ],
            }
        ],
        publications=[
            "IEEE FIE 2024 — LLM-enhanced learning environments (RAG, guardrails)",
            "IEEE SouthEastCon 2023 — Explainable AI in Education",
        ],
        achievements=["Kaggle Expert (Top 1% in Notebooks)"],
    )

    job = JobApplicationContext(
        company_name="Innovative Tech Corp",
        position="Senior AI Product Engineer",
        job_description="Own production LLM systems with retrieval; optimize cost/latency; partner with product.",
    )

    crew = PhilosophicalApplicationCrew()

    print("\n=== COVER LETTER ===\n")
    print(crew.create_cover_letter(job, candidate))

    print("\n=== LINKEDIN MESSAGES ===\n")
    li_ctx = LinkedInContext(
        connection_name="Jane Doe",
        connection_title="Director of AI",
        company_name="Innovative Tech Corp",
        shared_interests=["AI Reliability", "Product-Led ML"],
        interaction_purpose="Connect and compare approaches to reliable production LLM systems.",
        philosophical_tone="authentic_engagement",
    )
    print(json.dumps(crew.create_linkedin_message(li_ctx, candidate), indent=2))
