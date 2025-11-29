from __future__ import annotations

import os
from typing import List, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from alfred.connectors.web_connector import WebConnector
from alfred.prompts import load_prompt

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
    description: str = "Fetch and extract readable text from the given URLs. Input: a comma-separated list of URLs."

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


SYSTEM_PROMPT = load_prompt("company_researcher", "system.md")
_FINALIZE_PROMPT = load_prompt("company_researcher", "finalize.md")
_SEED_PROMPT = load_prompt("company_researcher", "seed.md")


def build_company_graph():
    tools = make_tools()
    llm = make_llm(temperature=0.0).bind_tools(tools)

    def think_or_act(state: CompanyState):
        return {"messages": [*state["messages"], llm.invoke(state["messages"])]}

    def finalize(state: CompanyState):
        synth = make_llm(temperature=0.1)
        prompt = _FINALIZE_PROMPT
        msg = synth.invoke(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                *state["messages"],
                {"role": "user", "content": prompt},
            ]
        )
        return {"messages": [*state["messages"], msg]}

    def tools_condition_local(state: CompanyState):
        msgs = state.get("messages", [])
        if not msgs:
            return END
        last = msgs[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    def tools_node(state: CompanyState):
        msgs = state.get("messages", [])
        if not msgs:
            return {"messages": msgs}
        last = msgs[-1]
        if not isinstance(last, AIMessage):
            return {"messages": msgs}
        name_to_tool = {t.name: t for t in tools}
        out: list[ToolMessage] = []
        for call in getattr(last, "tool_calls", []) or []:
            name = getattr(call, "name", None) or (
                call.get("name") if isinstance(call, dict) else None
            )
            args = (
                getattr(call, "args", None)
                or (call.get("args") if isinstance(call, dict) else None)
                or ""
            )
            call_id = getattr(call, "id", None) or (
                call.get("id") if isinstance(call, dict) else name
            )
            tool = name_to_tool.get(name or "")
            if tool is None:
                out.append(
                    ToolMessage(content=f"(tool not found: {name})", tool_call_id=str(call_id))
                )
                continue
            try:
                result = tool.invoke(args)
            except Exception:
                try:
                    result = tool.run(args)
                except Exception as exc:
                    result = f"(error) {exc}"
            out.append(ToolMessage(content=str(result), tool_call_id=str(call_id)))
        return {"messages": [*msgs, *out]}

    g = StateGraph(CompanyState)
    g.add_node("agent", think_or_act)
    g.add_node("tools", tools_node)
    g.add_node("finalize", finalize)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition_local, {"tools": "tools", END: "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)

    return g.compile()


def research_company(name: str) -> str:
    graph = build_company_graph()
    seed = f"{_SEED_PROMPT}\nCompany to research: {name}."
    final = ""
    for chunk in graph.stream(
        {
            "messages": [
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=seed),
            ]
        },
        config={"recursion_limit": 60},
    ):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    return final


class CompanyState(TypedDict):
    messages: list[BaseMessage]
