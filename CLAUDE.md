# Alfred — Knowledge Factory

## Project Overview
Alfred is a knowledge factory for ambitious generalists. It ingests, decomposes, connects, and helps users capitalize on what they know.

### Architecture
- **Backend:** FastAPI + Celery + Redis + PostgreSQL (SQLModel/Alembic)
- **Frontend:** Next.js 16 / React 19 / TypeScript / Tailwind CSS 4 / shadcn/ui
- **Vector DB:** Qdrant Cloud
- **LLMs:** OpenAI (primary), Ollama, Anthropic — provider-agnostic via llm_factory.py
- **Auth:** Clerk (currently disabled, keys need refresh)

### Key Directories
- `web/` — Next.js frontend
- `app/` — FastAPI backend
- `web/components/ui/` — shadcn/ui component library
- `web/features/` — Data layer (queries, mutations per feature)
- `web/lib/stores/` — Zustand state management

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

### Quick Reference
- **Fonts:** Instrument Serif (display), DM Sans (body), JetBrains Mono (labels/nav/meta), Geist (data)
- **Accent:** #E8590C (deep orange) — the ONLY color used for emphasis
- **Dark base:** #0F0E0D — warm charcoal, NOT cool blue-black
- **Light base:** #FAF8F5 — warm off-white, NOT pure white
- **Neutrals:** Warm grays (stone, not steel)
- **Labels/nav:** JetBrains Mono, uppercase, small size, tracked
- **Border radius:** sm(4px) md(8px) lg(12px) — sharp, not bubbly
