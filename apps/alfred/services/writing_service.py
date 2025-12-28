from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, TypedDict
from urllib.parse import urlparse

from redis import Redis

from alfred.core.settings import LLMProvider, settings
from alfred.prompts import load_prompt
from alfred.schemas.writing import WritingPreset, WritingRequest

if TYPE_CHECKING:  # pragma: no cover
    from alfred.services.checkpoint_postgres import PostgresCheckpointSaver

logger = logging.getLogger(__name__)

WRITER_CACHE_VERSION = "writer-2025-12-26-v1"
WRITER_CHECKPOINT_NS = "writer"


def _normalize_hostname(site_url: str) -> str:
    if not site_url.strip():
        return ""
    try:
        parsed = urlparse(site_url)
        return (parsed.hostname or "").lower().strip()
    except Exception:  # pragma: no cover - defensive
        return ""


def infer_preset_key(site_url: str) -> str:
    host = _normalize_hostname(site_url)
    if not host:
        return "generic"

    # Social
    if host.endswith("linkedin.com"):
        return "linkedin"
    if host.endswith("x.com") or host.endswith("twitter.com"):
        return "x"
    if host.endswith("reddit.com"):
        return "reddit"
    if host.endswith("news.ycombinator.com") or host.endswith("ycombinator.com"):
        return "hackernews"

    # Work
    if host.endswith("mail.google.com"):
        return "gmail"
    if host.endswith("github.com"):
        return "github"
    if host.endswith("notion.so"):
        return "notion"
    if host.endswith("slack.com"):
        return "slack"

    return "generic"


def list_writing_presets() -> list[WritingPreset]:
    return [
        WritingPreset(
            key="generic",
            title="General",
            description="Clean, minimal writing for most sites.",
            format="plain",
        ),
        WritingPreset(
            key="linkedin",
            title="LinkedIn",
            description="Professional, skimmable, confident; short paragraphs; no fluff.",
            format="plain",
        ),
        WritingPreset(
            key="x",
            title="X / Twitter",
            description="Punchy, direct; avoid hashtags; keep it tight.",
            max_chars=280,
            format="plain",
        ),
        WritingPreset(
            key="reddit",
            title="Reddit",
            description="Helpful and grounded; explain briefly why; conversational, not salesy.",
            format="plain",
        ),
        WritingPreset(
            key="hackernews",
            title="Hacker News",
            description="Calm, factual, technical; minimal hype; acknowledge uncertainty.",
            format="plain",
        ),
        WritingPreset(
            key="gmail",
            title="Gmail",
            description="Professional email tone; concise; clear CTA.",
            format="plain",
        ),
        WritingPreset(
            key="github",
            title="GitHub",
            description="Concise and technical; prefer Markdown; crisp bullets when helpful.",
            format="markdown",
        ),
        WritingPreset(
            key="notion",
            title="Notion",
            description="Structured notes; concise headings and bullets; minimal verbosity.",
            format="markdown",
        ),
        WritingPreset(
            key="slack",
            title="Slack",
            description="Short, friendly, actionable; avoid long paragraphs.",
            format="plain",
        ),
    ]


def resolve_preset(*, site_url: str, preset: Optional[str]) -> WritingPreset:
    presets = {p.key: p for p in list_writing_presets()}
    key = (preset or "").strip().lower() or infer_preset_key(site_url)
    return presets.get(key, presets["generic"])


def preset_rules(preset: WritingPreset, *, max_chars: Optional[int]) -> str:
    budget = max_chars if max_chars is not None else preset.max_chars
    parts: list[str] = []

    if preset.key == "linkedin":
        parts.extend(
            [
                "LinkedIn style:",
                "- Start with a strong 1-line hook.",
                "- Use short paragraphs (1–2 lines).",
                "- Be confident and specific; remove filler.",
                "- Avoid hashtags unless the user explicitly asks.",
            ]
        )
    elif preset.key == "x":
        parts.extend(
            [
                "X/Twitter style:",
                "- Be punchy and specific.",
                "- Avoid hashtags unless requested.",
                "- No emojis unless the user used them first.",
            ]
        )
    elif preset.key == "reddit":
        parts.extend(
            [
                "Reddit style:",
                "- Be helpful and grounded.",
                "- Explain briefly why, not just what.",
                "- Avoid marketing language.",
            ]
        )
    elif preset.key == "hackernews":
        parts.extend(
            [
                "Hacker News style:",
                "- Be factual and technical.",
                "- Avoid hype; state assumptions.",
                "- Keep it concise; cite numbers only if known.",
            ]
        )
    elif preset.key == "gmail":
        parts.extend(
            [
                "Email style:",
                "- Output body only.",
                "- Keep it concise, polite, and direct.",
                "- End with a clear CTA.",
            ]
        )
    elif preset.key == "github":
        parts.extend(
            [
                "GitHub style:",
                "- Prefer Markdown.",
                "- Be concrete and actionable; include steps when relevant.",
                "- Avoid verbosity.",
            ]
        )
    elif preset.key == "notion":
        parts.extend(
            [
                "Notion style:",
                "- Prefer Markdown headings/bullets.",
                "- Be structured and scannable.",
            ]
        )
    elif preset.key == "slack":
        parts.extend(
            [
                "Slack style:",
                "- Keep it short and friendly.",
                "- Use bullets for multiple items.",
            ]
        )

    if budget is not None:
        parts.append(f"Hard limit: {int(budget)} characters (do not exceed).")

    if preset.format == "markdown":
        parts.append("Formatting: Markdown is allowed and preferred.")
    else:
        parts.append("Formatting: plain text (no Markdown) unless the user included Markdown.")

    return "\n".join(parts).strip()


def _hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WriterCacheHit:
    output: str
    score: Optional[float] = None


class WriterSemanticCache:
    """
    Semantic cache for writer outputs using Redis Stack (RediSearch + vectors).

    This is intentionally writer-specific (stores plain strings) instead of using
    LangChain's global LLM cache, to avoid cross-service side effects.
    """

    DEFAULT_SCHEMA = {
        "content_key": "prompt",
        "text": [{"name": "prompt"}],
        "extra": [{"name": "output"}, {"name": "llm_string"}, {"name": "version"}],
    }

    def __init__(
        self,
        *,
        redis_url: str,
        embedding: Any,
        version: str,
        score_threshold: float = 0.2,
        index_prefix: str = "alfred:writer_cache",
    ) -> None:
        # Lazily import heavy deps (langchain/transformers/torch) only when cache is enabled.
        self._vectorstore_cls()
        self._cache: dict[str, Any] = {}
        self.redis_url = redis_url
        self.embedding = embedding
        self.score_threshold = score_threshold
        self.index_prefix = index_prefix
        self.version = version
        self._disabled_reason: str | None = None
        self._disabled_reason = self._preflight_reason()
        if self._disabled_reason:
            logger.warning("Writer semantic cache disabled: %s", self._disabled_reason)

    @staticmethod
    def _vectorstore_cls() -> Any:
        try:
            # Deprecated in langchain-community, but still ships and works for Redis Stack.
            from langchain_community.vectorstores.redis import (
                Redis as RedisVectorstore,  # noqa: PLC0415
            )
        except Exception as exc:  # pragma: no cover - optional dependency surface
            raise RuntimeError("Redis vectorstore backend is not available") from exc
        return RedisVectorstore

    def _preflight_reason(self) -> str | None:
        """
        Avoid noisy errors inside LangChain by checking Redis modules up-front.

        Semantic caching requires Redis Stack with RediSearch >= 2.4.
        """
        try:
            client: Redis = Redis.from_url(self.redis_url)
        except Exception as exc:  # pragma: no cover - env dependent
            return f"Redis connect failed: {exc}"

        try:
            raw = client.execute_command("MODULE", "LIST")
        except Exception as exc:  # pragma: no cover - env dependent
            return f"Redis MODULE LIST failed: {exc}"

        # `MODULE LIST` returns a list of alternating key/value pairs per module.
        modules: list[dict[str, str]] = []
        for entry in raw or []:
            try:
                it = iter(entry)
                d: dict[str, str] = {}
                for k in it:
                    v = next(it)
                    kk = k.decode("utf-8") if isinstance(k, (bytes, bytearray)) else str(k)
                    vv = v.decode("utf-8") if isinstance(v, (bytes, bytearray)) else str(v)
                    d[kk] = vv
                modules.append(d)
            except Exception:
                continue

        search = next((m for m in modules if (m.get("name") or "").lower() == "search"), None)
        if not search:
            return (
                "Redis is missing RediSearch. Run Redis Stack Server (redis-stack-server) "
                "or disable with ALFRED_WRITER_SEMANTIC_CACHE=false."
            )

        # RediSearch version is usually an integer like 20613 (for 2.6.13).
        try:
            ver = int(search.get("ver") or "0")
        except Exception:
            ver = 0
        if ver and ver < 20400:
            return (
                f"RediSearch version is too old (ver={ver}); need >= 2.4. "
                "Upgrade Redis Stack Server."
            )
        return None

    def _index_name(self, llm_string: str) -> str:
        return f"{self.index_prefix}:{_hash(llm_string)}"

    def _get_index(self, llm_string: str) -> Any:
        if self._disabled_reason:
            raise RuntimeError(self._disabled_reason)
        index_name = self._index_name(llm_string)
        if index_name in self._cache:
            return self._cache[index_name]

        RedisVectorstore = self._vectorstore_cls()
        try:
            vs = RedisVectorstore.from_existing_index(
                embedding=self.embedding,
                index_name=index_name,
                redis_url=self.redis_url,
                schema=dict(self.DEFAULT_SCHEMA),
            )
        except ValueError:
            vs = RedisVectorstore(
                embedding=self.embedding,
                index_name=index_name,
                redis_url=self.redis_url,
                index_schema=dict(self.DEFAULT_SCHEMA),
            )
            dim = len(self.embedding.embed_query(text="test"))
            vs._create_index_if_not_exist(dim=dim)

        self._cache[index_name] = vs
        return vs

    def lookup(self, *, prompt: str, llm_string: str) -> Optional[WriterCacheHit]:
        try:
            vs = self._get_index(llm_string)
        except Exception as exc:
            if not self._disabled_reason:
                self._disabled_reason = str(exc) or "Writer semantic cache unavailable"
                logger.warning("Writer semantic cache disabled: %s", self._disabled_reason)
            return None
        try:
            docs = vs.similarity_search(
                query=prompt,
                k=1,
                distance_threshold=self.score_threshold,
            )
        except Exception as exc:
            logger.warning("Writer semantic cache lookup failed: %s", exc)
            return None

        if not docs:
            return None
        doc = docs[0]
        meta = doc.metadata or {}
        if meta.get("version") != self.version:
            return None
        output = str(meta.get("output") or "")
        if not output:
            return None
        return WriterCacheHit(output=output)

    def put(self, *, prompt: str, llm_string: str, output: str) -> None:
        try:
            vs = self._get_index(llm_string)
        except Exception as exc:
            if not self._disabled_reason:
                self._disabled_reason = str(exc) or "Writer semantic cache unavailable"
                logger.warning("Writer semantic cache disabled: %s", self._disabled_reason)
            return
        meta = {
            "llm_string": llm_string,
            "prompt": prompt,
            "output": output,
            "version": self.version,
        }
        try:
            vs.add_texts(texts=[prompt], metadatas=[meta])
        except Exception as exc:
            logger.warning("Writer semantic cache put failed: %s", exc)


class WriterState(TypedDict, total=False):
    req: WritingRequest
    preset: WritingPreset
    site_rules: str
    voice_examples: str
    cache_hit: bool
    output: str


def _use_stub_writing() -> bool:
    # Back-compat for earlier env var naming.
    if os.getenv("ALFRED_WRITING_STUB") == "1" or os.getenv("ALFRED_WRITER_STUB") == "1":
        return True
    if settings.app_env in {"test", "ci"}:
        return True
    if settings.llm_provider == LLMProvider.openai and not settings.openai_api_key:
        return True
    return False


def _stub_output(req: WritingRequest, preset: WritingPreset) -> str:
    base = req.selection.strip() or req.draft.strip() or req.instruction.strip()
    if not base:
        base = "Write something clear and minimal."
    budget = req.max_chars if req.max_chars is not None else preset.max_chars
    if budget:
        base = base[: int(budget)]
    return base


def _get_checkpointer() -> Optional[PostgresCheckpointSaver]:
    from alfred.services.checkpoint_postgres import (  # noqa: PLC0415
        PostgresCheckpointConfig,
        PostgresCheckpointSaver,
    )

    dsn = (settings.writer_checkpoint_dsn or "").strip()
    if not dsn:
        return None
    return PostgresCheckpointSaver(cfg=PostgresCheckpointConfig(dsn=dsn))


def _get_semantic_cache() -> Optional[WriterSemanticCache]:
    if not settings.writer_semantic_cache_enabled:
        return None
    redis_url = (settings.redis_url or "").strip()
    if not redis_url:
        return None
    try:
        from alfred.core.llm_factory import get_embedding_model  # noqa: PLC0415

        embedding = get_embedding_model()
        threshold = float(settings.writer_cache_threshold)
        return WriterSemanticCache(
            redis_url=redis_url,
            embedding=embedding,
            score_threshold=threshold,
            version=WRITER_CACHE_VERSION,
        )
    except Exception:
        # Redis Stack might not be installed; treat as optional.
        return None


def _llm_string(*, model: str, temperature: float, provider: LLMProvider) -> str:
    return f"provider={provider.value}|model={model}|temp={temperature}|v={WRITER_CACHE_VERSION}"


def _build_prompt(
    req: WritingRequest, preset: WritingPreset, site_rules: str, voice_examples: str
) -> str:
    return load_prompt("writer", "draft.md").format(
        intent=req.intent,
        site_name=preset.title,
        instruction=req.instruction.strip() or "(none)",
        selection=req.selection.strip() or "(none)",
        draft=req.draft.strip() or "(none)",
        page_text=req.page_text.strip() or "(none)",
        voice_examples=voice_examples.strip() or "(none)",
        site_rules=site_rules.strip() or "(none)",
    )


def _truncate(text: str, *, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit].rstrip()


def _retrieve_voice_examples(req: WritingRequest) -> str:
    # Uses the user's note KB (Qdrant/Chroma) if configured. Safe no-op otherwise.
    from alfred.services.agentic_rag import make_retriever  # noqa: PLC0415

    retriever = make_retriever(k=int(settings.writer_voice_k))
    query = (req.draft.strip() or req.selection.strip() or req.instruction.strip()).strip()
    if not query:
        query = "writing samples in my voice"
    try:
        docs = retriever.invoke(query)
    except Exception:
        return ""

    parts: list[str] = []
    budget = int(settings.writer_voice_char_budget)
    used = 0
    for d in docs or []:
        chunk = str(getattr(d, "page_content", "") or "").strip()
        if not chunk:
            continue
        remaining = budget - used
        if remaining <= 0:
            break
        snippet = _truncate(chunk, limit=min(500, remaining))
        if snippet:
            parts.append(snippet)
            used += len(snippet)
    return "\n\n---\n\n".join(parts).strip()


def build_writer_graph():
    from langchain_core.messages import HumanMessage, SystemMessage  # noqa: PLC0415
    from langgraph.graph import END, START, StateGraph  # noqa: PLC0415
    from langgraph.types import StreamWriter  # noqa: PLC0415

    from alfred.core.llm_factory import get_chat_model  # noqa: PLC0415

    cache = _get_semantic_cache()

    def prepare_node(state: WriterState) -> WriterState:
        req = state["req"]
        preset = resolve_preset(site_url=req.site_url, preset=req.preset)
        rules = preset_rules(preset, max_chars=req.max_chars)
        return {"preset": preset, "site_rules": rules}

    def cache_lookup_node(state: WriterState, *, writer: StreamWriter) -> WriterState:
        if cache is None:
            return {"cache_hit": False}
        req = state["req"]
        preset = state["preset"]
        llm_key = _llm_string(
            provider=settings.llm_provider,
            model=settings.writer_model,
            temperature=float(
                req.temperature if req.temperature is not None else settings.writer_temperature
            ),
        )
        prompt = _build_prompt(req, preset, state["site_rules"], voice_examples="")
        hit = cache.lookup(prompt=prompt, llm_string=llm_key)
        if hit is None:
            return {"cache_hit": False}
        if hit.output:
            writer(hit.output)
        return {"cache_hit": True, "output": hit.output}

    def voice_node(state: WriterState) -> WriterState:
        req = state["req"]
        return {"voice_examples": _retrieve_voice_examples(req)}

    def generate_node(state: WriterState, *, writer: StreamWriter) -> WriterState:
        req = state["req"]
        preset = state["preset"]
        if _use_stub_writing():
            return {"output": _stub_output(req, preset)}

        model_name = settings.writer_model
        temperature = (
            float(req.temperature)
            if req.temperature is not None
            else float(settings.writer_temperature)
        )
        chat = get_chat_model(
            provider=settings.llm_provider, model=model_name, temperature=temperature
        )

        sys = load_prompt("writer", "system.md")
        prompt = _build_prompt(req, preset, state["site_rules"], state.get("voice_examples", ""))
        messages = [SystemMessage(content=sys), HumanMessage(content=prompt)]

        chunks: list[str] = []
        for part in chat.stream(messages):
            # ChatOpenAI yields message chunks; normalize to text.
            content = getattr(part, "content", "")
            if isinstance(content, str):
                text = content
            elif isinstance(content, list):
                text = "".join(str(x) for x in content)
            else:
                text = str(content)
            if text:
                writer(text)
                chunks.append(text)

        output = "".join(chunks).strip()
        budget = req.max_chars if req.max_chars is not None else preset.max_chars
        if budget is not None and len(output) > int(budget):
            output = output[: int(budget)].rstrip()
        return {"output": output}

    def cache_store_node(state: WriterState) -> WriterState:
        if cache is None:
            return {}
        if state.get("cache_hit"):
            return {}
        req = state["req"]
        preset = state["preset"]
        llm_key = _llm_string(
            provider=settings.llm_provider,
            model=settings.writer_model,
            temperature=float(
                req.temperature if req.temperature is not None else settings.writer_temperature
            ),
        )
        prompt = _build_prompt(
            req, preset, state["site_rules"], voice_examples=state.get("voice_examples", "")
        )
        cache.put(prompt=prompt, llm_string=llm_key, output=state.get("output", ""))
        return {}

    def route_after_cache(state: WriterState) -> str:
        return END if state.get("cache_hit") else "voice"

    graph = StateGraph(WriterState)
    graph.add_node("prepare", prepare_node)
    graph.add_node("cache_lookup", cache_lookup_node)
    graph.add_node("voice", voice_node)
    graph.add_node("generate", generate_node)
    graph.add_node("cache_store", cache_store_node)

    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "cache_lookup")
    graph.add_conditional_edges("cache_lookup", route_after_cache, {END: END, "voice": "voice"})
    graph.add_edge("voice", "generate")
    graph.add_edge("generate", "cache_store")
    graph.add_edge("cache_store", END)

    checkpointer = _get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_writer_graph()
    return _GRAPH


@dataclass(frozen=True)
class WritingResult:
    preset_used: WritingPreset
    output: str


def write(req: WritingRequest) -> WritingResult:
    preset = resolve_preset(site_url=req.site_url, preset=req.preset)
    if _use_stub_writing():
        return WritingResult(preset_used=preset, output=_stub_output(req, preset))

    thread_id = (getattr(req, "thread_id", None) or "").strip() or "writer"
    out = _graph().invoke(
        {"req": req},
        config={"configurable": {"thread_id": thread_id, "checkpoint_ns": WRITER_CHECKPOINT_NS}},
    )
    output = str(out.get("output") or "")
    return WritingResult(preset_used=preset, output=output)


def write_stream(req: WritingRequest) -> tuple[WritingPreset, Iterable[str]]:
    preset = resolve_preset(site_url=req.site_url, preset=req.preset)
    if _use_stub_writing():
        return preset, iter([_stub_output(req, preset)])

    thread_id = (getattr(req, "thread_id", None) or "").strip() or "writer"

    def gen() -> Iterator[str]:
        for item in _graph().stream(
            {"req": req},
            config={
                "configurable": {"thread_id": thread_id, "checkpoint_ns": WRITER_CHECKPOINT_NS}
            },
            stream_mode="custom",
        ):
            # item is whatever StreamWriter writes (we write strings).
            if isinstance(item, str) and item:
                yield item

    return preset, gen()


__all__ = [
    "WriterCacheHit",
    "WriterSemanticCache",
    "WritingResult",
    "infer_preset_key",
    "list_writing_presets",
    "preset_rules",
    "resolve_preset",
    "write",
    "write_stream",
]
