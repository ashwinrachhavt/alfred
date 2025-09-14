from __future__ import annotations

import os
from typing import List

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

DEFAULT_UA = (
    "Mozilla/5.0 (compatible; AlfredBot/1.0; +https://github.com/alfred)"
)


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass


def make_llm(temperature: float = 0.0) -> ChatOpenAI:
    _load_env()
    from alfred_app.services.agentic_rag import CHAT_MODEL, FALLBACK_MODEL  # reuse

    try:
        return ChatOpenAI(model=CHAT_MODEL, temperature=temperature)
    except Exception:
        return ChatOpenAI(model=FALLBACK_MODEL, temperature=temperature)


class FetchUrlsTool(BaseTool):
    name: str = "fetch_urls"
    description: str = (
        "Fetch and extract readable text from the given URLs. "
        "Input: a comma-separated list of URLs. "
        "Returns merged plain text with small 'SOURCE: <url>' markers."
    )

    max_chars_per_url: int = 6000

    def _run(self, urls_text: str) -> str:  # type: ignore[override]
        try:
            from langchain_community.document_loaders import WebBaseLoader
        except Exception:
            return "(error) web loader not available"

        # Parse URLs (comma or newline separated)
        raw = [u.strip() for u in urls_text.replace("\n", ",").split(",")]
        urls = [u for u in raw if u]
        if not urls:
            return "(no urls provided)"

        header = {
            "User-Agent": os.getenv("USER_AGENT", DEFAULT_UA),
            "Accept-Language": "en-US,en;q=0.9",
        }
        out_parts: List[str] = []
        for u in urls:
            try:
                loader = WebBaseLoader([u], header_template=header)
                docs = loader.load()
                merged = "\n".join(d.page_content for d in docs if d.page_content)
                merged = merged[: self.max_chars_per_url]
                out_parts.append(f"SOURCE: {u}\n{merged}")
            except Exception as e:
                out_parts.append(f"SOURCE: {u}\n(error fetching: {e})")
        return "\n\n---\n\n".join(out_parts)

    async def _arun(self, *args, **kwargs) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)


def make_tools() -> list:
    tools: list = []
    # Web search
    try:
        from langchain_community.tools import DuckDuckGoSearchRun  # type: ignore

        ddg = DuckDuckGoSearchRun()
        ddg.name = "web_search"
        ddg.description = (
            "Search the public web for company websites, press, blogs, and news."
        )
        tools.append(ddg)
    except Exception:
        pass

    tools.append(FetchUrlsTool())
    return tools


SYSTEM_PROMPT = (
    "You are an expert company researcher. Find the official site and key pages (About, "
    "Products, Customers, Careers, Press, Blog). Use tools to search and fetch sources. "
    "Then write a structured brief with: Overview, Mission, Products, Customers/Segments, "
    "Business Model, Funding (if any), Leadership, Tech Stack (if evident), Recent News, "
    "Strategy Signals, Risks, Competitors, Sources. Use first person ('I') in conclusions "
    "when asked to tailor. Keep claims grounded; add Sources at the end."
)


def build_company_graph():
    tools = make_tools()
    llm = make_llm(temperature=0.0).bind_tools(tools)

    def think_or_act(state: MessagesState):
        return {"messages": [llm.invoke(state["messages"])]}

    def finalize(state: MessagesState):
        synth = make_llm(temperature=0.2)
        prompt = (
            "Synthesize a concise company brief from the conversation so far. "
            "Focus on facts. Output sections with short paragraphs or bullets. "
            "End with Sources (titles or domains + URLs)."
        )
        msg = synth.invoke([{"role": "system", "content": SYSTEM_PROMPT},
                            *state["messages"],
                            {"role": "user", "content": prompt}])
        return {"messages": [msg]}

    g = StateGraph(MessagesState)
    g.add_node("agent", think_or_act)
    g.add_node("tools", ToolNode(tools))
    g.add_node("finalize", finalize)

    g.add_edge(START, "agent")
    g.add_conditional_edges(
        "agent",
        tools_condition,
        {"tools": "tools", END: "finalize"},
    )
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)

    return g.compile()


def research_company(name: str) -> str:
    graph = build_company_graph()
    seed = (
        "Research the company thoroughly. Identify the official site, then fetch About, "
        "Products, Customers, Careers, Press, Blog, docs or platform pages. If there are "
        "multiple similarly named entities, pick the most prominent technology company. "
        f"Company to research: {name}."
    )
    final = ""
    for chunk in graph.stream({"messages": [{"role": "system", "content": SYSTEM_PROMPT},
                                            {"role": "user", "content": seed}]}):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    return final
