from __future__ import annotations

import json
import logging
import os
from typing import Any, Iterable, List, Literal, Sequence, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from alfred.prompts import load_prompt
from alfred.services.web_search import search_web

# Keep it simple: no checkpointing by default
_MEMORY_SAVER = None


class AgentState(TypedDict):
    messages: list[BaseMessage]


# ------------------------ CONFIG ------------------------
COLLECTION = os.getenv("QDRANT_COLLECTION", os.getenv("CHROMA_COLLECTION", "personal_kb"))
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-4.1")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gpt-4.1-mini")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_store")
QDRANT_URL = os.getenv("QDRANT_URL")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")
QDRANT_HOST = os.getenv("QDRANT_HOST")
QDRANT_PORT = os.getenv("QDRANT_PORT")
ENABLE_QDRANT = os.getenv("ALFRED_ENABLE_QDRANT", "0").lower() in {"1", "true", "yes"}


# ------------------------ PROMPTS ------------------------

_CORE_SYSTEM_PROMPT = load_prompt("agentic_rag", "core.md")
_MODE_PROMPT_FILES: dict[str, str] = {
    "minimal": "minimal.md",
    "concise": "concise.md",
    "formal": "formal.md",
    "deep": "deep.md",
    "interview": "interview.md",
}


def build_system_prompt(mode: str = "minimal") -> str:
    mode_key = (mode or "minimal").lower()
    prefix = ""
    prompt_file = _MODE_PROMPT_FILES.get(mode_key)
    if prompt_file:
        try:
            prefix = load_prompt("agentic_rag", prompt_file)
        except FileNotFoundError:
            prefix = ""

    parts = [prefix, _CORE_SYSTEM_PROMPT]
    return "\n\n".join(part for part in parts if part).strip()


# ------------------------ HELPERS ------------------------
def make_llm(temperature: float = 0.2):
    try:
        return ChatOpenAI(model=CHAT_MODEL, temperature=temperature)
    except Exception:
        return ChatOpenAI(model=FALLBACK_MODEL, temperature=temperature)


logger = logging.getLogger(__name__)


class _NullRetriever:
    """Retriever stub used when vector stores are unavailable."""

    def invoke(self, query: str) -> Sequence[Document]:  # type: ignore[override]
        return []

    async def ainvoke(self, query: str) -> Sequence[Document]:  # pragma: no cover
        return []


class _RetrieverTool(BaseTool):  # pragma: no cover - simple stringifying tool
    retriever: Any

    name: str = "retrieve_notes"
    description: str = "Retrieve relevant context snippets from the personal knowledge base."

    def _run(self, query: str) -> str:  # type: ignore[override]
        docs: Sequence[Document] = self.retriever.invoke(query)
        return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)

    async def _arun(self, query: str) -> str:  # pragma: no cover
        docs: Sequence[Document] = await self.retriever.ainvoke(query)
        return "\n\n".join(getattr(d, "page_content", str(d)) for d in docs)


class _WebSearchTool(BaseTool):  # pragma: no cover - HTTP-backed search tool
    name: str = "web_search"
    description: str = (
        "Search the public web via SearxNG. Provide a plain-language query. "
        "The tool returns JSON with fields title, url, snippet for the top results."
    )

    top_k: int = 5

    def _run(self, query: str) -> str:  # type: ignore[override]
        resp = search_web(query, mode="auto")
        hits = resp.get("hits", [])
        simplified = []
        for item in hits:
            simplified.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": (item.get("snippet", "") or "")[:240],
                }
            )
        return json.dumps({"results": simplified}, ensure_ascii=False)

    async def _arun(self, query: str) -> str:  # pragma: no cover
        return self._run(query)


def _build_qdrant_vector_store(embed: OpenAIEmbeddings):  # type: ignore[name-defined]
    if not ((QDRANT_URL and QDRANT_API_KEY) or (QDRANT_HOST and QDRANT_PORT)):
        return None

    try:
        from langchain_qdrant import QdrantVectorStore  # type: ignore
        from qdrant_client import QdrantClient  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        logger.warning("Qdrant client not installed; using no-op retriever (%s)", exc)
        return None

    try:
        if QDRANT_URL:
            client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        else:
            client = QdrantClient(
                host=QDRANT_HOST,
                port=int(QDRANT_PORT or 6333),
                api_key=QDRANT_API_KEY,
            )

        if hasattr(client, "collection_exists"):
            exists = client.collection_exists(collection_name=COLLECTION)
            if not exists:
                raise RuntimeError(f"Qdrant collection '{COLLECTION}' not found")

        return QdrantVectorStore(client=client, collection_name=COLLECTION, embedding=embed)
    except Exception as exc:
        logger.warning("Qdrant unavailable; using no-op retriever (%s)", exc)
        return None


def make_retriever(k: int = 4):
    if not ENABLE_QDRANT:
        return _NullRetriever()

    embed = OpenAIEmbeddings(model=EMBED_MODEL)
    vs = _build_qdrant_vector_store(embed)
    if vs is None:
        return _NullRetriever()

    return vs.as_retriever(search_kwargs={"k": k})


def create_retriever_tool(retriever: Any, name: str, description: str) -> BaseTool:
    return _RetrieverTool(name=name, description=description, retriever=retriever)


def get_context_chunks(question: str, k: int = 4) -> List[dict]:
    retriever = make_retriever(k=k)
    docs = retriever.invoke(question)
    items = []
    for d in docs:
        items.append(
            {
                "text": d.page_content,
                "source": (d.metadata or {}).get("source"),
                "title": (d.metadata or {}).get("title"),
            }
        )
    return items


# ------------------------ TOOLS ------------------------
def make_tools(k: int = 4):
    # Qdrant retriever tool over personal notes
    retriever = make_retriever(k=k)
    retriever_tool = create_retriever_tool(
        retriever,
        name="retrieve_notes",
        description=(
            "Search and return information from Ashwin's personal notes (vector store). "
            "Use this to answer questions about my work, projects, publications, and content."
        ),
    )

    # DuckDuckGo web search tool
    try:
        from langchain_community.tools import DuckDuckGoSearchRun  # type: ignore

        ddg = DuckDuckGoSearchRun()
        ddg.name = "web_search"
        ddg.description = (
            "Look up current information on the public web (DuckDuckGo). "
            "Use this when asked to research external companies or topics beyond my notes."
        )
        tools = [retriever_tool, ddg]
    except Exception:
        tools = [retriever_tool]

    # Always include a web search tool for richer sourcing
    tools.append(_WebSearchTool())

    return tools


# ------------------------ GRAPH NODES ------------------------
def generate_query_or_respond(state: AgentState, k: int = 4):
    tools = make_tools(k=k)
    llm = make_llm(temperature=0.0).bind_tools(tools)
    response = llm.invoke(state["messages"])  # decide to call a tool or respond
    return {"messages": [*state["messages"], response]}


GRADE_PROMPT = (
    "You grade whether this context helps answer the user’s question.\n"
    'If it meaningfully overlaps in entities, facts, or tasks → "yes". Otherwise → "no".\n'
    'Be strict: superficial keyword overlap without factual support is "no".\n'
    'Return binary_score = "yes" or "no".\n\n'
    "Question: {question}\n"
    "Context: {context}\n"
)


class GradeDocuments(BaseModel):
    binary_score: str = Field(
        description="Relevance score: 'yes' if relevant, or 'no' if not relevant"
    )


def grade_documents(state: AgentState) -> Literal["generate_answer", "rewrite_question"]:
    messages = state["messages"]
    question = messages[0].content
    context = messages[-1].content
    grader = make_llm(temperature=0.0)
    prompt = GRADE_PROMPT.format(question=question, context=context)
    result = grader.with_structured_output(GradeDocuments).invoke(
        [{"role": "user", "content": prompt}]
    )
    return "generate_answer" if result.binary_score == "yes" else "rewrite_question"


REWRITE_PROMPT = (
    "Infer the user’s intent and rewrite a sharper, retrieval-friendly question that:\n"
    "- Names the entity/topic explicitly.\n"
    '- Includes time bounds if implied ("latest", "as of YYYY-MM").\n'
    "- Preserves first-person perspective when the question is about me.\n\n"
    "Return ONLY the rewritten question, nothing else.\n\n"
    "Original question:\n{question}\n"
)


def rewrite_question(state: AgentState):
    question = state["messages"][0].content
    pro = REWRITE_PROMPT.format(question=question)
    response = make_llm(temperature=0.0).invoke([{"role": "user", "content": pro}])
    return {"messages": [*state["messages"], {"role": "user", "content": response.content}]}


def generate_answer(state: AgentState, mode: str = "minimal"):
    question = state["messages"][0].content
    context = state["messages"][-1].content
    system = build_system_prompt(mode)
    pro = (
        system
        + "\n\nTask: Answer the user in MY first-person voice.\n\n"
        + "Question:\n{question}\n\n".format(question=question)
        + "Context (retrieved notes + optional web_search):\n{context}\n\n".format(context=context)
        + "Now produce:\n"
        + "1) A direct first-person answer (1–2 lines).\n"
        + "2) 3–6 concise bullets: evidence (with small attributions), impact/metrics, key decisions or trade-offs.\n"
        + "3) If anything is missing, one line: “What I’d need to answer fully: …”\n"
        + "4) A `Sources:` section with markdown bullet list linking to any URLs returned by tools.\n"
    )
    response = make_llm(temperature=0.2).invoke([{"role": "user", "content": pro}])
    return {"messages": [*state["messages"], response]}


def tools_condition_local(state: AgentState):
    msgs = state.get("messages", [])
    if not msgs:
        return END
    last = msgs[-1]
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    return END


def tools_node(state: AgentState, tools: list[BaseTool]):
    msgs = state.get("messages", [])
    if not msgs:
        return {"messages": msgs}

    last = msgs[-1]
    if not isinstance(last, AIMessage):
        return {"messages": msgs}

    name_to_tool = {t.name: t for t in tools}
    out: list[ToolMessage] = []
    for call in getattr(last, "tool_calls", []) or []:
        name = getattr(call, "name", None) or (call.get("name") if isinstance(call, dict) else None)
        args = (
            getattr(call, "args", None)
            or (call.get("args") if isinstance(call, dict) else None)
            or ""
        )
        call_id = getattr(call, "id", None) or (call.get("id") if isinstance(call, dict) else name)
        tool = name_to_tool.get(name or "")
        if tool is None:
            out.append(ToolMessage(content=f"(tool not found: {name})", tool_call_id=str(call_id)))
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


# ------------------------ GRAPH BUILD/EXEC ------------------------
def build_agent_graph(k: int = 4, mode: str = "minimal"):
    workflow = StateGraph(AgentState)

    workflow.add_node("generate_query_or_respond", lambda s: generate_query_or_respond(s, k=k))
    workflow.add_node("tools", lambda s: tools_node(s, make_tools(k=k)))
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("generate_answer", lambda s: generate_answer(s, mode=mode))

    workflow.add_edge(START, "generate_query_or_respond")

    # Decide whether to retrieve or finish
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition_local,
        {"tools": "tools", END: END},
    )

    workflow.add_conditional_edges("tools", grade_documents)
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")

    # No checkpointer configured; compile straightforwardly
    return workflow.compile()


def answer_agentic(question: str, k: int = 4, mode: str = "minimal") -> str:
    graph = build_agent_graph(k=k, mode=mode)
    final = ""
    for chunk in graph.stream({"messages": [HumanMessage(content=question)]}):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    return enforce_first_person(final)


def enforce_first_person(text: str) -> str:
    swaps = {
        "Ashwin has": "I have",
        "Ashwin is": "I am",
        "Ashwin was": "I was",
        "Ashwin did": "I did",
        "Ashwin led": "I led",
        "Ashwin built": "I built",
    }
    for a, b in swaps.items():
        text = text.replace(a, b)
    return text


def stream_answer(question: str, k: int = 4) -> Iterable[str]:
    # Simple non-token streaming: yield the final answer once (compatible with existing SSE shape)
    yield answer_agentic(question, k=k)
