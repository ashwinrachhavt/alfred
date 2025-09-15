from __future__ import annotations

import os
from typing import List

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from alfred.connectors.web_connector import WebConnector

DEFAULT_UA = "Mozilla/5.0 (compatible; AlfredBot/1.0; +https://github.com/alfred)"


def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass


def make_llm(temperature: float = 0.0) -> ChatOpenAI:
    _load_env()
    from alfred.services.agentic_rag import CHAT_MODEL, FALLBACK_MODEL

    try:
        return ChatOpenAI(model=CHAT_MODEL, temperature=temperature)
    except Exception:
        return ChatOpenAI(model=FALLBACK_MODEL, temperature=temperature)


class UnifiedWebSearchTool(BaseTool):
    name: str = "web_search_multi"
    description: str = (
        "Search the public web across multiple providers and return candidate result URLs "
        "with short snippets. Input: a query string about the company or a specific page."
    )

    max_results: int = 20

    def _run(self, query: str) -> str:  # type: ignore[override]
        try:
            conn = WebConnector(mode="multi")
            resp = conn.search(query)
            hits = resp.hits[: self.max_results]
            lines = []
            for h in hits:
                title = h.title or ""
                url = h.url or ""
                snip = (h.snippet or "").replace("\n", " ")
                lines.append(f"- {title} | {url} | {snip}")
            return "\n".join(lines) if lines else "(no results)"
        except Exception as e:
            return f"(error) {e}"

    async def _arun(self, *args, **kwargs) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)


class FetchUrlsTool(BaseTool):
    name: str = "fetch_urls"
    description: str = (
        "Fetch and extract readable text from the given URLs. Input: a comma-separated list of URLs."
    )

    max_chars_per_url: int = 12000

    def _run(self, urls_text: str) -> str:  # type: ignore[override]
        try:
            from langchain_community.document_loaders import WebBaseLoader
        except Exception:
            return "(error) web loader not available)"

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
    try:
        from langchain_community.tools import DuckDuckGoSearchRun  # type: ignore

        ddg = DuckDuckGoSearchRun()
        ddg.name = "web_search"
        ddg.description = "Search the public web for company websites, press, blogs, and news."
        tools.append(ddg)
    except Exception:
        pass

    tools.append(UnifiedWebSearchTool())
    tools.append(FetchUrlsTool())
    return tools


SYSTEM_PROMPT = (
    "You are an expert company researcher. Use the search tools to identify the official site "
    "and authoritative pages (About, Products/Docs, Customers/Case Studies, Pricing, Careers, Press/News, Blog). "
    "Fetch those pages and any high-quality third-party sources (news, filings, reputable analysis). "
    "Then write a long-form research report (target 1,500–2,500 words) with these sections: "
    "1) Overview and Mission; 2) History and Milestones; 3) Products and Value Proposition; 4) Target Customers and Segments; "
    "5) Business Model and Monetization; 6) Go-to-Market and Distribution; 7) Market Landscape and Competitors; 8) Technology Stack and IP; "
    "9) Pricing and Packaging (if public); 10) Traction and Financials/Funding; 11) Partnerships and Ecosystem; 12) Risks and Challenges; 13) Strategy Signals and Roadmap; "
    "14) SWOT; 15) Notable People and Hiring Signals; 16) Sources. Keep claims grounded in fetched content. When unclear, state assumptions explicitly. "
    "Cite domains and URLs in a Sources section at the end."
)


def build_company_graph():
    tools = make_tools()
    llm = make_llm(temperature=0.0).bind_tools(tools)

    def think_or_act(state: MessagesState):
        return {"messages": [llm.invoke(state["messages"])]}

    def finalize(state: MessagesState):
        synth = make_llm(temperature=0.1)
        prompt = (
            "Produce the long-form company research report now. Ensure complete sections and include a Sources section with domains and URLs."
        )
        msg = synth.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                *state["messages"],
                {"role": "user", "content": prompt},
            ]
        )
        return {"messages": [msg]}

    g = StateGraph(MessagesState)
    g.add_node("agent", think_or_act)
    g.add_node("tools", ToolNode(tools))
    g.add_node("finalize", finalize)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)

    return g.compile()


def research_company(name: str) -> str:
    graph = build_company_graph()
    seed = (
        "Research the company thoroughly. Identify the official site, then fetch About, Products/Docs, Customers, Pricing, "
        "Careers, Press/News, Blog. Include reputable third-party context. If multiple similarly named entities exist, "
        "select the most prominent technology company. "
        f"Company to research: {name}."
    )
    final = ""
    for chunk in graph.stream(
        {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": seed},
            ]
        },
        config={"recursion_limit": 60}
    ):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    return final
