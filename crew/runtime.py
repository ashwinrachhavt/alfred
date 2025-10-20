from __future__ import annotations

import asyncio
from functools import lru_cache

from alfred.services.crew import (
    JobApplicationContext,
    PhilosophicalApplicationCrew,
    research_task,
)


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
    """
    Run the research crew for an arbitrary topic and return the raw JSON summary.

    The underlying CrewAI pipeline is synchronous, so we offload it to a worker
    thread to keep FastAPI's event loop responsive.
    """
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


__all__ = ["kickoff_research_writer"]
