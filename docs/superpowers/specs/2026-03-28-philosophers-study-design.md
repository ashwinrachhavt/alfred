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

**Knowledge anchors:** Inline markers in Alfred's response like `[-> Your card: Arendt's Banality]` that highlight the corresponding item in the Context Panel when clicked.

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
| Custom | User-defined lens with custom instructions. |

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

**3c. Concept Map**
- Small interactive force-directed graph
- Solid nodes = existing concepts in user's knowledge (warm gray)
- Dashed nodes = gap concepts (orange border)
- Edges = relationships Alfred has identified
- Clickable nodes open card detail or gap detail

**3d. Exploration Stats**
- Topics touched, cards referenced, gaps identified, new cards created, frameworks used

### 4. Thread Persistence

Every exploration is saved as a first-class object:
- Auto-titled from first message (user can rename)
- Listed in sidebar under "EXPLORATIONS"
- Stores: all messages, active lenses per message, knowledge references, detected gaps
- Can be: resumed, archived, exported as notes

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

### ExplorationThread

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| title | str | Auto-generated or user-named |
| created_at | datetime | Thread creation time |
| updated_at | datetime | Last activity |
| status | str | "active" or "archived" |
| active_lenses | list[str] | Currently active framework lenses |
| summary | str? | AI-generated thread summary |
| topic_tags | list[str] | Auto-extracted topic tags |

### ExplorationMessage

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| thread_id | int | FK to ExplorationThread |
| role | str | "user" or "assistant" |
| content | str | Message text (markdown) |
| active_lenses | list[str] | Lenses active for this message |
| knowledge_refs | list[int] | IDs of surfaced ZettelCards |
| document_refs | list[int] | IDs of surfaced Documents |
| gap_refs | list[dict] | Detected gaps [{concept, description, importance}] |
| created_at | datetime | Message timestamp |

### KnowledgeGap

| Field | Type | Description |
|-------|------|-------------|
| id | int | Primary key |
| concept | str | Gap concept name |
| description | str | Why this matters |
| detected_in | int | FK to ExplorationThread where first found |
| status | str | "open", "exploring", or "resolved" |
| related_cards | list[int] | ZettelCards that partially cover this |
| importance | float | 0-1 importance score |
| created_at | datetime | Detection time |
| resolved_at | datetime? | When gap was filled |

## API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/think/threads` | Create new exploration thread |
| GET | `/api/think/threads` | List all threads (with pagination) |
| GET | `/api/think/threads/{id}` | Get thread with all messages |
| POST | `/api/think/threads/{id}/messages` | Send message, get AI response (SSE stream) |
| PATCH | `/api/think/threads/{id}` | Update thread (title, lenses, status) |
| GET | `/api/think/threads/{id}/context` | Get knowledge context for current thread |
| POST | `/api/think/threads/{id}/cards` | Create Zettelkasten card from exploration insight |
| GET | `/api/think/gaps` | List all knowledge gaps across threads |
| PATCH | `/api/think/gaps/{id}` | Update gap status |

## Design System Compliance

All UI follows DESIGN.md:
- **Nav label:** JetBrains Mono, 12px, uppercase, tracked — "THINK"
- **Conversation text:** DM Sans, 16px body for messages
- **Alfred's display quotes:** Instrument Serif for emphasized philosophical text
- **Framework lens chips:** JetBrains Mono, 10px, uppercase, accent-muted background when active, accent border
- **Knowledge anchors:** Inline orange text with subtle underline, accent color
- **Gap indicators:** Warning color (#B45309) icon + DM Sans text
- **Context panel cards:** Standard card styling — bg-card, 1px border, 8px radius, serif title
- **Graph nodes:** Warm gray fill (existing) / orange stroke-only (gaps)
- **Dark mode default** with warm charcoal surfaces

## Error Handling

| Scenario | Behavior |
|----------|----------|
| RAG returns no results | Respond from LLM only. Context panel: "No matching knowledge — new frontier for you" |
| LLM streaming fails | Retry once, then show error + "Try again" button |
| Gap analysis slow | Render conversation immediately, gaps populate async |
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
