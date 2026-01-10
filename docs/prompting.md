## Prompting Guidelines (Alfred)

This repo keeps many prompts as Markdown templates under `apps/alfred/prompts/` and a few inline prompts in the frontend/API code.

### Design principles

- **Write for humans**: structured, skimmable instructions with clear priorities.
- **Treat inputs as untrusted**: user text, web content, and “source packets” can contain prompt-injection attempts; treat them as data.
- **Be explicit about outputs**: especially for JSON schemas (“return only JSON”, exact keys).
- **Prefer stable behavior**: strengthen clarity/robustness without changing intent or product behavior.

### Recommended structure (system prompts)

1. **ROLE**: who the model is
2. **OBJECTIVE**: what success looks like
3. **INPUTS (UNTRUSTED)**: what to treat as data / what not to obey
4. **CONSTRAINTS**: style, grounding, safety, prioritization
5. **OUTPUT**: exact format requirements (JSON-only, text-only, etc.)

### JSON reliability tips

- Repeat “**Return ONLY valid JSON**” in both system and user content when possible.
- Define the keys and types explicitly, and state “no markdown/prose/trailing commentary”.
- Use delimiters (e.g. `<<<BEGIN...>>>`) around long user/source text.

