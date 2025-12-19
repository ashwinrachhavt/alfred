from __future__ import annotations

import hashlib
import importlib.util
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from alfred.prompts import load_prompt
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)

# Optional dependency: langextract
_LANGEXTRACT_AVAILABLE = importlib.util.find_spec("langextract") is not None
if _LANGEXTRACT_AVAILABLE:  # pragma: no cover - environment dependent
    import langextract as lx  # type: ignore
else:  # pragma: no cover - environment dependent
    lx = None  # type: ignore


@dataclass
class ExtractionService:
    """
    Placeholder wrapper for a structured extraction service (e.g., LangExtract).

    In production, wire this to your actual extractor. For now, it returns a
    minimal shape suitable for graph upserts (entities/relations/topics).
    """

    api_key: Optional[str] = None

    def extract_graph(self, *, text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """
        Use LangExtract (if available) with OpenAI provider to extract entities,
        relations, and topics. Falls back to OpenAI structured outputs.
        """
        text = (text or "").strip()
        out: Dict[str, Any] = {"entities": [], "relations": [], "topics": []}
        if not text:
            return out

        # LangExtract graph extraction (OpenAI provider), if available
        try:
            if _LANGEXTRACT_AVAILABLE and lx is not None:
                from dataclasses import dataclass as _dc_dataclass

                @_dc_dataclass
                class Entity:
                    name: Optional[str] = None
                    type: Optional[str] = None

                @_dc_dataclass
                class Relation:
                    source: Optional[str] = field(default=None, metadata={"alias": "from"})
                    target: Optional[str] = field(default=None, metadata={"alias": "to"})
                    type: Optional[str] = None

                @_dc_dataclass
                class GraphExtraction:
                    entities: List[Entity] = field(default_factory=list)
                    relations: List[Relation] = field(default_factory=list)
                    topics: List[str] = field(default_factory=list)

                instr = (
                    "Extract entities (name,type) and relations (from,to,type). "
                    "Return JSON that matches the schema exactly. Use snake_case for types and topics."
                )
                result = lx.extract(  # type: ignore[attr-defined]
                    text_or_documents=text,
                    prompt_description=instr,
                    examples=[],
                    target_schemas=[GraphExtraction],
                    model_id="openai:gpt-4o-mini",
                    max_workers=0,
                    extraction_passes=1,
                )
                entities_list: List[Dict[str, Any]] = []
                relations_list: List[Dict[str, Any]] = []
                topics_list: List[str] = []
                for ex in getattr(result, "extractions", []) or []:
                    attrs = getattr(ex, "attributes", {}) or {}
                    for e in attrs.get("entities", []) or []:
                        n = e.get("name") or e.get("Name")
                        t = e.get("type") or e.get("Type")
                        if n:
                            entities_list.append({"name": n, "type": t})
                    for r in attrs.get("relations", []) or []:
                        f = r.get("from") or r.get("source")
                        t = r.get("to") or r.get("target")
                        rt = r.get("type") or "RELATED_TO"
                        if f and t:
                            relations_list.append({"from": f, "to": t, "type": rt})
                    topics_list.extend(
                        [str(x) for x in attrs.get("topics", []) if isinstance(x, str)]
                    )
                if entities_list or relations_list or topics_list:
                    out["entities"] = entities_list
                    out["relations"] = relations_list
                    out["topics"] = list(dict.fromkeys(topics_list))
                    return out
        except Exception as exc:
            logger.debug("LangExtract graph failed: %s", exc)

        # Fallback: OpenAI structured outputs
        class EntityModel(BaseModel):
            name: str
            type: Optional[str] = None

        class RelationModel(BaseModel):
            from_name: str = Field(alias="from")
            to_name: str = Field(alias="to")
            type: Optional[str] = None

        class GraphOut(BaseModel):
            entities: List[EntityModel] = Field(default_factory=list)
            relations: List[RelationModel] = Field(default_factory=list)
            topics: List[str] = Field(default_factory=list)

        ls = LLMService()
        prompt = (
            "Extract entities (name,type) and relations (from,to,type).\n"
            "Return compact JSON: {entities:[], relations:[], topics:[]} with snake_case.\n\n"
            + text[:5000]
        )
        result = ls.structured(
            [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            schema=GraphOut,
        )
        ents = [e.model_dump() for e in result.entities]
        rels = [
            {"from": r.from_name, "to": r.to_name, "type": r.type or "RELATED_TO"}
            for r in result.relations
        ]
        return {"entities": ents, "relations": rels, "topics": result.topics}

    # ------------------------------------------------------------
    # Full enrichment (lang, summary, topics, tags, entities, embedding)
    # ------------------------------------------------------------
    def extract_all(
        self,
        *,
        cleaned_text: str,
        raw_markdown: Optional[str] = None,
        metadata: Dict[str, Any] | None = None,
        include_embedding: bool = True,
    ) -> Dict[str, Any]:
        """
        Use OpenAI models to populate a broad enrichment payload:
        - lang (ISO 639-1 where possible)
        - summary: {short, long, bullets, key_points}
        - topics: {primary, secondary}
        - tags: [str]
        - entities: [{name, type}]
        - embedding: [float]
        Also includes convenience fields: tokens, hash, cleaned_text, raw_markdown.
        """
        # env loaded via unified settings

        text = (raw_markdown or cleaned_text or "").strip()
        # Cap text to keep token usage reasonable
        text = text[:8000]

        # ---------- helpers ----------
        def _token_count(s: str) -> int:
            try:
                return len((s or "").split())
            except Exception:
                return 0

        def _sha256_hex(s: str) -> str:
            return hashlib.sha256((s or "").encode("utf-8")).hexdigest()

        # ---------- 1) Combined structured extraction (LangExtract preferred) ----------
        class EnrichOut(BaseModel):
            lang: Optional[str] = None
            summary_short: Optional[str] = None
            summary_long: Optional[str] = None
            bullets: List[str] = Field(default_factory=list)
            key_points: List[str] = Field(default_factory=list)
            topics_primary: Optional[str] = None
            topics_secondary: List[str] = Field(default_factory=list)
            tags: List[str] = Field(default_factory=list)

        out: EnrichOut
        try:
            if _LANGEXTRACT_AVAILABLE and lx is not None:

                @dataclass
                class DocEnrichment:
                    lang: Optional[str] = None
                    summary_short: Optional[str] = None
                    summary_long: Optional[str] = None
                    bullets: List[str] = field(default_factory=list)
                    key_points: List[str] = field(default_factory=list)
                    topics_primary: Optional[str] = None
                    topics_secondary: List[str] = field(default_factory=list)
                    tags: List[str] = field(default_factory=list)

                instr = (
                    "Detect `lang` (ISO 639-1). "
                    "Write a richer summary_short (3-6 sentences in a single cohesive paragraph) and "
                    "a more detailed summary_long (2-4 paragraphs, each with 5-8 sentences). "
                    "Also include bullets (2-6) and key_points (2-6). "
                    "Return topics_primary and topics_secondary in snake_case, and 2-10 snake_case tags."
                )
                result = lx.extract(  # type: ignore[attr-defined]
                    text_or_documents=text,
                    prompt_description=instr,
                    examples=[],
                    target_schemas=[DocEnrichment],
                    model_id="openai:gpt-4o-mini",
                    max_workers=0,
                    extraction_passes=1,
                )
                attrs = None
                exs = getattr(result, "extractions", []) or []
                if exs:
                    attrs = getattr(exs[0], "attributes", None)
                if attrs is None:
                    out = EnrichOut()
                else:
                    out = EnrichOut.model_validate(attrs)  # type: ignore[arg-type]
            else:
                raise RuntimeError("langextract not available")
        except Exception as exc:
            logger.debug("LangExtract enrich failed: %s", exc)
            ls = LLMService()
            out = ls.structured(
                [
                    {
                        "role": "system",
                        "content": (
                            "Return JSON only with keys: lang (ISO 639-1 code), "
                            "summary_short, summary_long, bullets (2-6), key_points (2-6), "
                            "topics_primary (snake_case), topics_secondary (0-8 snake_case), tags (2-10 snake_case). "
                            "Make the summaries richer: summary_short should be 3-6 sentences in one paragraph; "
                            "summary_long should be 2-4 paragraphs with 5-8 sentences per paragraph."
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                schema=EnrichOut,
            )

        # ---------- 2) Entities/relations (graph extract) ----------
        entities: List[Dict[str, Any]] = []
        try:
            g = self.extract_graph(text=text, metadata=metadata or {})
            entities = g.get("entities") or []
            # merge topics if present
            if (not out.topics_primary) and (g.get("topics")):
                topics = g.get("topics") or []
                if isinstance(topics, list) and topics:
                    out.topics_primary = topics[0]
                    out.topics_secondary = topics[1:]
        except Exception as exc:
            logger.debug("graph enrich failed: %s", exc)

        # ---------- 3) Embedding ----------
        embedding: Optional[List[float]] = None
        if include_embedding:
            try:
                from openai import OpenAI  # type: ignore

                from alfred.core.settings import settings

                api_key = (
                    settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
                )
                client = OpenAI(
                    api_key=api_key,
                    base_url=settings.openai_base_url,
                    organization=settings.openai_organization,
                )
                resp = client.embeddings.create(model="text-embedding-3-small", input=text)
                embedding = list(resp.data[0].embedding)
            except Exception as exc:  # pragma: no cover - network
                logger.debug("embedding failed: %s", exc)

        # ---------- 4) Assemble output ----------
        summary = {
            "short": (out.summary_short or "").strip(),
            "long": (out.summary_long or None),
            "bullets": [b for b in out.bullets if isinstance(b, str) and b.strip()],
            "key_points": [k for k in out.key_points if isinstance(k, str) and k.strip()],
        }
        # drop empties to keep storage tidy
        if (
            not summary.get("short")
            and not summary.get("long")
            and not summary["bullets"]
            and not summary["key_points"]
        ):
            summary = {}

        topics = {
            "primary": out.topics_primary,
            "secondary": out.topics_secondary,
        }
        if not topics.get("primary") and not (topics.get("secondary") or []):
            topics = {}

        return {
            "lang": (out.lang or None),
            "raw_markdown": raw_markdown,
            "cleaned_text": cleaned_text,
            "tokens": _token_count(cleaned_text),
            "hash": _sha256_hex(cleaned_text),
            "summary": summary or None,
            "topics": topics or None,
            "entities": entities or None,
            "tags": out.tags or [],
            "embedding": embedding,
        }

    # ------------------------------------------------------------
    # Taxonomy classification via LangExtract (with prompt templates)
    # ------------------------------------------------------------
    def classify_taxonomy(
        self, *, text: str, taxonomy_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Classify text into (domain, subdomain, microtopics, topic{title,confidence}).

        Uses prompt templates in apps/alfred/prompts/classification and LangExtract with
        OpenAI provider for structured output. Falls back to LLMService.structured on error.
        """
        txt = (text or "").strip()[:8000]
        # Prepare prompt description
        instructions = load_prompt("classification", "instructions.md")
        taxonomy = taxonomy_context or load_prompt("classification", "taxonomy_min.txt")
        prompt_description = instructions.replace("{TAXONOMY}", taxonomy).replace("{TEXT}", txt)

        # LangExtract schema (dataclasses)
        from dataclasses import dataclass as _dc_dataclass

        @_dc_dataclass
        class Topic:
            title: Optional[str] = None
            confidence: Optional[float] = None

        @_dc_dataclass
        class Classification:
            domain: Optional[str] = None
            subdomain: Optional[str] = None
            microtopics: list[str] = field(default_factory=list)
            topic: Topic = field(default_factory=Topic)

        try:
            if _LANGEXTRACT_AVAILABLE and lx is not None:
                result = lx.extract(  # type: ignore[attr-defined]
                    text_or_documents=txt,
                    prompt_description=prompt_description,
                    examples=[],
                    target_schemas=[Classification],
                    model_id="openai:gpt-4o-mini",
                    max_workers=0,
                    extraction_passes=1,
                )
                exs = getattr(result, "extractions", []) or []
                attrs = getattr(exs[0], "attributes", None) if exs else None
                if isinstance(attrs, dict):
                    # Ensure keys exist as expected
                    out = {
                        "domain": attrs.get("domain"),
                        "subdomain": attrs.get("subdomain"),
                        "microtopics": attrs.get("microtopics") or [],
                        "topic": attrs.get("topic") or {},
                    }
                    return out
        except Exception as exc:
            logger.debug("LangExtract classify failed: %s", exc)

        # Fallback to LLMService.structured
        class TopicTitle(BaseModel):
            title: str
            confidence: float = Field(ge=0.0, le=1.0)

        class ClassificationResult(BaseModel):
            domain: Optional[str] = None
            subdomain: Optional[str] = None
            microtopics: Optional[List[str]] = None
            topic: TopicTitle

        ls = LLMService()
        res = ls.structured(
            [
                {"role": "system", "content": "Return valid JSON only."},
                {"role": "user", "content": prompt_description},
            ],
            schema=ClassificationResult,
        )
        return res.model_dump()
