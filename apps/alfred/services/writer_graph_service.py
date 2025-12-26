from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from typing import Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import StreamWriter

from alfred.core.llm_factory import get_chat_model, get_embedding_model
from alfred.core.settings import LLMProvider, settings
from alfred.prompts import load_prompt
from alfred.schemas.writing import WritingPreset, WritingRequest
from alfred.services.agentic_rag import make_retriever
from alfred.services.checkpoint_postgres import (
    PostgresCheckpointConfig,
    PostgresCheckpointSaver,
)
from alfred.services.writer_semantic_cache import WriterSemanticCache
from alfred.services.writing_presets import preset_rules, resolve_preset

WRITER_CACHE_VERSION = "writer-2025-12-26-v1"
WRITER_CHECKPOINT_NS = "writer"


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


def write(req: WritingRequest) -> tuple[WritingPreset, str]:
    """
    Non-streaming writer invocation.

    Uses LangGraph internally; if a checkpointer DSN is configured, the request's
    `thread_id` (if present) becomes resumable across calls.
    """
    preset = resolve_preset(site_url=req.site_url, preset=req.preset)
    if _use_stub_writing():
        return preset, _stub_output(req, preset)

    thread_id = (getattr(req, "thread_id", None) or "").strip() or "writer"
    out = _graph().invoke(
        {"req": req},
        config={"configurable": {"thread_id": thread_id, "checkpoint_ns": WRITER_CHECKPOINT_NS}},
    )
    return preset, str(out.get("output") or "")


def write_stream(req: WritingRequest) -> tuple[WritingPreset, Iterable[str]]:
    """
    Streaming writer invocation.

    Yields tokens (strings). Uses LangGraph stream_mode="custom" so tokens can
    be emitted from inside nodes via StreamWriter.
    """
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


__all__ = ["write", "write_stream"]
