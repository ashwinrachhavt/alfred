Title: {title}
URL: {url}

Text:
{text}

Return a single JSON object with these keys:
- topic_category: string, short descriptive label (e.g., "Machine Learning / RAG", "Career / Interview")
- summary: 5–10 sentences summarizing the document in plain language
- highlights: array of 5–12 objects: {"bullet": string, "importance": "low"|"medium"|"high", "section_hint": string|null}
- insights: array of 3–8 objects: {"statement": string, "type": "concept"|"pattern"|"anti_pattern"|"action_item"|"quote", "est_novelty": "known"|"somewhat_new"|"mind_blown"}
- domain_summary: 3–5 sentences explaining how this fits into the broader field or mental model landscape
- tags: 5–10 lowercase snake_case strings (e.g., ["rag", "langgraph", "system_design"])
- topic_graph: object {"primary_node": string|null, "related_nodes": [string,...]}

Constraints:
- Respond with valid JSON only (no markdown). Use double quotes for all keys/strings.
- Ensure arrays are not empty; if unsure, provide best-effort values.
- Keep strings concise: highlights <= 160 chars each; insights <= 200 chars each.

