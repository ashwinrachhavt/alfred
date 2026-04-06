# Alfred — Knowledge Factory

## Project Overview
Alfred is a knowledge factory for ambitious generalists. It ingests, decomposes, connects, and helps users capitalize on what they know.

### Architecture
- **Backend:** FastAPI + Celery + Redis + PostgreSQL (SQLModel/Alembic)
- **Frontend:** Next.js 16 / React 19 / TypeScript / Tailwind CSS 4 / shadcn/ui
- **Vector DB:** Qdrant Cloud
- **LLMs:** OpenAI (primary), Ollama, Anthropic — provider-agnostic via llm_factory.py
- **Auth:** Clerk (Google + Notion OAuth)

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
- **Fonts:** Source Serif 4 (display), DM Sans (body/UI), Berkeley Mono / JetBrains Mono (data/meta/system)
- **Accent:** #E8590C (deep orange) — the ONLY color used for emphasis
- **Dark base:** #0F0E0D — warm charcoal, NOT cool blue-black
- **Light base:** #FAF8F5 — warm off-white, NOT pure white
- **Neutrals:** Warm grays (stone, not steel)
- **Labels/nav:** DM Sans 500 weight, uppercase, small size, tracked
- **System layer:** Berkeley Mono for timestamps, metadata, shortcuts, section headers
- **Border radius:** sm(4px) md(8px) lg(12px) — sharp, not bubbly

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
