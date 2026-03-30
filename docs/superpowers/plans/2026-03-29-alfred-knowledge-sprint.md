# Alfred Knowledge Sprint — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Alfred's content capture, enrichment, and knowledge creation pipeline into a seamless, intelligent system — with smart text cleanup, auto-zettel creation, full-screen reader, Excalidraw AI diagrams, seamless paste UX, and canonical taxonomy.

**Architecture:** Each feature is an independent workstream that can be developed and shipped in isolation. Backend changes use FastAPI + SQLModel + Celery. Frontend uses Next.js 16 / React 19 / TypeScript / Tailwind. LLM calls go through the existing `llm_factory.py` (OpenAI primary). All features follow existing patterns: lazy service init, Pydantic schemas, Zustand stores.

**Tech Stack:** FastAPI, SQLModel, Celery, LangGraph, Next.js 16, React 19, TypeScript, Tailwind CSS 4, shadcn/ui, Tiptap, Excalidraw, OpenAI GPT-5.x

---

## Feature Index

| # | Feature | Files | Est. Tasks |
|---|---------|-------|-----------|
| 1 | Smart Text Cleanup on Capture | 3 backend | 5 |
| 2 | Auto Multi-Zettel Creation on Enrich | 4 backend, 1 frontend | 7 |
| 3 | Seamless Paste UX for Zettel Creation | 2 frontend, 1 backend | 6 |
| 4 | Full-Screen Reader Mode | 3 frontend | 5 |
| 5 | Cleanup Zettel UI from Inbox | 2 frontend | 3 |
| 6 | Smart Taxonomy Canonicalization | 2 backend | 6 |
| 7 | Excalidraw AI Agent | 3 backend, 3 frontend | 8 |

---

## Feature 1: Smart Text Cleanup on Capture

**Problem:** When users do Ctrl+A → Ctrl+S on a webpage, the captured text includes navigation bars, footer links, cookie banners, sidebar menus, and other non-content text. This pollutes summaries and zettels.

**Approach:** Add a content cleaning step in the ingestion pipeline that uses heuristics first (regex patterns for common noise), then an LLM call to extract just the article body. Run this BEFORE storing `cleaned_text`.

### Task 1.1: Content Cleaner Utility

**Files:**
- Create: `apps/alfred/services/doc_storage/_content_cleaner.py`
- Test: `tests/alfred/services/test_content_cleaner.py`

- [ ] **Step 1: Write failing tests for heuristic cleaning**

```python
# tests/alfred/services/test_content_cleaner.py
from alfred.services.doc_storage._content_cleaner import clean_web_content


class TestCleanWebContent:
    def test_removes_cookie_banners(self):
        text = "Accept all cookies\nWe use cookies to improve...\n\nActual article content here about machine learning."
        result = clean_web_content(text)
        assert "cookie" not in result.lower()
        assert "machine learning" in result

    def test_removes_navigation_noise(self):
        text = "Home\nAbout\nContact\nLogin\nSign Up\n\nThe Art of System Design\nBy John Doe\nPublished March 2026\n\nSystem design is..."
        result = clean_web_content(text)
        assert "Home\nAbout\nContact" not in result
        assert "System design is" in result

    def test_removes_footer_links(self):
        text = "Article content about React hooks.\n\n© 2026 TechBlog. All rights reserved.\nPrivacy Policy | Terms of Service | Sitemap"
        result = clean_web_content(text)
        assert "Privacy Policy" not in result
        assert "React hooks" in result

    def test_preserves_short_content(self):
        """Content under 200 chars should not be cleaned (likely a selection, not full page)."""
        text = "A brief note about Stoicism."
        result = clean_web_content(text)
        assert result == text

    def test_removes_subscribe_ctas(self):
        text = "Great article about finance.\n\nSubscribe to our newsletter\nEnter your email\nSign up now\n\nMore great content follows."
        result = clean_web_content(text)
        assert "Subscribe" not in result
        assert "finance" in result

    def test_removes_share_buttons_text(self):
        text = "Deep learning article.\n\nShare on Twitter\nShare on Facebook\nCopy link\n\nThe transformer architecture..."
        result = clean_web_content(text)
        assert "Share on Twitter" not in result
        assert "transformer architecture" in result
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/ashwinrachha/coding/alfred && .venv/bin/python -m pytest tests/alfred/services/test_content_cleaner.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement heuristic content cleaner**

```python
# apps/alfred/services/doc_storage/_content_cleaner.py
"""Heuristic content cleaner for web page captures.

Removes navigation, cookie banners, footers, CTAs, and other noise
that appears when users do Ctrl+A → Ctrl+S on a webpage.
"""

from __future__ import annotations

import re

# Minimum content length to trigger cleaning (short text is likely a deliberate selection)
_MIN_CLEAN_LENGTH = 200

# Patterns that indicate non-content lines (case-insensitive)
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    # Cookie/consent banners
    re.compile(r"^(accept|reject|manage)\s+(all\s+)?cookies", re.IGNORECASE),
    re.compile(r"^we use cookies", re.IGNORECASE),
    re.compile(r"^cookie (policy|preferences|settings)", re.IGNORECASE),
    # Navigation items (short lines that look like menu items)
    re.compile(r"^(home|about|contact|login|sign\s*(up|in)|register|cart|menu|search)$", re.IGNORECASE),
    # Share/social
    re.compile(r"^share\s+(on|to|via)\s+", re.IGNORECASE),
    re.compile(r"^(copy|share)\s+link$", re.IGNORECASE),
    re.compile(r"^(tweet|post|pin)\s+this$", re.IGNORECASE),
    # Subscribe/newsletter CTAs
    re.compile(r"^subscribe\s+(to|now|today)", re.IGNORECASE),
    re.compile(r"^enter your email", re.IGNORECASE),
    re.compile(r"^sign up (for|now|today)", re.IGNORECASE),
    re.compile(r"^get (the|our) newsletter", re.IGNORECASE),
    # Footer patterns
    re.compile(r"^©\s*\d{4}", re.IGNORECASE),
    re.compile(r"^all rights reserved", re.IGNORECASE),
    re.compile(r"^(privacy policy|terms of service|terms & conditions|sitemap|accessibility)", re.IGNORECASE),
    # Ad/promo patterns
    re.compile(r"^(advertisement|sponsored|promoted|ad)\s*$", re.IGNORECASE),
    re.compile(r"^skip to (main |)content$", re.IGNORECASE),
]

# Lines that are likely navigation if they appear in a cluster at the start
_NAV_LINE_MAX_WORDS = 3
_NAV_CLUSTER_THRESHOLD = 4  # N+ consecutive short lines = navigation block


def clean_web_content(text: str) -> str:
    """Remove web noise from captured page text.

    Returns cleaned text with navigation, banners, footers, and CTAs removed.
    Short content (<200 chars) is returned unchanged.
    """
    if not text or len(text) < _MIN_CLEAN_LENGTH:
        return text

    lines = text.split("\n")
    cleaned: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()

        # Skip empty lines (preserve structure, collapse later)
        if not line:
            cleaned.append("")
            i += 1
            continue

        # Check against noise patterns
        if any(pat.match(line) for pat in _NOISE_PATTERNS):
            i += 1
            continue

        # Detect navigation clusters: N+ consecutive short lines at the start
        if not cleaned or all(l == "" for l in cleaned):
            cluster_end = i
            while cluster_end < len(lines) and _is_nav_line(lines[cluster_end].strip()):
                cluster_end += 1
            if cluster_end - i >= _NAV_CLUSTER_THRESHOLD:
                i = cluster_end
                continue

        # Check for footer separator patterns (pipe-separated links)
        if "|" in line and all(len(part.strip().split()) <= 4 for part in line.split("|")):
            i += 1
            continue

        cleaned.append(line)
        i += 1

    # Collapse multiple blank lines into max 2
    result = "\n".join(cleaned)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result


def _is_nav_line(line: str) -> bool:
    """Check if a line looks like a navigation item."""
    if not line:
        return False
    words = line.split()
    return len(words) <= _NAV_LINE_MAX_WORDS and not any(c in line for c in ".!?:;")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/alfred/services/test_content_cleaner.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Wire cleaner into create_page endpoint**

In `apps/alfred/api/documents/routes.py`, after the `looks_like_error_content` check and before creating `DocumentIngest`:

```python
from alfred.services.doc_storage._content_cleaner import clean_web_content

# Inside create_page(), after cleaned_text = (payload.raw_text or "").strip()
if payload.selection_type == "full_page":
    cleaned_text = clean_web_content(cleaned_text)
```

This only cleans full-page captures, not deliberate selections.

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/services/doc_storage/_content_cleaner.py \
        tests/alfred/services/test_content_cleaner.py \
        apps/alfred/api/documents/routes.py
git commit -m "feat(pipeline): add heuristic content cleaner for web captures"
```

---

## Feature 2: Auto Multi-Zettel Creation on Enrich

**Problem:** Currently, enrichment creates exactly 1 zettel per document. Complex articles should decompose into multiple atomic knowledge cards (one per key concept).

**Approach:** After enrichment completes, use an LLM call to decompose the document into multiple zettel candidates. Use the existing `ZettelkastenService.create_card()` for each. Store the decomposition result so it's not re-run.

### Task 2.1: LLM Zettel Decomposition Service

**Files:**
- Create: `apps/alfred/services/zettel_decomposer.py`
- Test: `tests/alfred/services/test_zettel_decomposer.py`

- [ ] **Step 1: Write failing test for decomposition prompt structure**

```python
# tests/alfred/services/test_zettel_decomposer.py
import json
from alfred.services.zettel_decomposer import build_decomposition_prompt, parse_decomposition_response


class TestDecompositionPrompt:
    def test_prompt_includes_document_context(self):
        prompt = build_decomposition_prompt(
            title="System Design Primer",
            summary="A comprehensive guide to system design...",
            cleaned_text="Load balancers distribute traffic... Caching reduces latency...",
            topics={"primary": "system-design", "secondary": ["distributed-systems"]},
        )
        assert "System Design Primer" in prompt
        assert "system-design" in prompt

    def test_prompt_limits_text_length(self):
        long_text = "x " * 10000
        prompt = build_decomposition_prompt(
            title="Test", summary="Test", cleaned_text=long_text, topics={}
        )
        # Should truncate to ~4000 tokens worth
        assert len(prompt) < 20000


class TestParseDecomposition:
    def test_parses_valid_json_array(self):
        response = json.dumps([
            {"title": "Load Balancers", "content": "Distribute traffic across servers", "tags": ["infra"]},
            {"title": "Caching Strategies", "content": "Reduce latency with caching", "tags": ["performance"]},
        ])
        cards = parse_decomposition_response(response)
        assert len(cards) == 2
        assert cards[0]["title"] == "Load Balancers"

    def test_handles_markdown_code_fence(self):
        response = '```json\n[{"title": "Test", "content": "Content", "tags": []}]\n```'
        cards = parse_decomposition_response(response)
        assert len(cards) == 1

    def test_returns_empty_on_invalid_json(self):
        cards = parse_decomposition_response("not json at all")
        assert cards == []

    def test_caps_at_max_cards(self):
        many_cards = [{"title": f"Card {i}", "content": f"Content {i}", "tags": []} for i in range(20)]
        response = json.dumps(many_cards)
        cards = parse_decomposition_response(response)
        assert len(cards) <= 10  # Max 10 cards per document
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/alfred/services/test_zettel_decomposer.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Implement zettel decomposer**

```python
# apps/alfred/services/zettel_decomposer.py
"""Decompose a document into multiple atomic zettel cards using LLM."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

MAX_CARDS_PER_DOCUMENT = 10
MAX_TEXT_CHARS = 8000  # ~2000 tokens


def build_decomposition_prompt(
    *,
    title: str,
    summary: str | None,
    cleaned_text: str,
    topics: dict[str, Any] | None,
) -> str:
    """Build the LLM prompt for zettel decomposition."""
    truncated_text = cleaned_text[:MAX_TEXT_CHARS] if cleaned_text else ""
    topic_str = ""
    if topics:
        primary = topics.get("primary", "")
        secondary = topics.get("secondary", [])
        topic_str = f"Primary topic: {primary}. Tags: {', '.join(secondary[:5])}."

    return f"""Decompose this document into 2-{MAX_CARDS_PER_DOCUMENT} atomic knowledge cards (Zettelkasten method).

Each card should capture ONE distinct concept, fact, or insight. Cards should be:
- Atomic: one idea per card
- Self-contained: understandable without the source document
- Connected: use tags to show relationships

Document Title: {title}
{f'Summary: {summary}' if summary else ''}
{topic_str}

Document Text (truncated):
{truncated_text}

Return a JSON array of cards. Each card has:
- "title": concise title (max 80 chars)
- "content": 1-3 sentence explanation
- "tags": array of 1-3 lowercase tags

Return ONLY the JSON array, no other text."""


def parse_decomposition_response(response: str) -> list[dict[str, Any]]:
    """Parse LLM response into list of card dicts."""
    # Strip markdown code fences
    cleaned = re.sub(r"```json\s*", "", response)
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()

    try:
        cards = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Failed to parse decomposition response as JSON")
        return []

    if not isinstance(cards, list):
        return []

    # Validate and cap
    valid: list[dict[str, Any]] = []
    for card in cards[:MAX_CARDS_PER_DOCUMENT]:
        if isinstance(card, dict) and "title" in card and "content" in card:
            valid.append({
                "title": str(card["title"])[:255],
                "content": str(card["content"]),
                "tags": [str(t) for t in card.get("tags", [])][:5],
            })
    return valid
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/alfred/services/test_zettel_decomposer.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Replace single-zettel creation in enrichment task**

Modify `apps/alfred/tasks/document_enrichment.py` to call the decomposer instead of creating a single zettel. The function `_create_zettel_from_enrichment()` should:

1. Call `build_decomposition_prompt()` with document data
2. Send to LLM via `llm_factory`
3. Parse response with `parse_decomposition_response()`
4. Create each card via `ZettelkastenService.create_card()`
5. Fall back to single-card creation if LLM fails

Key change: Replace the existing `_create_zettel_from_enrichment()` body with decomposition logic. Keep the duplicate check (skip if zettels already exist for this document_id).

- [ ] **Step 6: Add frontend indicator for auto-created zettels**

In `web/app/(app)/inbox/_components/inbox-detail.tsx`, the "Knowledge Cards" section already shows zettels linked to the document. Update the count badge to show how many were auto-created vs manual.

- [ ] **Step 7: Commit**

```bash
git add apps/alfred/services/zettel_decomposer.py \
        tests/alfred/services/test_zettel_decomposer.py \
        apps/alfred/tasks/document_enrichment.py \
        web/app/(app)/inbox/_components/inbox-detail.tsx
git commit -m "feat(zettels): auto-decompose documents into multiple atomic cards on enrich"
```

---

## Feature 3: Seamless Paste UX for Zettel Creation

**Problem:** Users want to paste large text chunks when creating a zettel. The current dialog has a small textarea. Need a responsive, reflexive UI that handles large pastes gracefully — auto-detecting title, expanding textarea, showing token count.

**Approach:** Redesign the create-zettel dialog to have a "paste mode" that activates on large paste (>100 chars). Auto-extracts title from first line, shows live token count, auto-generates tags via LLM.

### Task 3.1: Enhanced Paste-Aware Zettel Dialog

**Files:**
- Modify: `web/app/(app)/knowledge/_components/create-zettel-dialog.tsx`
- Create: `web/lib/hooks/use-paste-detection.ts`

- [ ] **Step 1: Create paste detection hook**

```typescript
// web/lib/hooks/use-paste-detection.ts
import { useCallback, useState } from "react";

const PASTE_THRESHOLD = 100; // chars

export function usePasteDetection() {
  const [isPasteMode, setIsPasteMode] = useState(false);
  const [pastedText, setPastedText] = useState("");
  const [tokenEstimate, setTokenEstimate] = useState(0);

  const handlePaste = useCallback((e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const text = e.clipboardData.getData("text/plain");
    if (text.length > PASTE_THRESHOLD) {
      setIsPasteMode(true);
      setPastedText(text);
      setTokenEstimate(Math.ceil(text.split(/\s+/).length * 1.3)); // rough token estimate
    }
  }, []);

  const extractTitle = useCallback((text: string): string => {
    // First non-empty line, truncated to 120 chars
    const firstLine = text.split("\n").find((l) => l.trim().length > 0)?.trim() || "";
    return firstLine.length > 120 ? firstLine.slice(0, 117) + "..." : firstLine;
  }, []);

  const reset = useCallback(() => {
    setIsPasteMode(false);
    setPastedText("");
    setTokenEstimate(0);
  }, []);

  return { isPasteMode, pastedText, tokenEstimate, handlePaste, extractTitle, reset };
}
```

- [ ] **Step 2: Redesign create-zettel dialog for paste mode**

Key UI changes to `create-zettel-dialog.tsx`:
- Textarea expands to full height on large paste (min-h-[300px])
- Auto-fills title from first line of pasted text
- Shows token count badge: `{tokenEstimate} tokens`
- "Auto-tag" button that calls `/api/zettels/cards/generate` to suggest tags
- Responsive layout: single column on mobile, side-by-side fields on desktop

- [ ] **Step 3: Add backend endpoint for tag suggestion**

Create `POST /api/zettels/suggest-tags` endpoint:
```python
@router.post("/suggest-tags")
def suggest_tags(payload: TagSuggestionRequest) -> TagSuggestionResponse:
    """Given text content, suggest relevant tags using LLM."""
```

- [ ] **Step 4: Wire auto-tag button to suggestion endpoint**

- [ ] **Step 5: Add keyboard shortcut: Cmd+Enter to submit**

- [ ] **Step 6: Commit**

```bash
git add web/lib/hooks/use-paste-detection.ts \
        web/app/(app)/knowledge/_components/create-zettel-dialog.tsx \
        apps/alfred/api/zettels/routes.py
git commit -m "feat(zettels): seamless paste UX with auto-title, token count, auto-tag"
```

---

## Feature 4: Full-Screen Reader Mode

**Problem:** The document viewer is an editor, not a reader. Users want a zen-mode reading experience for captured articles.

**Approach:** Add a full-screen reader overlay component with clean typography, scroll progress, and quick-actions (create zettel from selection, highlight).

### Task 4.1: Reader Mode Component

**Files:**
- Create: `web/app/(app)/inbox/_components/reader-mode.tsx`
- Modify: `web/app/(app)/inbox/_components/inbox-detail.tsx` (add "Read" button)

- [ ] **Step 1: Create reader mode component**

Full-screen overlay with:
- Clean reading typography (Inter 18px, 1.8 line-height, max-width 680px)
- Scroll progress bar at top
- Close button (Escape key)
- Title + source URL header
- Summary section (collapsible)
- Full cleaned text body (rendered as markdown)
- Floating action bar: Close, Create Zettel, Copy

- [ ] **Step 2: Add "Read" button to inbox detail panel**

- [ ] **Step 3: Format content for reader**

Clean the `cleaned_text` for reading: normalize whitespace, convert markdown headings, add paragraph breaks.

- [ ] **Step 4: Add keyboard navigation**

Escape to close, Space to scroll, Z to create zettel from selection.

- [ ] **Step 5: Commit**

```bash
git add web/app/(app)/inbox/_components/reader-mode.tsx \
        web/app/(app)/inbox/_components/inbox-detail.tsx
git commit -m "feat(inbox): add full-screen reader mode for captured articles"
```

---

## Feature 5: Cleanup Zettel UI from Inbox

**Problem:** The inbox detail panel shows zettel creation inline. Since zettels are now auto-created on enrich, the manual creation UI in inbox should be simplified — show existing cards, but remove the creation form. Keep "Create Zettel" as a quick action button that opens the knowledge dialog.

### Task 5.1: Simplify Inbox Zettel Section

**Files:**
- Modify: `web/app/(app)/inbox/_components/inbox-detail.tsx`

- [ ] **Step 1: Replace inline zettel form with card list + quick action**

Remove the inline form fields. Show:
- List of auto-created zettels (from enrichment)
- "Create More" button → opens create-zettel-dialog pre-filled with document data
- Count badge showing total zettels linked

- [ ] **Step 2: Test visual regression**

- [ ] **Step 3: Commit**

```bash
git add web/app/(app)/inbox/_components/inbox-detail.tsx
git commit -m "refactor(inbox): simplify zettel section, rely on auto-creation"
```

---

## Feature 6: Smart Taxonomy Canonicalization

**Problem:** The taxonomy system creates new nodes freely, leading to duplicates and inconsistency (e.g., "ai-engineering" vs "artificial-intelligence" vs "machine-learning" all as top-level domains). Need smart matching to canonicalize into existing taxonomy before creating new nodes.

**Approach:** Before creating a new taxonomy node, search existing nodes for semantic similarity. Use fuzzy matching + LLM to decide if the new topic maps to an existing node.

### Task 6.1: Taxonomy Canonicalizer

**Files:**
- Create: `apps/alfred/services/taxonomy_canonicalizer.py`
- Test: `tests/alfred/services/test_taxonomy_canonicalizer.py`
- Modify: `apps/alfred/services/taxonomy_service.py` (wire in canonicalizer)

- [ ] **Step 1: Write failing tests for canonical matching**

```python
# tests/alfred/services/test_taxonomy_canonicalizer.py
from alfred.services.taxonomy_canonicalizer import find_canonical_match


class TestCanonicalMatch:
    def test_exact_match(self):
        existing = ["ai-engineering", "finance", "philosophy"]
        match = find_canonical_match("ai-engineering", existing)
        assert match == "ai-engineering"

    def test_fuzzy_match_hyphen_variants(self):
        existing = ["ai-engineering", "system-design"]
        match = find_canonical_match("ai_engineering", existing)
        assert match == "ai-engineering"

    def test_fuzzy_match_synonyms(self):
        existing = ["ai-engineering", "system-design"]
        match = find_canonical_match("artificial-intelligence", existing)
        assert match == "ai-engineering"

    def test_no_match_returns_none(self):
        existing = ["ai-engineering", "system-design"]
        match = find_canonical_match("cooking-recipes", existing)
        assert match is None

    def test_plural_normalization(self):
        existing = ["investment"]
        match = find_canonical_match("investments", existing)
        assert match == "investment"
```

- [ ] **Step 2: Implement canonicalizer with synonym map + fuzzy matching**

```python
# apps/alfred/services/taxonomy_canonicalizer.py
"""Canonicalize taxonomy slugs to prevent duplicates."""

from __future__ import annotations

from difflib import SequenceMatcher

# Known synonym groups → canonical slug
_SYNONYM_MAP: dict[str, str] = {
    "artificial-intelligence": "ai-engineering",
    "ai": "ai-engineering",
    "machine-learning": "ai-engineering",
    "ml": "ai-engineering",
    "deep-learning": "ai-engineering",
    "distributed-systems": "system-design",
    "microservices": "system-design",
    "investing": "finance",
    "investments": "finance",
    "stocks": "finance",
    "crypto": "finance",
    "stoicism": "philosophy",
    "ethics": "philosophy",
    "existentialism": "philosophy",
    "geopolitics": "politics",
    "international-relations": "politics",
}

_FUZZY_THRESHOLD = 0.8


def find_canonical_match(slug: str, existing_slugs: list[str]) -> str | None:
    """Find canonical match for a slug among existing taxonomy nodes.

    Priority: exact match > synonym map > fuzzy match > None.
    """
    normalized = slug.lower().replace("_", "-").strip()

    # 1. Exact match
    if normalized in existing_slugs:
        return normalized

    # 2. Synonym map
    if normalized in _SYNONYM_MAP:
        canonical = _SYNONYM_MAP[normalized]
        if canonical in existing_slugs:
            return canonical

    # 3. Plural/singular normalization
    if normalized.endswith("s") and normalized[:-1] in existing_slugs:
        return normalized[:-1]
    if f"{normalized}s" in existing_slugs:
        return f"{normalized}s"

    # 4. Fuzzy matching (SequenceMatcher)
    best_match = None
    best_ratio = 0.0
    for existing in existing_slugs:
        ratio = SequenceMatcher(None, normalized, existing).ratio()
        if ratio > best_ratio and ratio >= _FUZZY_THRESHOLD:
            best_ratio = ratio
            best_match = existing

    return best_match
```

- [ ] **Step 3: Run tests**

- [ ] **Step 4: Wire canonicalizer into TaxonomyService._ensure_node()**

Before creating a new node, check `find_canonical_match()` against existing slugs at the same level. If match found, return the existing node instead of creating a new one.

- [ ] **Step 5: Add LLM fallback for ambiguous cases**

When fuzzy match score is between 0.6-0.8 (ambiguous), use a quick LLM call: "Are these the same topic? '{new}' vs '{existing}'"

- [ ] **Step 6: Commit**

```bash
git add apps/alfred/services/taxonomy_canonicalizer.py \
        tests/alfred/services/test_taxonomy_canonicalizer.py \
        apps/alfred/services/taxonomy_service.py
git commit -m "feat(taxonomy): smart canonicalization with synonyms, fuzzy matching, LLM fallback"
```

---

## Feature 7: Excalidraw AI Agent

**Problem:** The canvas AI panel can only insert text. Users want an AI that can automatically draw diagrams — architecture diagrams, flowcharts, mind maps, concept diagrams — directly onto the Excalidraw canvas.

**Approach:** Build an LLM-to-Excalidraw translator. The AI agent receives a natural language prompt, generates Excalidraw element JSON (rectangles, arrows, text), and the frontend inserts them onto the canvas. Use a structured output format that maps to Excalidraw's element schema.

### Task 7.1: Excalidraw Element Schema & Generator

**Files:**
- Create: `apps/alfred/services/excalidraw_agent.py`
- Test: `tests/alfred/services/test_excalidraw_agent.py`

- [ ] **Step 1: Define Excalidraw element generation prompt**

The LLM must output valid Excalidraw element JSON. Define the output schema as a Pydantic model that maps to Excalidraw's `ExcalidrawElement` interface.

Key element types to support:
- `rectangle` (boxes for concepts/services)
- `ellipse` (for actors/decisions)
- `diamond` (for decisions)
- `arrow` (connections with labels)
- `text` (labels)
- `line` (dividers)

- [ ] **Step 2: Implement prompt builder for diagram generation**

```python
# apps/alfred/services/excalidraw_agent.py
"""Generate Excalidraw diagram elements from natural language."""

def build_diagram_prompt(user_request: str, canvas_context: str | None = None) -> str:
    """Build LLM prompt that generates Excalidraw elements JSON."""
    ...
```

The prompt must include the Excalidraw element schema so the LLM outputs valid JSON.

- [ ] **Step 3: Write parser for LLM → Excalidraw elements**

Parse the LLM response into a list of Excalidraw-compatible element dicts. Validate coordinates, IDs, bindings.

- [ ] **Step 4: Create API endpoint**

`POST /api/canvas/generate-diagram`:
```python
class DiagramRequest(BaseModel):
    prompt: str
    canvas_context: str | None = None  # existing canvas elements for context

class DiagramResponse(BaseModel):
    elements: list[dict]  # Excalidraw element JSON
    app_state: dict | None = None  # optional viewport adjustments
```

- [ ] **Step 5: Wire frontend canvas AI panel to diagram endpoint**

Modify `web/app/(app)/canvas/_components/canvas-ai-panel.tsx`:
- Detect "diagram-like" requests (keywords: draw, diagram, flowchart, architecture, mind map)
- Call `/api/canvas/generate-diagram` instead of text stream
- Insert returned elements directly onto Excalidraw canvas via `excalidrawAPI.updateScene()`

- [ ] **Step 6: Add "Insert as Diagram" button for text responses**

Even for text responses, add a button that converts structured text into a simple diagram layout (bulleted list → mind map, numbered steps → flowchart).

- [ ] **Step 7: Auto-layout algorithm**

The LLM won't perfectly position elements. Add a simple grid-based auto-layout:
- Place boxes in a grid (columns of 3-4)
- Route arrows between connected elements
- Center the viewport on the new elements

- [ ] **Step 8: Commit**

```bash
git add apps/alfred/services/excalidraw_agent.py \
        tests/alfred/services/test_excalidraw_agent.py \
        apps/alfred/api/canvas/ \
        web/app/(app)/canvas/_components/canvas-ai-panel.tsx
git commit -m "feat(canvas): AI agent generates Excalidraw diagrams from natural language"
```

---

## Execution Order (Recommended)

Start with the quick wins that improve daily workflow, then tackle the larger features:

1. **Feature 1** (Text Cleanup) — 30 min, immediate quality improvement
2. **Feature 5** (Cleanup Inbox Zettel) — 15 min, UI simplification
3. **Feature 6** (Smart Taxonomy) — 1 hr, prevents data mess
4. **Feature 2** (Auto Multi-Zettel) — 1.5 hr, core knowledge flow
5. **Feature 3** (Paste UX) — 1 hr, UX polish
6. **Feature 4** (Reader Mode) — 1 hr, reading experience
7. **Feature 7** (Excalidraw AI) — 2+ hr, largest feature

---

## Dependencies

- Features 1-6 are independent (can be done in parallel)
- Feature 2 benefits from Feature 6 (better taxonomy → better auto-tags on zettels)
- Feature 7 is fully independent
- All features require the Celery broker (RabbitMQ/Redis) for async tasks
