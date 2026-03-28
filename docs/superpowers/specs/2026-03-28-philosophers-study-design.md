# The Philosopher's Study — Design Spec

## Overview

The Philosopher's Study is an Exploration Engine for Alfred — a dedicated space where users have philosophical conversations powered by their own knowledge base. Alfred responds with depth, surfaces related knowledge, identifies gaps, and can shift between philosophical framework lenses to examine questions from multiple perspectives.

Philosophy is the feature, not scaffolding. The exploration IS the product.

## Problem Statement

Alfred ingests, decomposes, and connects knowledge. But there's no space for users to *think* with that knowledge — to ask deep questions, examine ideas through multiple philosophical lenses, and discover what they know and what they're missing. The Philosopher's Study fills this gap: a first-class thinking environment that gets smarter because it knows what you know.

## User Stories

- As a user, I want to ask a deep philosophical question and get a response that references my own knowledge base, so my exploration builds on what I've already learned.
- As a user, I want to see what I *don't* know about a topic (knowledge gaps), so I can direct my future reading.
- As a user, I want to examine a question through multiple philosophical frameworks (Stoic, Kantian, Utilitarian, etc.), so I can understand different perspectives.
- As a user, I want to save insights from explorations as Zettelkasten cards, so my thinking feeds back into my knowledge base.
- As a user, I want to browse and resume past explorations, so I can revisit and deepen my thinking over time.

## Architecture

### UI: Three Entry Points

1. **`/think` route** — Full-page Philosopher's Study (the "room")
2. **AI Panel (J key)** — Quick-access exploration (the "doorway"), with "Deep Explore" button to open `/think`
3. **Sidebar nav** — "THINK" entry between Notes and Knowledge

### Page Layout: `/think`

Three-column layout following Alfred's existing app shell pattern:

```
┌──────────────────────────────────────────────────────────────┐
│  SIDEBAR (220px)  │  CONVERSATION (flex-1)  │  CONTEXT (360px) │
│                   │                         │                  │
│  Nav items        │  Thread history         │  KNOWLEDGE PANEL │
│  ...              │  [Framework lenses]     │  Related Cards   │
│  * THINK          │                         │  Related Docs    │
│  ...              │  Messages with inline   │  Knowledge Gaps  │
│                   │  [knowledge anchors]    │  Mini Graph      │
│  EXPLORATIONS     │                         │  Stats           │
│  - Thread 1       │  [Input field]          │                  │
│  - Thread 2       │                         │                  │
└──────────────────────────────────────────────────────────────┘
```

- Conversation column takes all remaining space (flex-1)
- Context panel is fixed 360px, collapsible via `K` shortcut
- Exploration threads listed in sidebar, persistent and browsable
- Framework lens bar above input as toggleable chips

## Components

### 1. Conversation Engine

The core interaction. User types a question, Alfred responds with philosophical depth while integrating the user's knowledge base.

**Message pipeline (per user message):**

1. Embed the message as a vector
2. Parallel retrieval:
   - Search Zettelkasten cards (top-k cosine similarity)
   - Search Documents (top-k cosine similarity)
   - Search concept graph for related nodes
3. Gap analysis: compare topic's expected concept space vs. user's knowledge
4. Build LLM prompt:
   - System: philosopher persona + active lens instructions
   - Context: surfaced cards/docs as reference material
   - History: thread conversation history
   - User: current message
5. Stream LLM response via SSE
6. Post-process: extract knowledge anchors, update context panel, persist message

**Knowledge anchors:** Inline markers in Alfred's response that highlight the corresponding item in the Context Panel when clicked. Implementation: after the LLM response completes, a post-processing step matches surfaced card titles and concepts against the response text using fuzzy string matching. Matches are wrapped in anchor markup and emitted as `anchor` SSE events with card IDs and text offsets. The frontend renders these as clickable orange-underlined spans.

### 2. Framework Lenses

Toggleable philosophical frameworks that shape Alfred's reasoning. Rendered as chips above the input field.

| Lens | Behavior |
|------|----------|
| Socratic | Responds primarily with questions. Forces user to articulate position. |
| Stoic | Frames through control/acceptance. "What's in your power here?" |
| Existentialist | Frames through freedom, authenticity, meaning-creation. |
| Utilitarian | Frames through consequences and outcomes. |
| Kantian | Frames through duty and universalizability. |
| Virtue Ethics | Frames through character and the good life. |
| Eastern | Buddhist/Daoist/Confucian perspectives. |

Custom user-defined lenses are deferred to v2 after validating lens usage patterns.

Multiple lenses can be active simultaneously. When multiple are active, Alfred presents the question through each and shows where they agree/diverge.

### 3. Knowledge Context Panel (Right Sidebar)

Four collapsible sections:

**3a. Related Knowledge**
- Zettelkasten cards matching the current topic, sorted by relevance score
- Documents from the document store matching the current topic
- Each item is clickable (opens detail popover)

**3b. Knowledge Gaps**
- Concepts the user hasn't explored yet, detected by comparing topic concept space against existing knowledge
- Each gap shows: concept name, why it matters, "Add to reading list" action
- "Add to reading list" creates a stub ZettelCard tagged `gap` + `to-explore`
- Shows coverage percentage: "Your coverage: 62% (5 of ~8 key concepts)"

**3c. Related Concepts** (MVP: list view, graph visualization deferred to v2)
- "Your Concepts" — list of concepts from your knowledge base related to this exploration
- "Missing Concepts" — list of gap concepts you haven't explored
- Each item clickable to open card detail or gap detail
- v2: upgrade to interactive force-directed graph

**3d. Exploration Stats**
- Topics touched, cards referenced, gaps identified, new cards created, frameworks used

### 4. Thread Persistence

Every exploration is saved as a first-class object:
- Auto-titled from first message (user can rename)
- Listed in sidebar under "EXPLORATIONS"
- Stores: all messages, active lenses per message, knowledge references, detected gaps
- Can be: resumed, archived (export to notes deferred to v2)

### 5. Insight-to-Card Generation

Select text from any Alfred response -> "Save as Card" action:
1. Creates ZettelCard with selected content
2. Auto-tags with thread's topics
3. Links to cards surfaced as context
4. If the card fills a detected gap, marks that gap "resolved"

Closes the loop: explore -> discover -> capture -> knowledge base grows -> future explorations are richer.

### 6. AI Panel Upgrade (Doorway)

The existing AI Panel (J key toggle) gains:
- "Deep Explore" button that opens `/think` with current conversation context
- Compact knowledge context view (related cards only, no graph)
- Conversations can be "promoted" to full Exploration Threads

## Data Model

All models inherit from the project's `Model` base class (provides `id`, `created_at`, `updated_at`). All models include `user_id: str` for multi-tenancy (defaults to placeholder while Clerk auth is disabled).

### ExplorationThread (inherits Model)

| Field | Type | Description |
|-------|------|-------------|
| user_id | str | User identifier (FK-ready for Clerk re-enablement) |
| title | str | Auto-generated or user-named |
| status | str | "active" or "archived" |
| summary | str? | AI-generated thread summary |
| topic_tags | list[str] | Auto-extracted topic tags |

Note: `active_lenses` lives on ExplorationMessage only, not the thread. The thread's "current" lenses = the last message's `active_lenses`.

### ExplorationMessage (inherits Model)

| Field | Type | Description |
|-------|------|-------------|
| user_id | str | User identifier |
| thread_id | int | FK to ExplorationThread |
| role | str | "user" or "assistant" |
| content | str | Message text (markdown) |
| active_lenses | list[str] | Lenses active when this message was sent/generated |
| knowledge_refs | list[int] | IDs of surfaced ZettelCards |
| document_refs | list[int] | IDs of surfaced Documents |
| gap_refs | list[dict] | Detected gaps [{concept, description, importance}] |

### KnowledgeGap (inherits Model)

| Field | Type | Description |
|-------|------|-------------|
| user_id | str | User identifier |
| concept | str | Gap concept name |
| description | str | Why this matters |
| detected_in | int | FK to ExplorationThread where first found |
| status | str | "open", "exploring", or "resolved" |
| related_cards | list[int] | ZettelCards that partially cover this |
| importance | float | 0-1 importance score |
| resolved_at | datetime? | When gap was filled |

### Migration

Run `alembic revision --autogenerate -m 'add_philosopher_study_tables'`. Test up/down migrations before deployment. Index on `user_id` for all three tables.

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/think/threads` | Create new exploration thread |
| GET | `/api/think/threads` | List threads (`?q=search&status=active&limit=20&skip=0`) |
| GET | `/api/think/threads/{id}` | Get thread with all messages |
| POST | `/api/think/threads/{id}/messages` | Send message, get AI response (SSE stream) |
| PATCH | `/api/think/threads/{id}` | Update thread (title, status) |
| GET | `/api/think/threads/{id}/context` | Get knowledge context for current thread |
| POST | `/api/think/threads/{id}/cards` | Create Zettelkasten card from exploration insight |
| GET | `/api/think/gaps` | List all knowledge gaps across threads |
| PATCH | `/api/think/gaps/{id}` | Update gap status |

### SSE Event Format

The `POST /api/think/threads/{id}/messages` endpoint streams responses as Server-Sent Events:

```
event: token
data: {"content": "chunk of response text"}

event: anchor
data: {"card_id": 123, "text": "Arendt's Banality of Evil", "offset": 245}

event: context
data: {"related_cards": [...], "related_docs": [...], "gaps": [...]}

event: done
data: {"message_id": 456}

event: error
data: {"message": "LLM provider unavailable", "retryable": true}
```

- `token` events stream as the LLM generates text
- `anchor` events fire after response is complete, linking inline references to knowledge base items (post-processed by matching surfaced card titles/concepts against response text)
- `context` event fires after parallel retrieval completes (may arrive before response is done)
- `done` signals completion with the persisted message ID
- `error` signals failure with retry guidance

## Design System Compliance

All UI follows DESIGN.md:
- **Nav label:** JetBrains Mono, 12px, uppercase, tracked — "THINK"
- **Conversation text:** DM Sans, 16px body for messages
- **Alfred's display quotes:** Instrument Serif for emphasized philosophical text
- **Framework lens chips:** JetBrains Mono, 10px, uppercase, accent-muted background when active, accent border
- **Knowledge anchors:** Inline orange text with subtle underline, accent color
- **Gap indicators:** Warning color (#B45309) icon + DM Sans text
- **Context panel cards:** Standard card styling — bg-card, 1px border, 8px radius, serif title
- **Dark mode default** with warm charcoal surfaces

## Error Handling

| Scenario | Behavior |
|----------|----------|
| RAG returns no results | Respond from LLM only. Context panel: "No matching knowledge — new frontier for you" |
| LLM streaming fails | Retry once, then show error + "Try again" button |
| Gap analysis slow | Render conversation immediately, gaps populate async via Celery task (`@shared_task def analyze_knowledge_gaps(thread_id, message_id)`). Context Panel shows loading skeleton for gaps section. Target: gaps appear within 2-3 seconds. |
| Empty state (first use) | Guided prompt suggestions from user's most-tagged topics |
| Context panel empty | Show onboarding: "Start capturing knowledge to enrich your explorations" |

## Leverages Existing Infrastructure

- RAG agent (`apps/alfred/services/`) for vector search
- Zettelkasten service for card CRUD and search
- Document storage service for doc retrieval
- LLM factory for provider-agnostic AI calls (OpenAI/Anthropic/Ollama)
- Celery for async gap analysis
- Existing app shell layout and sidebar
- Existing AI Panel component (upgrade path)

## Testing Strategy

- **Backend:** API tests for thread CRUD, message pipeline, knowledge retrieval accuracy
- **Frontend:** Component tests for conversation rendering, context panel updates, lens toggling, card generation
- **Integration:** E2E test of send message -> response with knowledge context -> save as card

## Success Criteria

1. User can have a philosophical conversation that references their own knowledge
2. Knowledge gaps are detected and displayed in real-time
3. Framework lenses meaningfully change the character of Alfred's responses
4. Insights can be captured as Zettelkasten cards in one action
5. Explorations persist and are browsable/resumable
6. The experience feels like "thinking with a brilliant friend who's read everything you've read"

## Rate Limiting

20 messages per thread per hour (configurable). Return 429 with `Retry-After` header if exceeded. Prevents runaway LLM costs.

## MVP Scope vs. v2

**MVP (this spec):**
- Conversation engine with knowledge retrieval
- 7 predefined framework lenses
- Knowledge context panel (cards, docs, gaps as lists, stats)
- Thread persistence and sidebar listing with search
- Insight-to-card generation
- AI Panel "Deep Explore" doorway
- SSE streaming with knowledge anchors

**Deferred to v2:**
- Custom user-defined lenses
- Force-directed concept graph visualization
- Thread export to notes/markdown
- Thread forking (branch an exploration)
