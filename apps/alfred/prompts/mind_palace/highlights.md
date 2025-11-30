Produce a JSON object with key "highlights": a list of 5–12 items.
Each item: {"bullet": string, "importance": "low"|"medium"|"high", "section_hint": string|null}

Use the page capture and the provided summary for context.

Title: {title}
URL: {url}
Summary: {summary}
Text:
{text}

Constraints:
- Return valid JSON only.
- Keep bullets <= 160 chars. Prefer facts/definitions/critical points.

