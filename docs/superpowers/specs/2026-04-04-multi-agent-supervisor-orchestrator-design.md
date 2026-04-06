# Alfred Multi-Agent Supervisor-Orchestrator Architecture

**Date:** 2026-04-04
**Status:** Draft
**Branch:** `performance`

## Overview

Replace Alfred's single-threaded, 4-tool agent with a two-tier hierarchical multi-agent system built on LangGraph. Every Alfred feature becomes accessible via tool calling. Connectors pipe data directly into agents as real-time queryable tools. The AI panel feeds conversations back into the knowledge graph as a first-class connector.

## Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | LangGraph (Command + Send API) | Hybrid routing, parallel fan-out, checkpointing, streaming |
| Architecture | Two-tier hierarchical supervisor | Focused prompts per team, model tiering, parallel team dispatch |
| Agent granularity | 8 fine-grained specialists | 1:1 mapping to existing services, independently testable |
| LLM routing | Hybrid heuristic + LLM fallback | Zero-cost for obvious intents, LLM only for ambiguous |
| Model tiering | Heavy (GPT-5.4) / Light (mini) / Local (Ollama) | Cost optimization per agent complexity |
| Streaming UX | Sequential reveal with parallel execution | Perplexity-style progress, simple frontend changes |
| AI panel feedback | Conversation-as-document + explicit save | Closed-loop knowledge ingestion |
| Execution modes | Real-time conversational + autonomous background | Same graph, different invocation patterns |

## 1. State Schema

### Top-Level State

```python
from typing import Annotated
from langgraph.graph import add_messages
from langchain_core.messages import AnyMessage
import operator

class AlfredState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    user_id: str
    intent: str | None
    active_agents: list[str]
    phase: str  # "routing" | "executing" | "synthesizing" | "done"

    # Reducer-merged results from sub-agents
    knowledge_results: Annotated[list[dict], operator.add]
    research_results: Annotated[list[dict], operator.add]
    connector_results: Annotated[list[dict], operator.add]
    enrichment_results: Annotated[list[dict], operator.add]

    # Output
    final_response: str | None
    artifacts: list[dict]  # created/modified zettels, documents, links
```

### Team-Level States

```python
class IngestTeamState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    connector_name: str | None
    import_params: dict | None
    connector_results: Annotated[list[dict], operator.add]
    enrichment_results: Annotated[list[dict], operator.add]

class KnowledgeTeamState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    knowledge_results: Annotated[list[dict], operator.add]
    link_suggestions: list[dict]
    review_queue: list[dict]

class SynthesisTeamState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    research_results: Annotated[list[dict], operator.add]
    final_response: str | None
    artifacts: list[dict]
```

## 2. Graph Topology

```
START
  |
  v
+---------------------------------------------+
|  router  (heuristic + LLM fallback)         |
|  Returns: Command(goto=team) or              |
|           Send([team_a, team_b]) for multi   |
+--+----------+----------+--------------------+
   |          |          |
   v          v          v
+--------+ +----------+ +-----------+
| ingest | |knowledge | | synthesis |  <-- nested create_supervisor()
| _team  | | _team    | | _team     |
+---+----+ +----+-----+ +-----+-----+
    |           |             |
    +-----------+-------------+
                |
                v
         +-----------+
         | synthesizer|  <-- merges team results into final_response
         +-----+-----+
                |
                v
         +-----------+
         | feedback   |  <-- auto-save conversation as document
         +-----+-----+
                |
                v
               END
```

## 3. Router Node

Hybrid heuristic + LLM classification. Heuristics handle ~60-70% of requests at zero LLM cost.

### Intent Routing Table

| Intent | Heuristic Pattern | Routes To | Parallel? |
|--------|-------------------|-----------|-----------|
| `import` | "import", "sync", "pull from" + connector name | Ingest Team | No |
| `search_kb` | "what do I know", "find", "search" | Knowledge Team | No |
| `connect` | "connections between", "link", "relate" | Knowledge Team | No |
| `research` | "research", "look up", "ArXiv", "find papers" | Synthesis Team | No |
| `write` | "write", "draft", "summarize", "explain" | Synthesis Team | No |
| `learn` | "review", "quiz", "spaced rep", "due cards" | Knowledge Team | No |
| `enrich` | "summarize this", "extract concepts", "classify" | Ingest Team | No |
| `complex` | No single match / multiple intents | Send([teams...]) | Yes |

### Router Logic

```python
def router(state: AlfredState) -> Command | list[Send]:
    user_msg = state["messages"][-1].content.lower()

    # 1. Heuristic fast-paths (zero LLM cost)
    if match := heuristic_classify(user_msg):
        return Command(
            update={"intent": match.intent, "phase": "executing"},
            goto=match.team
        )

    # 2. LLM fallback for ambiguous queries (GPT-5.4-mini)
    classification = classify_intent_llm(user_msg)

    # 3. Single team -> Command, multiple teams -> Send (parallel)
    if len(classification.teams) == 1:
        return Command(
            update={"intent": classification.intents[0], "phase": "executing"},
            goto=classification.teams[0]
        )
    else:
        return [
            Send(team, {"messages": state["messages"], "phase": "executing"})
            for team in classification.teams
        ]
```

## 4. The 8 Specialist Agents

### Ingest Team (Model: GPT-5.4-mini)

**Connector Agent** -- Live-queries any of 19 connectors on demand.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `query_notion(query, page_limit)` | `NotionHistoryConnector.fetch_items()` | Search Notion pages |
| `query_readwise(since, category)` | `ReadwiseConnector.export_highlights()` | Get recent highlights |
| `query_arxiv(query, max_results)` | `ArxivConnector.fetch_items()` | Search papers |
| `query_rss(feed_url, since)` | `RSSConnector.fetch_items()` | Pull feed entries |
| `query_web(query, engine)` | `WebConnector.fetch_items()` | Web search via SearX/Firecrawl |
| `query_wikipedia(topic)` | `WikipediaConnector.fetch_items()` | Wikipedia lookup |
| `query_github(repo, type)` | `GitHubConnector.fetch_items()` | Issues, PRs, code |
| `query_linear(project, status)` | `LinearConnector.fetch_items()` | Linear issues |
| `query_semantic_scholar(query)` | `SemanticScholarConnector.fetch_items()` | Academic papers |

**Import Agent** -- Triggers batch imports, monitors progress.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `run_import(connector_name, since)` | `BaseImportService.run_import()` | Trigger full import |
| `import_status(task_id)` | Celery `AsyncResult` | Check import progress |
| `list_connectors()` | Settings + connector registry | Show available/connected sources |

**Enrichment Agent** -- AI-powered document processing. Model: Ollama local / GPT-5.4-mini.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `summarize(doc_id, style)` | `LLMService.summarize()` | Generate summary |
| `extract_concepts(doc_id)` | `LLMService.extract_concepts()` | Pull domain concepts |
| `classify(doc_id, taxonomy)` | `LLMService.classify_document()` | Multi-level classification |
| `decompose_to_zettels(doc_id)` | `zettel_decomposer` task | Break doc into atomic cards |
| `generate_embeddings(doc_ids)` | `get_embedding_model()` | Batch embed documents |

### Knowledge Team (Model: GPT-5.4-mini)

**Knowledge Agent** -- Zettel CRUD and semantic search.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `search_kb(query, topic, tags, limit)` | `ZettelkastenService.list_cards()` | Semantic zettel search |
| `get_zettel(id)` | `ZettelkastenService.get_card()` | Retrieve full card |
| `create_zettel(title, content, tags, topic)` | `ZettelkastenService.create_card()` | Create atomic card |
| `update_zettel(id, **fields)` | `ZettelkastenService.update_card()` | Modify card |
| `get_document(doc_id)` | `DocStorageService.get_document_details()` | Retrieve source document |
| `search_documents(query, content_type)` | `DocStorageService` retrieval mixin | Search documents |

**Connection Agent** -- Link discovery and graph traversal.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `find_similar(card_id, threshold)` | `ZettelkastenService.find_similar_cards()` | Cosine similarity |
| `suggest_links(card_id, min_confidence)` | `ZettelkastenService.suggest_links()` | AI link suggestions |
| `create_link(from_id, to_id, type, context)` | `ZettelkastenService.create_link()` | Create relationship |
| `get_card_links(card_id)` | `ZettelkastenService` link queries | Traverse graph |
| `batch_link(limit, auto_link)` | `batch_link_task` | Batch link generation |

**Learning Agent** -- Spaced repetition and knowledge assessment.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `get_due_reviews(limit)` | `ZettelkastenService.list_reviews()` | Cards due for review |
| `submit_review(card_id, score)` | `ZettelkastenService` review methods | Record review result |
| `assess_knowledge(topic)` | New: Bloom's taxonomy assessment | Knowledge level check |
| `generate_quiz(topic, count)` | New: Active recall quiz generation | Quiz creation |
| `feynman_check(card_id)` | New: "Explain like I'm 5" gap detection | Gap detection |

### Synthesis Team (Model: GPT-5.4 / GPT-5.4-pro)

**Research Agent** -- Deep research and multi-source synthesis.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `deep_research(topic, sources)` | `deep_research` Celery task | Extended research synthesis |
| `search_web(query)` | `WebConnector` + `FirecrawlConnector` | Real-time web search |
| `search_papers(query, source)` | ArXiv + Semantic Scholar connectors | Academic search |
| `search_kb(query)` | `ZettelkastenService.list_cards()` | Cross-reference existing knowledge |
| `scrape_url(url)` | `FirecrawlConnector.scrape()` | Full page extraction |

**Writing Agent** -- Drafts, synthesizes, explains.

| Tool | Wraps | Purpose |
|------|-------|---------|
| `draft_zettel(topic, sources, style)` | LLM + zettel creation | Synthesize sources into atomic card |
| `progressive_summary(doc_ids)` | LLM + doc retrieval | Layer-by-layer summarization |
| `feynman_explain(topic, level)` | LLM | Teach-to-reveal-gaps explanation |
| `compare_perspectives(card_ids)` | LLM + zettel retrieval | Cross-card analysis |
| `create_zettel(title, content, tags)` | `ZettelkastenService.create_card()` | Save output as card |

### Tool Count Summary

| Team | Agent | Tools | Model |
|------|-------|-------|-------|
| Ingest | Connector | 9 | mini |
| Ingest | Import | 3 | mini |
| Ingest | Enrichment | 5 | local/mini |
| Knowledge | Knowledge | 6 | mini |
| Knowledge | Connection | 5 | mini |
| Knowledge | Learning | 5 | mini |
| Synthesis | Research | 5 | GPT-5.4 |
| Synthesis | Writing | 5 | GPT-5.4 |
| **Total** | **8 agents** | **43 tools** | -- |

## 5. AI Panel as Connector (Feedback Loop)

### Explicit Path (Foreground)
User clicks "Save as zettel" on any AI response. The `create_zettel()` tool fires immediately. Already exists.

### Implicit Path (Background)
After each AI thread completes, the feedback node:

1. Saves conversation as a `Document` via `AIPanelImportService(BaseImportService)`
   - `content_type = "ai_conversation"`
   - `metadata = {"lens": "socratic", "thread_id": 123, "model": "gpt-5.4"}`
   - Content = full conversation formatted as Markdown
   - Dedup via `hash = f"ai_thread:{thread_id}:{turn_count}"`

2. Enters normal enrichment pipeline (summarization, concept extraction, zettel decomposition)

3. Conversation embeddings indexed -- searchable via "What have I discussed about X?"

### SSE Event
```json
{"event": "feedback", "data": {"action": "conversation_saved", "doc_id": "uuid"}}
```

## 6. Streaming UX

Sequential reveal with parallel execution (Perplexity-style).

### SSE Event Types

| Event | Data | When |
|-------|------|------|
| `phase` | `{"phase": "routing", "message": "Understanding your request..."}` | Router starts |
| `phase` | `{"phase": "executing", "agents": ["research", "knowledge"]}` | Teams dispatched |
| `agent_status` | `{"agent": "research", "status": "searching ArXiv..."}` | Agent progress |
| `agent_status` | `{"agent": "knowledge", "status": "found 5 related cards"}` | Agent progress |
| `token` | `{"content": "Based on..."}` | Synthesizer streaming |
| `artifact` | `{"type": "zettel_created", "id": 173, "title": "..."}` | Side effects |
| `feedback` | `{"action": "conversation_saved", "doc_id": "uuid"}` | Background save |
| `done` | `{}` | Complete |

## 7. Background Daemon (Autonomous Path)

Same LangGraph graph invoked programmatically via Celery, no supervisor LLM.

### Daemon Modes

| Mode | Trigger | Agents Used |
|------|---------|-------------|
| Ingest Watch | Celery beat (every 30 min) | Connector + Import + Enrichment |
| Link Discovery | After new zettels created | Connection agent |
| Proactive Insights | Nightly | Research + Knowledge + Writing |
| Connector Sync | On-demand or scheduled | Connector + Import |

### Example: Ingest Watch

```python
@shared_task
def daemon_ingest_watch():
    graph = build_alfred_graph()
    graph.invoke({
        "messages": [HumanMessage(content="Check all connected sources for new content since last sync")],
        "intent": "import",
        "phase": "executing",
    })
```

## 8. Performance Optimizations

| Optimization | Where | Benefit |
|-------------|-------|---------|
| LLM response cache | Redis, keyed by (prompt_hash, model) | Avoid re-calling LLM for identical queries |
| Connector result cache | Redis, TTL per connector (Notion: 5min, ArXiv: 1hr) | Don't re-fetch recently queried sources |
| Embedding cache | Postgres (existing `ZettelCard.embedding`) | Already cached per card |
| Heuristic router | In-memory regex patterns | Zero-cost routing for 60-70% of intents |
| Parallel tool calls | LangGraph `Send` + `parallel_tool_calls=True` | Multiple agents/tools execute simultaneously |
| Tiered models | `llm_factory.py` config per agent | Mini for dispatch, frontier for synthesis |
| LangGraph checkpointing | PostgreSQL checkpointer (existing Neon DB) | Resume conversations, avoid reprocessing |

## 9. File Structure

```
apps/alfred/agents/
  __init__.py
  state.py                    # AlfredState, team states
  router.py                   # Hybrid heuristic + LLM router
  graph.py                    # Top-level StateGraph wiring
  tools/
    __init__.py
    connector_tools.py        # 9 connector query tools
    import_tools.py           # 3 import tools
    enrichment_tools.py       # 5 enrichment tools
    knowledge_tools.py        # 6 zettel CRUD + search tools
    connection_tools.py       # 5 link discovery tools
    learning_tools.py         # 5 spaced rep + assessment tools
    research_tools.py         # 5 deep research tools
    writing_tools.py          # 5 synthesis + draft tools
  teams/
    __init__.py
    ingest_team.py            # create_supervisor([connector, import, enrichment])
    knowledge_team.py         # create_supervisor([knowledge, connection, learning])
    synthesis_team.py         # create_supervisor([research, writing])
  feedback.py                 # AI panel -> document connector
  daemon.py                   # Celery periodic tasks for autonomous mode
```

### Migration from Current Agent

| Current | New | Change |
|---------|-----|--------|
| `services/agent/service.py` (hand-rolled tool loop) | `agents/graph.py` (LangGraph StateGraph) | Replace |
| `services/agent/tools.py` (4 tools) | `agents/tools/*.py` (43 tools) | Expand |
| `api/agent/routes.py` (SSE endpoint) | Same, but calls `graph.astream_events()` | Modify |
| N/A | `agents/teams/*.py` | New |
| N/A | `agents/router.py` | New |
| N/A | `agents/feedback.py` | New |
| N/A | `agents/daemon.py` | New |

## 10. LangGraph CLI Integration

The project already has `langgraph.json` with 4 registered graphs (`agentic_rag`, `company_outreach`, `writer`, `interviews_unified`). The new supervisor graph will be registered as `alfred_supervisor`:

```json
{
  "dependencies": ["./"],
  "graphs": {
    "agentic_rag": "./apps/alfred/agents/agentic_rag/agent.py:agent",
    "writer": "./apps/alfred/agents/writer/agent.py:agent",
    "alfred_supervisor": "./apps/alfred/agents/graph.py:alfred_graph"
  }
}
```

The legacy `company_outreach` and `interviews_unified` graphs can be removed (job search features were cut). The `agentic_rag` and `writer` agents may be subsumed by the new Research and Writing agents respectively.

## 11. Dependencies

### New Packages

```
langgraph>=1.0.0
langgraph-supervisor>=0.1.0
langchain-openai>=0.3.0
langchain-core>=0.3.0
```

### Existing (Already Used)

- `langchain` (used in `llm_factory.py` via `ChatOpenAI`, `ChatOllama`)
- `celery` (task queue)
- `redis` (caching + Celery broker)
- PostgreSQL (checkpointing + data)

## 12. Testing Strategy

| Layer | Test Type | What |
|-------|-----------|------|
| Tools | Unit tests | Each tool function with mocked services |
| Router | Unit tests | Heuristic patterns + LLM classification |
| Teams | Integration tests | Each team supervisor with mock LLM |
| Graph | Integration tests | End-to-end with mock LLM + real DB |
| SSE | API tests | Stream event format and ordering |
| Daemon | Task tests | Celery task invocation with mock graph |

## 13. Out of Scope (Future)

- Human-in-the-loop interrupts (LangGraph supports this, defer to v2)
- Multi-user agent isolation (currently single-user)
- LangGraph Cloud deployment (local-first for now)
- Agent memory across sessions (use checkpointing first)
- Canvas/whiteboard agent integration
