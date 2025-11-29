"""LangGraph wiring for the deep research workflow."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from alfred.services.research.nodes import (
    draft_refiner,
    draft_writer,
    evidence_synthesizer,
    internal_knowledge_collector,
    outline_planner,
    query_expander,
    web_search_collector,
)
from alfred.services.research.persistence import persist_research_run
from alfred.services.research.state import ResearchState


def build_research_graph() -> StateGraph:
    graph = StateGraph(ResearchState)

    graph.add_node("query_expander", query_expander)
    graph.add_node("web_search_collector", web_search_collector)
    graph.add_node("internal_knowledge_collector", internal_knowledge_collector)
    graph.add_node("evidence_synthesizer", evidence_synthesizer)
    graph.add_node("outline_planner", outline_planner)
    graph.add_node("draft_writer", draft_writer)
    graph.add_node("draft_refiner", draft_refiner)

    graph.set_entry_point("query_expander")
    graph.add_edge("query_expander", "web_search_collector")
    graph.add_edge("web_search_collector", "internal_knowledge_collector")
    graph.add_edge("internal_knowledge_collector", "evidence_synthesizer")
    graph.add_edge("evidence_synthesizer", "outline_planner")
    graph.add_edge("outline_planner", "draft_writer")
    graph.add_edge("draft_writer", "draft_refiner")
    graph.add_edge("draft_refiner", END)

    return graph


_research_graph = build_research_graph().compile()


async def run_research(
    *,
    query: str,
    target_length_words: int = 1000,
    tone: str = "neutral",
) -> tuple[str, ResearchState]:
    initial_state: ResearchState = {
        "query": query,
        "target_length_words": target_length_words,
        "tone": tone,  # type: ignore[assignment]
    }
    result = await _research_graph.ainvoke(initial_state)
    article = result.get("final_article", "")
    if article:
        persist_research_run(
            query=query,
            target_length_words=target_length_words,
            tone=tone,
            article=article,
            state=result,
        )
    return article, result
