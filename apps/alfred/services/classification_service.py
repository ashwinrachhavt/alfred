from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, Field

from alfred.services.llm_service import LLMService

DEFAULT_TAXONOMY_CONTEXT = """
### Taxonomy (domain → subdomains → microtopics)

Domains:
- AI
- SYSTEM_DESIGN
- FINANCE
- STARTUPS
- INVESTING
- WRITING
- POLITICS
- MOVIES_POP_CULTURE
- PHILOSOPHY
- PRODUCTIVITY_CAREER

Examples:
- AI → LLMS → ["SELF_ATTENTION","KV_CACHE","QUANTIZATION"]
- SYSTEM_DESIGN → DATABASES → ["LSM_TREES","MVCC","SHARDING"]
- FINANCE → MARKETS → ["EQUITIES","BONDS","YIELD_CURVE"]
""".strip()


class TopicTitle(BaseModel):
    title: str
    confidence: float = Field(ge=0.0, le=1.0)


class ClassificationResult(BaseModel):
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    microtopics: Optional[List[str]] = None
    topic: TopicTitle


PROMPT_TEMPLATE = """
You are a knowledge-classification assistant.
Your job: given a piece of text (document, article, blog post, paper, etc.), classify it into a four-level taxonomy:
  1. Domain
  2. Subdomain
  3. Microtopic(s) (one or more)
  4. Topic — the title (or best-guess title) for this piece

You must respond with valid JSON only, following exactly the schema described.

### JSON Schema
{{
  "domain": string | null,
  "subdomain": string | null,
  "microtopics": string[] | null,
  "topic": {{
     "title": string,
     "confidence": number
  }}
}}

### Instructions / Heuristics
- Domain, Subdomain, and microtopics must match (case-insensitively) entries in the canonical taxonomy provided below.
- If the document covers multiple microtopics, list them all in microtopics.
- If the document belongs to multiple domains/subdomains, choose the primary domain/subdomain.
- The "topic.title" should be a concise human-style title summarizing the core content.
- "confidence" reflects your confidence that the title fits the document (0.0–1.0).

### Taxonomy (domain → subdomains → microtopics)
{TAXONOMY}

---

### Input
<<<BEGIN_DOCUMENT>>>
{TEXT}
<<<END_DOCUMENT>>>

### Output
Return only the JSON.
""".strip()


@dataclass
class ClassificationService:
    model: Optional[str] = None  # use LLMService default if None

    def classify(
        self, *, text: str, taxonomy_context: Optional[str] = None
    ) -> ClassificationResult:
        taxonomy = (taxonomy_context or DEFAULT_TAXONOMY_CONTEXT).strip()
        prompt = PROMPT_TEMPLATE.replace("{TAXONOMY}", taxonomy).replace("{TEXT}", text[:8000])
        ls = LLMService()
        result = ls.structured(
            [
                {"role": "system", "content": "Return valid JSON only. Follow the schema."},
                {"role": "user", "content": prompt},
            ],
            schema=ClassificationResult,
            model=self.model,
        )
        return result
