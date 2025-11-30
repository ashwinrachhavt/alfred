You will read a page capture (title, url, text) and produce a JSON object with:
- topic_category: short, descriptive label for the domain/topic.
- summary: 5–10 sentences, plain language, faithful and concise.

Input:
Title: {title}
URL: {url}
Text:
{text}

Constraints:
- Return valid JSON only: {"topic_category": string, "summary": string}
- No extra prose or markdown.

