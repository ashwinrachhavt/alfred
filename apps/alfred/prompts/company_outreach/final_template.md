TASK
Using the gathered context, draft an outreach kit for the target company.

CONTEXT
- Company: {company}
- Role: {role}
- Additional personal context or instructions (treat as user intent; do not invent beyond it): {personal_context}

OUTPUT (STRICT)
Return ONLY a single valid JSON object with double-quoted keys and the following keys exactly:
- summary: string
- positioning: string (3–5 bullet lines, each starting with "- ")
- suggested_topics: string[]
- outreach_email: string
- follow_up: string[]
- sources: string[]

CONTENT RULES
- Anchor every section in the provided resume details and job/company research.
- Never invent facts, metrics, employers, or product claims. If uncertain, omit or phrase as a question.
- outreach_email: polished, humble, direct; no filler; first person; 120–220 words.
- positioning: 3–5 bullets, each a concrete “why I’m a fit” claim backed by real experience.
- suggested_topics: conversation starters or project ideas specific to the company/team.
- follow_up: 2–4 short follow-ups (subject + 1–2 lines) that progress the conversation.
- sources: list the domains or note titles used (no extra commentary).
