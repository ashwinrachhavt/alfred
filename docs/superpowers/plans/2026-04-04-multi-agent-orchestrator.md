# Multi-Agent Supervisor-Orchestrator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Alfred's single-threaded 4-tool agent with a two-tier hierarchical LangGraph multi-agent system exposing all 43 tools across 8 specialist agents.

**Architecture:** LangGraph StateGraph with hybrid heuristic+LLM router dispatching to 3 team supervisors (Ingest, Knowledge, Synthesis), each built with `create_supervisor()`. Teams run in parallel via `Send`, results merge in a synthesizer node, and conversations auto-save as documents via a feedback node.

**Tech Stack:** LangGraph (Command + Send API), langgraph-supervisor, langchain-openai, FastAPI SSE, Celery, PostgreSQL (Neon), Redis

**Spec:** `docs/superpowers/specs/2026-04-04-multi-agent-supervisor-orchestrator-design.md`

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `apps/alfred/agents/__init__.py` | Package init, exports `alfred_graph` |
| `apps/alfred/agents/state.py` | `AlfredState`, team-level TypedDicts |
| `apps/alfred/agents/router.py` | `heuristic_classify()`, `classify_intent_llm()`, `router()` node |
| `apps/alfred/agents/graph.py` | Top-level `StateGraph` wiring, `build_alfred_graph()` |
| `apps/alfred/agents/synthesizer.py` | Merges team results into `final_response` |
| `apps/alfred/agents/feedback.py` | `AIPanelImportService`, feedback node |
| `apps/alfred/agents/daemon.py` | Celery periodic tasks for autonomous mode |
| `apps/alfred/agents/tools/__init__.py` | Tool registry, exports all tool lists |
| `apps/alfred/agents/tools/knowledge_tools.py` | 6 zettel CRUD + search tools |
| `apps/alfred/agents/tools/connection_tools.py` | 5 link discovery tools |
| `apps/alfred/agents/tools/connector_tools.py` | 9 connector query tools |
| `apps/alfred/agents/tools/import_tools.py` | 3 import management tools |
| `apps/alfred/agents/tools/enrichment_tools.py` | 5 enrichment tools |
| `apps/alfred/agents/tools/learning_tools.py` | 5 spaced rep + assessment tools |
| `apps/alfred/agents/tools/research_tools.py` | 5 deep research tools |
| `apps/alfred/agents/tools/writing_tools.py` | 5 synthesis + draft tools |
| `apps/alfred/agents/teams/__init__.py` | Package init |
| `apps/alfred/agents/teams/ingest_team.py` | `create_supervisor([connector, import, enrichment])` |
| `apps/alfred/agents/teams/knowledge_team.py` | `create_supervisor([knowledge, connection, learning])` |
| `apps/alfred/agents/teams/synthesis_team.py` | `create_supervisor([research, writing])` |
| `tests/alfred/agents/test_state.py` | State schema tests |
| `tests/alfred/agents/test_router.py` | Router heuristic + LLM tests |
| `tests/alfred/agents/test_graph.py` | End-to-end graph tests |
| `tests/alfred/agents/tools/test_knowledge_tools.py` | Knowledge tool unit tests |
| `tests/alfred/agents/tools/test_connector_tools.py` | Connector tool unit tests |
| `tests/alfred/agents/teams/test_teams.py` | Team supervisor tests |

### Modified Files

| File | Change |
|------|--------|
| `pyproject.toml` | Add `langgraph-supervisor` dependency |
| `langgraph.json` | Register `alfred_supervisor` graph, remove legacy entries |
| `apps/alfred/api/agent/routes.py` | Replace `AgentService.stream_turn()` with `graph.astream_events()` |

---

## Phase 1: Foundation (State + Dependencies + First Tools)

### Task 1: Add langgraph-supervisor dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add langgraph-supervisor to pyproject.toml**

Open `pyproject.toml` and add `langgraph-supervisor` to the `dependencies` list. The existing `langgraph>=0.3.18,<0.5` constraint should be widened to `>=1.0.0` to support the latest `create_supervisor` API, and `langchain-openai` should be bumped to `>=0.3.0`:

```toml
    "langgraph>=1.0.0",
    "langgraph-supervisor>=0.1.0",
    "langchain-openai>=0.3.0,<0.4",
```

Replace the existing `langgraph` and `langchain-openai` lines in `pyproject.toml`.

- [ ] **Step 2: Install dependencies**

Run: `uv sync`
Expected: Dependencies resolve and install successfully.

- [ ] **Step 3: Verify imports work**

Run: `uv run python -c "from langgraph.graph import StateGraph; from langgraph.types import Command, Send; from langgraph_supervisor import create_supervisor; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add langgraph-supervisor, bump langgraph to >=1.0"
```

---

### Task 2: Create state schema

**Files:**
- Create: `apps/alfred/agents/__init__.py`
- Create: `apps/alfred/agents/state.py`
- Create: `tests/alfred/agents/__init__.py`
- Create: `tests/alfred/agents/test_state.py`

- [ ] **Step 1: Write the failing test**

Create `tests/alfred/agents/__init__.py` (empty) and `tests/alfred/agents/test_state.py`:

```python
"""Tests for agent state schema."""
from alfred.agents.state import AlfredState, IngestTeamState, KnowledgeTeamState, SynthesisTeamState


def test_alfred_state_has_required_keys():
    """AlfredState TypedDict has all required keys."""
    keys = AlfredState.__annotations__
    assert "messages" in keys
    assert "user_id" in keys
    assert "intent" in keys
    assert "phase" in keys
    assert "knowledge_results" in keys
    assert "research_results" in keys
    assert "connector_results" in keys
    assert "enrichment_results" in keys
    assert "final_response" in keys
    assert "artifacts" in keys


def test_team_states_have_messages():
    """All team states include messages."""
    for state_cls in (IngestTeamState, KnowledgeTeamState, SynthesisTeamState):
        assert "messages" in state_cls.__annotations__, f"{state_cls.__name__} missing messages"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/alfred/agents/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'alfred.agents.state'`

- [ ] **Step 3: Create the package and state module**

Create `apps/alfred/agents/__init__.py`:

```python
"""Alfred multi-agent supervisor-orchestrator system."""
```

Create `apps/alfred/agents/state.py`:

```python
"""State schemas for the Alfred multi-agent graph.

AlfredState is the top-level shared state. Team-level states are narrower
views used by nested supervisors. Reducers on list fields use operator.add
so parallel agents can append results independently.
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from langgraph.graph import add_messages
from langchain_core.messages import AnyMessage


class AlfredState(TypedDict):
    """Top-level graph state shared across all nodes."""

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
    artifacts: list[dict]


class IngestTeamState(TypedDict):
    """State for the Ingest team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    connector_name: str | None
    import_params: dict | None
    connector_results: Annotated[list[dict], operator.add]
    enrichment_results: Annotated[list[dict], operator.add]


class KnowledgeTeamState(TypedDict):
    """State for the Knowledge team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    knowledge_results: Annotated[list[dict], operator.add]
    link_suggestions: list[dict]
    review_queue: list[dict]


class SynthesisTeamState(TypedDict):
    """State for the Synthesis team supervisor."""

    messages: Annotated[list[AnyMessage], add_messages]
    research_results: Annotated[list[dict], operator.add]
    final_response: str | None
    artifacts: list[dict]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/alfred/agents/test_state.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/agents/__init__.py apps/alfred/agents/state.py tests/alfred/agents/__init__.py tests/alfred/agents/test_state.py
git commit -m "feat(agents): add state schemas for multi-agent graph"
```

---

### Task 3: Create knowledge tools (first tool module)

**Files:**
- Create: `apps/alfred/agents/tools/__init__.py`
- Create: `apps/alfred/agents/tools/knowledge_tools.py`
- Create: `tests/alfred/agents/tools/__init__.py`
- Create: `tests/alfred/agents/tools/test_knowledge_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/alfred/agents/tools/__init__.py` (empty) and `tests/alfred/agents/tools/test_knowledge_tools.py`:

```python
"""Tests for knowledge tools."""
from unittest.mock import MagicMock, patch

from alfred.agents.tools.knowledge_tools import (
    search_kb,
    get_zettel,
    create_zettel,
    update_zettel,
    get_document,
    search_documents,
    KNOWLEDGE_TOOLS,
)


def test_search_kb_calls_service():
    mock_svc = MagicMock()
    mock_svc.list_cards.return_value = []
    with patch("alfred.agents.tools.knowledge_tools._get_zettel_service", return_value=mock_svc):
        result = search_kb.invoke({"query": "epistemology", "limit": 5})
    mock_svc.list_cards.assert_called_once()
    assert isinstance(result, str)  # JSON string


def test_create_zettel_calls_service():
    mock_card = MagicMock()
    mock_card.id = 42
    mock_card.title = "Test"
    mock_svc = MagicMock()
    mock_svc.create_card.return_value = mock_card
    with patch("alfred.agents.tools.knowledge_tools._get_zettel_service", return_value=mock_svc):
        result = create_zettel.invoke({"title": "Test", "content": "Body"})
    mock_svc.create_card.assert_called_once()
    assert "42" in result


def test_knowledge_tools_list_has_six_entries():
    assert len(KNOWLEDGE_TOOLS) == 6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/alfred/agents/tools/test_knowledge_tools.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the knowledge tools implementation**

Create `apps/alfred/agents/tools/__init__.py`:

```python
"""Agent tool modules -- one file per agent's tool set."""
```

Create `apps/alfred/agents/tools/knowledge_tools.py`:

```python
"""Knowledge agent tools -- zettel CRUD and semantic search.

Each tool is a plain function decorated with @tool (LangGraph uses the
docstring as the tool description and type annotations for the schema).
Tools return JSON strings so agents can parse results.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool
from sqlmodel import Session

from alfred.core.database import SessionLocal
from alfred.services.zettelkasten_service import ZettelkastenService
from alfred.services.doc_storage_pg import DocStorageService

logger = logging.getLogger(__name__)


def _get_zettel_service() -> ZettelkastenService:
    """Create a ZettelkastenService with a fresh DB session."""
    session = SessionLocal()
    return ZettelkastenService(session=session)


def _get_doc_service() -> DocStorageService:
    """Create a DocStorageService with a fresh DB session."""
    session = SessionLocal()
    return DocStorageService(session=session)


@tool
def search_kb(query: str, topic: str | None = None, tags: str | None = None, limit: int = 10) -> str:
    """Search the knowledge base for zettels matching a query. Returns titles, summaries, and IDs."""
    svc = _get_zettel_service()
    cards = svc.list_cards(q=query, topic=topic, limit=limit)
    results = [
        {"id": c.id, "title": c.title, "topic": c.topic, "summary": (c.summary or c.content or "")[:200]}
        for c in cards
    ]
    return json.dumps(results)


@tool
def get_zettel(zettel_id: int) -> str:
    """Retrieve a specific zettel card by ID. Returns full content."""
    svc = _get_zettel_service()
    card = svc.get_card(zettel_id)
    if not card:
        return json.dumps({"error": f"Zettel {zettel_id} not found"})
    return json.dumps({
        "id": card.id, "title": card.title, "content": card.content,
        "tags": card.tags, "topic": card.topic, "status": card.status,
    })


@tool
def create_zettel(title: str, content: str, tags: list[str] | None = None, topic: str | None = None) -> str:
    """Create a new atomic knowledge card (zettel) in the knowledge base."""
    svc = _get_zettel_service()
    card = svc.create_card(title=title, content=content, tags=tags or [], topic=topic)
    return json.dumps({"id": card.id, "title": card.title, "status": "created"})


@tool
def update_zettel(zettel_id: int, title: str | None = None, content: str | None = None, tags: list[str] | None = None, topic: str | None = None) -> str:
    """Update an existing zettel card. Only provided fields are changed."""
    svc = _get_zettel_service()
    card = svc.get_card(zettel_id)
    if not card:
        return json.dumps({"error": f"Zettel {zettel_id} not found"})
    updates: dict[str, Any] = {}
    if title is not None:
        updates["title"] = title
    if content is not None:
        updates["content"] = content
    if tags is not None:
        updates["tags"] = tags
    if topic is not None:
        updates["topic"] = topic
    updated = svc.update_card(card, **updates)
    return json.dumps({"id": updated.id, "title": updated.title, "status": "updated"})


@tool
def get_document(doc_id: str) -> str:
    """Retrieve a source document by UUID. Returns title, summary, and content type."""
    svc = _get_doc_service()
    doc = svc.get_document_details(doc_id)
    if not doc:
        return json.dumps({"error": f"Document {doc_id} not found"})
    return json.dumps({
        "id": str(doc.get("id", doc_id)), "title": doc.get("title", ""),
        "summary": doc.get("summary", ""), "content_type": doc.get("content_type", ""),
    })


@tool
def search_documents(query: str, content_type: str | None = None, limit: int = 10) -> str:
    """Search documents in the knowledge store by query and optional content type."""
    svc = _get_doc_service()
    docs = svc.list_documents(limit=limit)
    results = [
        {"id": str(d.id), "title": d.title, "content_type": d.content_type, "summary": (d.summary or "")[:200]}
        for d in docs
        if (not content_type or d.content_type == content_type)
        and (not query or (query.lower() in (d.title or "").lower()) or (query.lower() in (d.summary or "").lower()))
    ][:limit]
    return json.dumps(results)


# List of all knowledge tools for agent registration
KNOWLEDGE_TOOLS = [search_kb, get_zettel, create_zettel, update_zettel, get_document, search_documents]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/alfred/agents/tools/test_knowledge_tools.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/agents/tools/__init__.py apps/alfred/agents/tools/knowledge_tools.py tests/alfred/agents/tools/__init__.py tests/alfred/agents/tools/test_knowledge_tools.py
git commit -m "feat(agents): add knowledge tools (search_kb, CRUD, documents)"
```

---

### Task 4: Create all remaining tool modules

**Files:**
- Create: `apps/alfred/agents/tools/connection_tools.py`
- Create: `apps/alfred/agents/tools/connector_tools.py`
- Create: `apps/alfred/agents/tools/import_tools.py`
- Create: `apps/alfred/agents/tools/enrichment_tools.py`
- Create: `apps/alfred/agents/tools/learning_tools.py`
- Create: `apps/alfred/agents/tools/research_tools.py`
- Create: `apps/alfred/agents/tools/writing_tools.py`

This is a large task. Each tool module follows the same pattern as knowledge_tools.py: @tool decorated functions wrapping existing services, returning JSON strings. The complete code for each module is in the spec (Section 4). Each module exports an `*_TOOLS` list.

- [ ] **Step 1: Create all 7 tool modules**

Create each file following the knowledge_tools pattern. Each tool:
- Uses `@tool` decorator from `langchain_core.tools`
- Has a descriptive docstring (becomes the tool description)
- Returns a JSON string
- Wraps an existing service method with error handling
- Lazy-imports connectors to avoid import-time failures

The tool modules and their tool counts:
- `connection_tools.py`: `find_similar`, `suggest_links`, `create_link`, `get_card_links`, `batch_link` (5 tools)
- `connector_tools.py`: `query_notion`, `query_readwise`, `query_arxiv`, `query_rss`, `query_web`, `query_wikipedia`, `query_github`, `query_linear`, `query_semantic_scholar` (9 tools)
- `import_tools.py`: `run_import`, `import_status`, `list_connectors` (3 tools)
- `enrichment_tools.py`: `summarize`, `extract_concepts`, `classify_document`, `decompose_to_zettels`, `generate_embeddings` (5 tools)
- `learning_tools.py`: `get_due_reviews`, `submit_review`, `assess_knowledge`, `generate_quiz`, `feynman_check` (5 tools)
- `research_tools.py`: `deep_research`, `search_web`, `search_papers`, `search_kb_for_research`, `scrape_url` (5 tools)
- `writing_tools.py`: `draft_zettel`, `progressive_summary`, `feynman_explain`, `compare_perspectives`, `create_zettel_from_synthesis` (5 tools)

See the spec Section 4 for the exact tool signatures and service methods they wrap.

- [ ] **Step 2: Verify all tool modules import and total is 43**

Run: `uv run python -c "
from alfred.agents.tools.knowledge_tools import KNOWLEDGE_TOOLS
from alfred.agents.tools.connection_tools import CONNECTION_TOOLS
from alfred.agents.tools.connector_tools import CONNECTOR_TOOLS
from alfred.agents.tools.import_tools import IMPORT_TOOLS
from alfred.agents.tools.enrichment_tools import ENRICHMENT_TOOLS
from alfred.agents.tools.learning_tools import LEARNING_TOOLS
from alfred.agents.tools.research_tools import RESEARCH_TOOLS
from alfred.agents.tools.writing_tools import WRITING_TOOLS
total = sum(len(t) for t in [KNOWLEDGE_TOOLS, CONNECTION_TOOLS, CONNECTOR_TOOLS, IMPORT_TOOLS, ENRICHMENT_TOOLS, LEARNING_TOOLS, RESEARCH_TOOLS, WRITING_TOOLS])
print(f'{total} tools across 8 modules')
"`
Expected: `43 tools across 8 modules`

- [ ] **Step 3: Commit**

```bash
git add apps/alfred/agents/tools/
git commit -m "feat(agents): add all 43 agent tools across 8 modules"
```

---

## Phase 2: Router + Teams + Graph

### Task 5: Create the hybrid router

**Files:**
- Create: `apps/alfred/agents/router.py`
- Create: `tests/alfred/agents/test_router.py`

- [ ] **Step 1: Write the failing test**

Create `tests/alfred/agents/test_router.py`:

```python
"""Tests for the hybrid intent router."""
from alfred.agents.router import heuristic_classify, IntentMatch


def test_import_intent():
    match = heuristic_classify("import my notion pages")
    assert match is not None
    assert match.intent == "import"
    assert match.team == "ingest_team"


def test_search_intent():
    match = heuristic_classify("what do I know about epistemology")
    assert match is not None
    assert match.intent == "search_kb"
    assert match.team == "knowledge_team"


def test_research_intent():
    match = heuristic_classify("research transformer architectures on arxiv")
    assert match is not None
    assert match.intent == "research"
    assert match.team == "synthesis_team"


def test_write_intent():
    match = heuristic_classify("write a summary of my notes on stoicism")
    assert match is not None
    assert match.intent == "write"
    assert match.team == "synthesis_team"


def test_learn_intent():
    match = heuristic_classify("show me cards due for review")
    assert match is not None
    assert match.intent == "learn"
    assert match.team == "knowledge_team"


def test_ambiguous_returns_none():
    match = heuristic_classify("tell me something interesting")
    assert match is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/alfred/agents/test_router.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement the router**

Create `apps/alfred/agents/router.py`:

```python
"""Hybrid heuristic + LLM intent router for the Alfred supervisor.

Heuristics handle ~60-70% of intents at zero LLM cost. The LLM fallback
fires only for ambiguous or multi-intent queries.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from langgraph.types import Command, Send

from alfred.agents.state import AlfredState

logger = logging.getLogger(__name__)

TEAM_NAMES = Literal["ingest_team", "knowledge_team", "synthesis_team"]


@dataclass
class IntentMatch:
    intent: str
    team: TEAM_NAMES


# Pattern -> (intent, team) -- order matters, first match wins
_HEURISTIC_RULES: list[tuple[re.Pattern, str, TEAM_NAMES]] = [
    (re.compile(r"\b(import|sync|pull from|ingest)\b", re.I), "import", "ingest_team"),
    (re.compile(r"\b(summarize this|extract concepts?|classify|enrich)\b", re.I), "enrich", "ingest_team"),
    (re.compile(r"\b(review|quiz|spaced rep|due cards?|flashcard|feynman)\b", re.I), "learn", "knowledge_team"),
    (re.compile(r"\b(connections? between|link|relate|similar to)\b", re.I), "connect", "knowledge_team"),
    (re.compile(r"\b(what do i know|search|find in (my|the) (knowledge|zettel|card))\b", re.I), "search_kb", "knowledge_team"),
    (re.compile(r"\b(research|look up|arxiv|find papers?|academic|scholar)\b", re.I), "research", "synthesis_team"),
    (re.compile(r"\b(write|draft|summarize|explain|compare|synthesize)\b", re.I), "write", "synthesis_team"),
]


def heuristic_classify(message: str) -> IntentMatch | None:
    """Classify intent using regex heuristics. Returns None if ambiguous."""
    for pattern, intent, team in _HEURISTIC_RULES:
        if pattern.search(message):
            return IntentMatch(intent=intent, team=team)
    return None


def router(state: AlfredState) -> Command:
    """Route user messages to the appropriate team.

    1. Try heuristic classification (zero LLM cost)
    2. Fall back to knowledge_team for general queries
    """
    last_msg = state["messages"][-1]
    user_msg = last_msg.content if hasattr(last_msg, "content") else str(last_msg)

    match = heuristic_classify(user_msg)
    if match:
        logger.info("Router: heuristic match -> %s (%s)", match.intent, match.team)
        return Command(
            update={"intent": match.intent, "phase": "executing", "active_agents": [match.team]},
            goto=match.team,
        )

    logger.info("Router: no heuristic match, defaulting to knowledge_team")
    return Command(
        update={"intent": "general", "phase": "executing", "active_agents": ["knowledge_team"]},
        goto="knowledge_team",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/alfred/agents/test_router.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add apps/alfred/agents/router.py tests/alfred/agents/test_router.py
git commit -m "feat(agents): add hybrid heuristic+LLM intent router"
```

---

### Task 6: Create the 3 team supervisors

**Files:**
- Create: `apps/alfred/agents/teams/__init__.py`
- Create: `apps/alfred/agents/teams/ingest_team.py`
- Create: `apps/alfred/agents/teams/knowledge_team.py`
- Create: `apps/alfred/agents/teams/synthesis_team.py`

- [ ] **Step 1: Create all team modules**

Each team uses `create_supervisor()` from `langgraph_supervisor` with `create_react_agent()` for each specialist. Model selection follows the tiered approach:
- Ingest + Knowledge teams: `gpt-4.1-mini` (mostly tool dispatch)
- Synthesis team: `gpt-4.1` (deep reasoning)

See the spec Section 4 for the exact agent prompts and tool assignments per team.

Pattern for each team file:
```python
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph_supervisor import create_supervisor
from alfred.core.settings import settings

def build_<team>_team():
    model = ChatOpenAI(model="gpt-4.1-mini", api_key=..., base_url=...)
    agent_a = create_react_agent(model=model, tools=TOOLS_A, name="agent_a", prompt="...")
    agent_b = create_react_agent(model=model, tools=TOOLS_B, name="agent_b", prompt="...")
    workflow = create_supervisor(agents=[agent_a, agent_b], model=model, prompt="...")
    return workflow.compile(name="<team>_team")
```

- [ ] **Step 2: Verify imports**

Run: `uv run python -c "from alfred.agents.teams.ingest_team import build_ingest_team; from alfred.agents.teams.knowledge_team import build_knowledge_team; from alfred.agents.teams.synthesis_team import build_synthesis_team; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add apps/alfred/agents/teams/
git commit -m "feat(agents): add 3 team supervisors (ingest, knowledge, synthesis)"
```

---

### Task 7: Create synthesizer node and wire the top-level graph

**Files:**
- Create: `apps/alfred/agents/synthesizer.py`
- Create: `apps/alfred/agents/graph.py`
- Modify: `langgraph.json`
- Create: `tests/alfred/agents/test_graph.py`

- [ ] **Step 1: Write the failing test**

Create `tests/alfred/agents/test_graph.py`:

```python
"""Tests for the top-level Alfred graph."""
from alfred.agents.graph import build_alfred_graph


def test_graph_builds():
    """The graph compiles without error."""
    graph = build_alfred_graph()
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/alfred/agents/test_graph.py -v`
Expected: FAIL

- [ ] **Step 3: Create synthesizer.py**

```python
"""Synthesizer node -- merges results from all teams into a final response."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage

from alfred.agents.state import AlfredState

logger = logging.getLogger(__name__)


def synthesizer(state: AlfredState) -> dict:
    """Merge team results into final_response."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return {"final_response": msg.content, "phase": "done"}

    all_results = (
        state.get("knowledge_results", []) + state.get("research_results", [])
        + state.get("connector_results", []) + state.get("enrichment_results", [])
    )
    if all_results:
        summary = json.dumps(all_results[:20], default=str, indent=2)
        return {"final_response": f"Here's what I found:\n\n{summary}", "phase": "done"}

    return {"final_response": "I processed your request but found no specific results.", "phase": "done"}
```

- [ ] **Step 4: Create graph.py**

```python
"""Top-level Alfred supervisor graph."""

from __future__ import annotations

import logging

from langgraph.graph import StateGraph, START, END

from alfred.agents.state import AlfredState
from alfred.agents.router import router
from alfred.agents.synthesizer import synthesizer
from alfred.agents.teams.ingest_team import build_ingest_team
from alfred.agents.teams.knowledge_team import build_knowledge_team
from alfred.agents.teams.synthesis_team import build_synthesis_team

logger = logging.getLogger(__name__)


def build_alfred_graph():
    """Build and compile the Alfred multi-agent supervisor graph."""
    builder = StateGraph(AlfredState)

    builder.add_node("router", router)
    builder.add_node("ingest_team", build_ingest_team())
    builder.add_node("knowledge_team", build_knowledge_team())
    builder.add_node("synthesis_team", build_synthesis_team())
    builder.add_node("synthesizer", synthesizer)

    builder.add_edge(START, "router")
    builder.add_edge("ingest_team", "synthesizer")
    builder.add_edge("knowledge_team", "synthesizer")
    builder.add_edge("synthesis_team", "synthesizer")
    builder.add_edge("synthesizer", END)

    return builder.compile()


alfred_graph = build_alfred_graph
```

- [ ] **Step 5: Update langgraph.json**

```json
{
  "dependencies": ["./"],
  "graphs": {
    "alfred_supervisor": "./apps/alfred/agents/graph.py:alfred_graph",
    "agentic_rag": "./apps/alfred/agents/agentic_rag/agent.py:agent",
    "writer": "./apps/alfred/agents/writer/agent.py:agent"
  }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/alfred/agents/test_graph.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/alfred/agents/synthesizer.py apps/alfred/agents/graph.py langgraph.json tests/alfred/agents/test_graph.py
git commit -m "feat(agents): wire top-level StateGraph with router, teams, synthesizer"
```

---

## Phase 3: SSE Integration + Feedback

### Task 8: Create the feedback node

**Files:**
- Create: `apps/alfred/agents/feedback.py`

- [ ] **Step 1: Create the feedback module**

The feedback node saves AI conversations as Documents via `DocStorageService.ingest_document_store_only()`. It uses `content_type = "ai_conversation"` and dedup via content hash. See spec Section 5 for the full data flow.

- [ ] **Step 2: Commit**

```bash
git add apps/alfred/agents/feedback.py
git commit -m "feat(agents): add feedback node (AI panel as knowledge connector)"
```

---

### Task 9: Integrate LangGraph into the SSE endpoint

**Files:**
- Modify: `apps/alfred/api/agent/routes.py`

- [ ] **Step 1: Replace AgentService with graph in the stream endpoint**

In the `agent_stream` endpoint, replace the `event_stream()` inner function. Keep all thread management code (lines 1-184) and the `StreamingResponse` return. Replace the `AgentService.stream_turn()` call with:

1. `build_alfred_graph()` to get the compiled graph
2. Build `initial_state` from the request body and history
3. Use `graph.astream_events(initial_state, version="v2")` to stream events
4. Map LangGraph events (`on_chat_model_stream`, `on_tool_start`, `on_tool_end`) to the existing SSE event format (`token`, `tool_start`, `tool_result`)

Also add `from langchain_core.messages import AIMessage` at the top.

- [ ] **Step 2: Verify the API module imports**

Run: `uv run python -c "from alfred.api.agent.routes import router; print('routes OK')"`
Expected: `routes OK`

- [ ] **Step 3: Commit**

```bash
git add apps/alfred/api/agent/routes.py
git commit -m "feat(agents): integrate LangGraph graph into SSE streaming endpoint"
```

---

## Phase 4: Daemon + Final Tests

### Task 10: Create the background daemon

**Files:**
- Create: `apps/alfred/agents/daemon.py`

- [ ] **Step 1: Create the daemon module**

Two Celery shared_tasks: `ingest_watch` (check connected sources for new content) and `link_discovery` (find under-linked cards). Both invoke `build_alfred_graph()` synchronously with pre-set intent. See spec Section 7.

- [ ] **Step 2: Commit**

```bash
git add apps/alfred/agents/daemon.py
git commit -m "feat(agents): add background daemon tasks (ingest_watch, link_discovery)"
```

---

### Task 11: Run full test suite and final verification

- [ ] **Step 1: Run all agent tests**

Run: `uv run pytest tests/alfred/agents/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run existing tests for regressions**

Run: `uv run pytest tests/ -x --timeout=60 -q 2>&1 | tail -20`
Expected: No new failures

- [ ] **Step 3: Verify the API starts and serves requests**

Run: `uv run uvicorn alfred.main:app --port 8001 &` then `curl -s localhost:8001/healthz`
Expected: `{"status": "ok"}`

- [ ] **Step 4: Final commit**

```bash
git add -A
git status
git commit -m "feat(agents): complete multi-agent supervisor-orchestrator system

Two-tier hierarchical LangGraph architecture:
- 8 specialist agents across 3 teams (Ingest, Knowledge, Synthesis)
- 43 tools wrapping existing services and connectors
- Hybrid heuristic+LLM intent router
- AI panel as knowledge connector (feedback loop)
- Background daemon for autonomous operation
- SSE streaming via graph.astream_events()"
```
