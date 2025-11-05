"""Node implementations for the research LangGraph."""

from __future__ import annotations

import asyncio
import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from alfred.prompts import load_prompt
from alfred.services.research.llm import get_llm
from alfred.services.research.state import ResearchSource, ResearchState
from alfred.services.web_search import search_web

logger = logging.getLogger(__name__)

QUERY_PLANNER_PROMPT = load_prompt("research", "query_planner.md")
EVIDENCE_SYNTH_PROMPT = load_prompt("research", "evidence_synthesizer.md")
OUTLINE_PLANNER_PROMPT = load_prompt("research", "outline_planner.md")
DRAFT_WRITER_PROMPT = load_prompt("research", "draft_writer.md")
DRAFT_REFINER_PROMPT = load_prompt("research", "draft_refiner.md")


def _safe_json_loads(payload: str) -> dict[str, object]:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON payload: %s", payload)
        raise ValueError("Model returned invalid JSON payload") from exc


async def query_expander(state: ResearchState) -> ResearchState:
    llm = get_llm(temperature=0.2)
    system = SystemMessage(
        content=QUERY_PLANNER_PROMPT
    )
    human = HumanMessage(
        content=json.dumps({"query": state["query"], "desired_sections": 5})
    )
    response = await llm.ainvoke([system, human])
    data = _safe_json_loads(response.content)
    state["expanded_queries"] = [str(item) for item in data.get("expanded_queries", [])][:7]
    state["subtopics"] = [str(item) for item in data.get("subtopics", [])][:7]
    return state


async def web_search_collector(state: ResearchState) -> ResearchState:
    expanded = state.get("expanded_queries", [])
    if not expanded:
        return state

    sources: list[ResearchSource] = state.get("sources", [])

    async def gather_one(query: str) -> list[ResearchSource]:
        result = await asyncio.to_thread(search_web, query, mode="multi")
        hits = result.get("hits", [])[:5]
        return [
            {
                "title": str(hit.get("title", "")),
                "url": str(hit.get("url", "")),
                "snippet": str(hit.get("snippet", "")),
                "content": str(hit.get("snippet", "")),
                "source_type": "web",
            }
            for hit in hits
        ]

    tasks = [gather_one(q) for q in expanded]
    for chunk in await asyncio.gather(*tasks):
        sources.extend(chunk)

    state["sources"] = sources
    return state


async def internal_knowledge_collector(state: ResearchState) -> ResearchState:
    # Placeholder for future internal knowledge integration.
    return state


async def evidence_synthesizer(state: ResearchState) -> ResearchState:
    llm = get_llm(temperature=0.0)
    sources = state.get("sources", [])[:30]
    condensed_sources = [
        {
            "title": src.get("title", ""),
            "snippet": src.get("snippet", ""),
            "url": src.get("url", ""),
            "source_type": src.get("source_type", "web"),
        }
        for src in sources
    ]
    system = SystemMessage(content=EVIDENCE_SYNTH_PROMPT)
    human = HumanMessage(
        content=json.dumps(
            {
                "subtopics": state.get("subtopics", []),
                "sources": condensed_sources,
            }
        )
    )
    response = await llm.ainvoke([system, human])
    state["evidence_notes"] = response.content
    return state


async def outline_planner(state: ResearchState) -> ResearchState:
    llm = get_llm(temperature=0.2)
    system = SystemMessage(content=OUTLINE_PLANNER_PROMPT)
    human = HumanMessage(
        content=json.dumps(
            {
                "query": state["query"],
                "subtopics": state.get("subtopics", []),
                "target_length": state.get("target_length_words", 1000),
                "tone": state.get("tone", "neutral"),
                "evidence_notes": state.get("evidence_notes", ""),
            }
        )
    )
    response = await llm.ainvoke([system, human])
    data = _safe_json_loads(response.content)
    state["outline"] = str(data.get("outline", ""))
    state["revision_instructions"] = str(data.get("instructions", ""))
    return state


async def draft_writer(state: ResearchState) -> ResearchState:
    llm = get_llm(temperature=0.4)
    system = SystemMessage(content=DRAFT_WRITER_PROMPT)
    human = HumanMessage(
        content=json.dumps(
            {
                "outline": state.get("outline", ""),
                "evidence_notes": state.get("evidence_notes", ""),
                "target_length": state.get("target_length_words", 1000),
                "tone": state.get("tone", "neutral"),
            }
        )
    )
    response = await llm.ainvoke([system, human])
    state["draft"] = response.content
    return state


async def draft_refiner(state: ResearchState) -> ResearchState:
    llm = get_llm(temperature=0.1)
    system = SystemMessage(content=DRAFT_REFINER_PROMPT)
    human = HumanMessage(
        content=json.dumps(
            {
                "draft": state.get("draft", ""),
                "revision_instructions": state.get("revision_instructions", ""),
                "target_length": state.get("target_length_words", 1000),
                "tone": state.get("tone", "neutral"),
            }
        )
    )
    response = await llm.ainvoke([system, human])
    state["final_article"] = response.content
    return state
