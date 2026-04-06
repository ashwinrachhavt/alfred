# Alfred Dictionary — Design Spec

**Date:** 2026-04-05
**Status:** Approved
**Approach:** Layered — Standalone Core (Phase 1) + Progressive Integration (Phase 2)

## Overview

A beautiful, iBooks-style dictionary built into Alfred. Operates in two modes: **standalone** (full dictionary page with search-first UX) and **embedded** (popover, command palette, sidebar panel accessible from anywhere in the app). Combines structured data from external dictionary APIs with LLM-generated contextual explanations and a personal vocabulary journal with save-with-intent and spaced repetition.

## Phases

- **Phase 1:** Standalone dictionary page, command palette lookup, save-with-intent, external API aggregation, LLM enrichment
- **Phase 2:** Embedded popover in Notes/Documents, knowledge connections panel, Qdrant indexing, spaced repetition via existing learning system, dictionary sidebar panel

---

## Data Model

### `VocabularyEntry` Table

| Column | Type | Purpose |
|--------|------|---------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK → User | Owner |
| `word` | str | The headword |
| `language` | str (default `"en"`) | Language code |
| `pronunciation_ipa` | str, nullable | IPA transcription |
| `pronunciation_audio_url` | str, nullable | URL to audio file |
| `definitions` | JSON | Array of `{part_of_speech, sense_number, definition, examples: []}` |
| `etymology` | text, nullable | Etymology text |
| `synonyms` | JSON, nullable | Array of `{sense, words: []}` |
| `antonyms` | JSON, nullable | Array of `{sense, words: []}` |
| `usage_notes` | text, nullable | Register, collocations, confused-with |
| `wikipedia_summary` | text, nullable | Cached Wikipedia excerpt |
| `ai_explanation` | text, nullable | LLM-generated contextual explanation |
| `ai_explanation_domains` | JSON, nullable | Domains the AI explanation was generated for |
| `personal_notes` | text, nullable | User's own annotations/mnemonics |
| `domain_tags` | JSON | Array of domain strings (e.g., `["system_design", "finance"]`) |
| `save_intent` | enum | `learning` / `reference` / `encountered` |
| `bloom_level` | int (1-6) | User's self-assessed comprehension depth |
| `source_urls` | JSON | Where the structured data came from |
| `zettel_id` | UUID FK → ZettelCard, nullable | Link to knowledge graph (Phase 2) |
| `created_at` | datetime | TimestampMixin |
| `updated_at` | datetime | TimestampMixin |

### Design Decisions

- **`definitions` as JSON** — definitions are always fetched as a complete set, never queried independently. JSON avoids joins and keeps reads fast. PostgreSQL `jsonb` allows indexing if needed later.
- **`save_intent` enum** drives behavior: `learning` entries enter spaced repetition, `reference` entries are bookmarked, `encountered` entries are passive history.
- **`zettel_id` nullable** — Phase 1 operates without knowledge graph links. Phase 2 auto-creates a Zettel card on save, linking vocabulary to the graph.
- **`ai_explanation_domains`** tracks which domains the AI explanation covers, enabling regeneration when the user adds new domains.

---

## Backend Service & API

### `dictionary_service.py`

Three responsibilities:

**1. Lookup (external aggregation)**

```python
async def lookup(word: str, language: str = "en", user_domains: list[str] | None = None) -> DictionaryResult
```

Calls multiple sources in parallel, merges into a unified `DictionaryResult`:
- **Wiktionary REST API** → definitions, pronunciation IPA, etymology, synonyms/antonyms
- **Existing Wikipedia service** (`alfred.services.wikipedia.retrieve_wikipedia()`) → encyclopedia summary
- **LLM via `llm_factory.py`** → contextual explanation tailored to user's domains

**2. Save (vocabulary journal)**

```python
async def save_entry(user_id: UUID, word: str, result: DictionaryResult, save_intent: SaveIntent, personal_notes: str | None = None, domain_tags: list[str] | None = None) -> VocabularyEntry
```

**3. Collection (vocabulary management)**

```python
async def list_entries(user_id: UUID, filters: VocabularyFilters | None = None) -> list[VocabularyEntry]
async def search_entries(user_id: UUID, query: str) -> list[VocabularyEntry]
async def update_entry(user_id: UUID, entry_id: UUID, updates: VocabularyUpdate) -> VocabularyEntry
async def delete_entry(user_id: UUID, entry_id: UUID) -> None
```

### API Routes — `apps/alfred/api/dictionary/routes.py`

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/dictionary/lookup?word=X&lang=en` | External lookup (no save) |
| `POST` | `/api/dictionary/entries` | Save word to vocabulary |
| `GET` | `/api/dictionary/entries` | List vocabulary (filterable by domain, intent, date) |
| `GET` | `/api/dictionary/entries/{id}` | Get single entry |
| `PATCH` | `/api/dictionary/entries/{id}` | Update personal notes, domain tags, bloom level |
| `DELETE` | `/api/dictionary/entries/{id}` | Remove from vocabulary |
| `GET` | `/api/dictionary/search?q=X` | Search saved vocabulary + trigger external lookup if no match |
| `POST` | `/api/dictionary/entries/{id}/regenerate-ai` | Re-generate AI explanation with updated domains |

### External API Strategy

- **Wiktionary:** Free REST API (`en.wiktionary.org/api/rest_v1/page/definition/{word}`). No key required.
- **Wikipedia:** Reuse existing `alfred.services.wikipedia.retrieve_wikipedia()`.
- **LLM:** Use existing `llm_factory.py`. System prompt includes user's taxonomy domains (from `taxonomy_service`). Temperature 0.3. Cached per word+domains combo.

### Fallback Chain

| Source | Fails? | Fallback |
|--------|--------|----------|
| Wiktionary | No article | LLM generates definitions |
| Wikipedia | No article | Section omitted |
| LLM | API error | Section shows "Generate explanation" button for retry |

---

## Frontend — Standalone Dictionary Page

### Route: `/dictionary`

Full-width page within existing app shell (sidebar + main content). Search-first: big search bar front and center.

### Components

**`DictionarySearchBar`**
- Large, prominent search input (Source Serif 4 placeholder)
- Debounced search (300ms)
- Dropdown shows two groups: "Your Vocabulary" (saved) and "Look Up" (external)
- Keyboard-first: arrow keys to navigate, Enter to select, Cmd+K global shortcut

**`DictionaryEntry`** — Section rendering order:

| Section | Typography | Behavior |
|---------|-----------|----------|
| Headword | Source Serif 4, display size | Word + pronunciation speaker icon |
| Pronunciation | Berkeley Mono | IPA transcription, clickable audio |
| Part of Speech + Definitions | DM Sans body, numbered | Grouped by POS, examples in italic |
| Save Bar | Sticky bottom | Intent selector + Save button (unsaved words only) |
| Etymology | DM Sans muted, collapsible | Collapsed by default |
| Synonyms & Antonyms | Inline badge chips | Clickable → navigates to that word |
| AI Contextual Explanation | DM Sans, accent-bordered panel | Domain-tagged, regenerate button |
| Usage Notes | DM Sans muted | Register, collocations |
| Encyclopedia | Collapsible card | Wikipedia summary, "Read more" link |
| Knowledge Connections | Card list (Phase 2) | Zettels, notes, documents mentioning this word |
| Personal Annotations | Editable textarea | Only for saved entries, rich text |

**`VocabularyCollection`** — Tab/toggle on dictionary page
- Compact card grid: word + POS + domain tags + bloom level
- Filterable: domain, intent, bloom level, date range
- Sortable: alphabetical, recently added, bloom level ascending

### Visual Treatment (DESIGN.md alignment)

- Headword in Source Serif 4 — feels like a printed dictionary page
- Definitions: clean numbered lists, generous line height
- Etymology: subtle left border in `--alfred-accent-muted`
- AI explanation panel: deep orange accent border (`#E8590C`)
- Domain tags: uppercase DM Sans 500 badge style
- Berkeley Mono: IPA, pronunciation keys, timestamps, bloom indicators
- Progressive rendering: each section has its own skeleton loader

### State Management

**Zustand store:** `web/lib/stores/dictionary-store.ts`
- `currentLookup` — active `DictionaryResult`
- `savedEntries` — paginated vocabulary list
- `filters` — active filter state
- `isLooking` — loading state

**React Query:** `web/features/dictionary/`
- `queries.ts` — `useDictionaryLookup`, `useVocabularyEntries`, `useVocabularyEntry`
- `mutations.ts` — `useSaveEntry`, `useUpdateEntry`, `useDeleteEntry`

---

## Embedded Experiences (Phase 2)

### Command Palette (`Cmd+D`)
- Global keyboard shortcut opens floating modal
- Reuses `DictionarySearchBar` component
- Compact `DictionaryEntry` view: headword, pronunciation, top 2 definitions, save button
- "Open full entry" link → `/dictionary?word=X`

### Text Selection Popover
- Select word in Notes editor, Document viewer, or Zettel card → floating toolbar with "Define" icon
- Click → compact popover: top definition + pronunciation + save button
- Uses cached `useDictionaryLookup` — instant for previously looked-up words

### Dictionary Sidebar Panel
- Collapsible right panel (380px, matching app shell spec)
- Persistent during work session
- Lookup history at bottom
- Toggle via sidebar icon or `Cmd+Shift+D`

### Integration Points
- Notes editor (`web/app/(app)/notes/`) — TipTap extension for word selection
- Documents viewer (`web/app/(app)/documents/`) — Selection event listener
- Zettel cards (`web/app/(app)/knowledge/`) — Same selection pattern
- App layout — Global keyboard listener for `Cmd+D`

---

## Spaced Repetition Integration (Phase 2)

- Words with `intent: "learning"` enter existing 3-stage review cycle (1d, 7d, 30d)
- Review card: headword → recall → flip to reveal full entry
- Bloom level tracks 1 (Remember) → 6 (Create)
- Registers as `entity_type: "vocabulary"` in existing `LearningReview` model via `learning_service.py`
- `/dictionary` shows badge: "N words due for review" linking to review flow

---

## File Structure

```
# Backend
apps/alfred/models/vocabulary.py            # VocabularyEntry SQLModel
apps/alfred/services/dictionary_service.py  # Lookup + aggregation + CRUD
apps/alfred/api/dictionary/__init__.py
apps/alfred/api/dictionary/routes.py        # REST endpoints
apps/alfred/migrations/versions/xxx_add_vocabulary_table.py  # Alembic migration

# Frontend
web/app/(app)/dictionary/page.tsx           # Main dictionary page
web/app/(app)/dictionary/layout.tsx         # Dictionary layout
web/components/dictionary/
  ├── dictionary-search-bar.tsx
  ├── dictionary-entry.tsx
  ├── dictionary-entry-skeleton.tsx         # Loading state
  ├── definition-section.tsx
  ├── etymology-section.tsx
  ├── synonyms-section.tsx
  ├── ai-explanation-section.tsx
  ├── encyclopedia-section.tsx
  ├── usage-notes-section.tsx
  ├── personal-annotations.tsx
  ├── save-bar.tsx
  └── vocabulary-collection.tsx
web/features/dictionary/
  ├── queries.ts                            # React Query hooks
  └── mutations.ts                          # Save/update/delete mutations
web/lib/stores/dictionary-store.ts          # Zustand store

# Phase 2 additions
web/components/dictionary/
  ├── dictionary-popover.tsx                # Text selection popover
  ├── dictionary-command.tsx                # Cmd+D modal
  └── dictionary-sidebar.tsx                # Right panel
```

---

## Out of Scope

- Multi-language support beyond English (model supports it, but Phase 1 is English only)
- Offline dictionary data (all lookups require network)
- Audio pronunciation generation (uses external audio URLs from Wiktionary)
- Custom dictionary imports (e.g., importing Anki decks)
- Collaborative vocabulary sharing between users
