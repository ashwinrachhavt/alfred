from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from alfred.agents.writer.state import WriterState


def build_writer_graph():
    """Build the writer graph.

    Implementation lives here to match LangGraph application structure, while the
    business logic helpers remain in `alfred.services.writing_service`.
    """

    from langchain_core.messages import HumanMessage, SystemMessage
    from langgraph.types import StreamWriter

    from alfred.core.llm_factory import get_chat_model
    from alfred.core.settings import settings
    from alfred.prompts import load_prompt
    from alfred.services import writing_service as ws

    cache = ws._get_semantic_cache()

    def prepare_node(state: WriterState) -> WriterState:
        req = state["req"]
        preset = ws.resolve_preset(site_url=req.site_url, preset=req.preset)
        rules = ws.preset_rules(preset, max_chars=req.max_chars)
        return {"preset": preset, "site_rules": rules}

    def cache_lookup_node(state: WriterState, *, writer: StreamWriter) -> WriterState:
        if cache is None:
            return {"cache_hit": False}
        req = state["req"]
        preset = state["preset"]
        llm_key = ws._llm_string(
            provider=settings.llm_provider,
            model=settings.writer_model,
            temperature=float(
                req.temperature if req.temperature is not None else settings.writer_temperature
            ),
        )
        prompt = ws._build_prompt(req, preset, state["site_rules"], voice_examples="")
        hit = cache.lookup(prompt=prompt, llm_string=llm_key)
        if hit is None:
            return {"cache_hit": False}
        if hit.output:
            writer(hit.output)
        return {"cache_hit": True, "output": hit.output}

    def voice_node(state: WriterState) -> WriterState:
        req = state["req"]
        return {"voice_examples": ws._retrieve_voice_examples(req)}

    def generate_node(state: WriterState, *, writer: StreamWriter) -> WriterState:
        req = state["req"]
        preset = state["preset"]
        if ws._use_stub_writing():
            return {"output": ws._stub_output(req, preset)}

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
        prompt = ws._build_prompt(req, preset, state["site_rules"], state.get("voice_examples", ""))
        messages = [SystemMessage(content=sys), HumanMessage(content=prompt)]

        chunks: list[str] = []
        for part in chat.stream(messages):
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
        llm_key = ws._llm_string(
            provider=settings.llm_provider,
            model=settings.writer_model,
            temperature=float(
                req.temperature if req.temperature is not None else settings.writer_temperature
            ),
        )
        prompt = ws._build_prompt(
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

    checkpointer = ws._get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


def agent():
    """LangGraph entrypoint for deployment."""

    return build_writer_graph()
