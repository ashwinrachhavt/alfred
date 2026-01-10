TASK
Generate a practice quiz.

CONTEXT (UNTRUSTED DATA)
- Company: {company}
- Role: {role}
- Number of questions: {num_questions}

PREP DOCUMENT (DATA)
{prep_doc}

REQUIREMENTS
- Mix: system design / coding / fundamentals / role-specific applied questions.
- Each question is crisp and unambiguous (no vague “talk about” prompts).
- Answers are optional; if included, keep them short and correct.
- Avoid questions that require private/internal company knowledge.

OUTPUT (STRICT)
Return ONLY valid JSON matching the requested schema.
