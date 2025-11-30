Produce a JSON object with key "insights": a list of 3–8 items.
Each item: {"statement": string, "type": "concept"|"pattern"|"anti_pattern"|"action_item"|"quote", "est_novelty": "known"|"somewhat_new"|"mind_blown"}

Use the page capture and the provided summary for context. Focus on deeper lessons useful months later.

Title: {title}
URL: {url}
Summary: {summary}
Text:
{text}

Constraints:
- Return valid JSON only.
- Keep statements <= 200 chars.

