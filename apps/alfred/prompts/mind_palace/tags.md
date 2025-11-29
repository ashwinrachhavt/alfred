Produce a JSON object with keys:
- tags: 5–10 lowercase snake_case strings summarizing the core topics.
- topic_graph: {"primary_node": string|null, "related_nodes": [string,...]}

Use the summary and text to capture the core concepts and relations.

Title: {title}
URL: {url}
Summary: {summary}
Text:
{text}

Constraints:
- Return valid JSON only.
- Prefer domain terms (e.g., rag, system_design, langgraph, dspy, agents).

