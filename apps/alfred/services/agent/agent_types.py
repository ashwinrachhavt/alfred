"""Agent type definitions for multi-context-window orchestration.

Each agent type defines:
- A focused system prompt (what this specialist does)
- A list of tool names it has access to (subset of the full registry)
- A description for the parent agent to know when to delegate

Modeled after Claude Code's sub-agent pattern where the parent LLM
decides when to spawn a specialist, and each specialist has its own
isolated context window with focused tools.

┌─────────────────────────────────────────────────────────┐
│  Parent Agent (full tool set, main conversation)        │
│                                                          │
│  → "delegate_task" tool call                             │
│    → spawns SubAgent with:                               │
│      - own context window (isolated messages)            │
│      - focused tool subset                               │
│      - specialist system prompt                          │
│      - runs to completion                                │
│    ← returns summary string                              │
│                                                          │
│  Parent continues with sub-agent result                  │
└─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentType:
    """Definition of a specialist sub-agent."""

    name: str
    description: str
    system_prompt: str
    tool_names: list[str]
    max_iterations: int = 5


# ---------------------------------------------------------------------------
# Specialist agent types
# ---------------------------------------------------------------------------

KNOWLEDGE_AGENT = AgentType(
    name="knowledge",
    description=(
        "Search, retrieve, create, and update knowledge cards (zettels). "
        "Use when the user asks about what they know, wants to save or edit cards, "
        "or needs to browse their knowledge base."
    ),
    system_prompt=(
        "You are a knowledge specialist. Your job is to search, retrieve, create, "
        "and manage the user's zettelkasten (atomic knowledge cards). "
        "Be thorough in searches. When creating cards, use clear titles and relevant tags. "
        "When you find relevant cards, summarize the key insights."
    ),
    tool_names=[
        "search_kb",
        "get_zettel",
        "create_zettel",
        "update_zettel",
        "list_recent_cards",
        "search_documents",
        "get_document",
    ],
)

RESEARCH_AGENT = AgentType(
    name="research",
    description=(
        "Search the web, academic papers, and external sources for information. "
        "Use when the user asks about current events, needs facts, wants papers, "
        "or needs to scrape/read web pages."
    ),
    system_prompt=(
        "You are a research specialist. Your job is to find information from the web, "
        "academic papers, and external sources. Be thorough. Cite your sources. "
        "Provide URLs. Summarize findings concisely with the most relevant details first."
    ),
    tool_names=[
        "web_search_searxng",
        "firecrawl_search",
        "firecrawl_scrape",
        "search_papers",
        "search_kb_for_research",
        "query_arxiv",
        "query_semantic_scholar",
        "query_wikipedia",
        "query_web",
    ],
)

WRITING_AGENT = AgentType(
    name="writing",
    description=(
        "Draft, synthesize, summarize, and explain knowledge. "
        "Use when the user wants to create new content, compare perspectives, "
        "get explanations, or synthesize information from multiple sources."
    ),
    system_prompt=(
        "You are a writing and synthesis specialist. Your job is to draft zettel cards, "
        "create summaries, explain concepts, and synthesize information from multiple sources. "
        "Write clearly and concisely. Use markdown formatting. "
        "When synthesizing, explicitly note connections and contradictions between sources."
    ),
    tool_names=[
        "draft_zettel",
        "progressive_summary",
        "feynman_explain",
        "compare_perspectives",
        "create_zettel_from_synthesis",
        "search_kb",
        "get_zettel",
    ],
)

LEARNING_AGENT = AgentType(
    name="learning",
    description=(
        "Run quizzes, spaced repetition reviews, knowledge assessments, and Feynman checks. "
        "Use when the user wants to test their knowledge, review cards, "
        "or assess their understanding of a topic."
    ),
    system_prompt=(
        "You are a learning specialist. Your job is to help the user test and strengthen "
        "their knowledge through quizzes, spaced repetition reviews, and assessments. "
        "Use Bloom's taxonomy for depth. Be encouraging but honest about gaps. "
        "When assessing, explain what level they're at and what to study next."
    ),
    tool_names=[
        "get_due_reviews",
        "submit_review",
        "assess_knowledge",
        "generate_quiz",
        "feynman_check",
        "search_kb",
        "get_zettel",
    ],
)

CONNECTION_AGENT = AgentType(
    name="connection",
    description=(
        "Find relationships, similarities, and links between knowledge cards. "
        "Use when the user asks about connections between ideas, wants to find "
        "similar cards, or needs to discover relationships in their knowledge graph."
    ),
    system_prompt=(
        "You are a connection specialist. Your job is to find relationships between "
        "ideas in the user's knowledge base. Look for semantic similarity, "
        "thematic connections, contradictions, and synthesis opportunities. "
        "Explain WHY things are connected, not just that they are."
    ),
    tool_names=[
        "find_similar",
        "suggest_links",
        "create_link",
        "get_card_links",
        "batch_link",
        "search_kb",
        "get_zettel",
    ],
)

CONNECTOR_AGENT = AgentType(
    name="connector",
    description=(
        "Query and import data from external services: Notion, Readwise, GitHub, "
        "Linear, RSS feeds, ArXiv. Use when the user asks about their connected "
        "services or wants to import data."
    ),
    system_prompt=(
        "You are an integration specialist. Your job is to query external services "
        "and import data into Alfred's knowledge base. Report what you found clearly. "
        "If an import fails, explain why and suggest alternatives."
    ),
    tool_names=[
        "query_notion",
        "query_readwise",
        "query_github",
        "query_linear",
        "query_rss",
        "list_connectors",
        "run_import",
        "import_status",
    ],
)

# Registry: agent_type_name → AgentType
AGENT_TYPES: dict[str, AgentType] = {
    agent.name: agent
    for agent in [
        KNOWLEDGE_AGENT,
        RESEARCH_AGENT,
        WRITING_AGENT,
        LEARNING_AGENT,
        CONNECTION_AGENT,
        CONNECTOR_AGENT,
    ]
}
