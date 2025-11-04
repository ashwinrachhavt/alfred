from __future__ import annotations

import json
import logging
import os
from typing import Annotated, Any, Iterable, List, Literal, Sequence, TypedDict

from dotenv import load_dotenv

load_dotenv()

from langchain_core.documents import Document
from langchain_core.tools import BaseTool

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages
from alfred.services.langgraph_compat import ToolNode, tools_condition
from alfred.services.searxng_agent import search_web as searx_search
from pydantic import BaseModel, Field

try:  # pragma: no cover - optional dependency
    from langgraph.checkpoint.memory import MemorySaver
except Exception:  # pragma: no cover
    MemorySaver = None  # type: ignore

_MEMORY_SAVER = MemorySaver() if MemorySaver is not None else None

try:  # pragma: no cover - optional dependency
    from langchain_core.retrievers import BaseRetriever
except Exception:  # pragma: no cover
    class BaseRetriever:  # type: ignore[empty-body]
        """Fallback minimal retriever interface."""

        def invoke(self, query: str):  # type: ignore[override]
            return []

        async def ainvoke(self, query: str):  # type: ignore[override]
            return []


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

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

# Core system prompt
CORE_PROMPT = (
    "You are Ashwin’s writing & thinking copilot. Always write in FIRST PERSON (“I”, “my”, “we” when I explicitly include a team).\n"
    "Your #1 rule: answer directly in my voice first, then support it with evidence from the retrieved notes or web_search.\n"
    "Never invent facts. If info is missing, say “I don’t know based on my notes” and list what would help.\n\n"
    "VOICE & STYLE\n"
    "- Tone: crisp, confident, practical. Prefer short sentences and active voice.\n"
    "- Lead with the answer. Then give 3–6 specific bullets (evidence, impact, tech, trade-offs). Close with next steps if useful.\n"
    "- Avoid filler (“as an AI…”, “according to my knowledge…”). No fluff.\n\n"
    "GROUNDING & SOURCING\n"
    "- Use ONLY: (a) retrieved notes from my vector store; (b) web_search results when asked to research.\n"
    "- Inline attribution like (source: domain or note title). If quoting, keep it short and clearly attributed.\n"
    "- If sources disagree, call it out and explain my take.\n"
    "- If you used my resume/notes for personal facts, mention it briefly. (Example: “Based on my resume notes…”) \n\n"
    "STRICT FIRST-PERSON GUARANTEE\n"
    "- Before finalizing, re-read and replace any third-person phrasing about me (e.g., “Ashwin did…”) with first person (“I did…”).\n"
    "- If the user asks about me, do NOT switch to third person—stay in first person unless explicitly requested otherwise.\n\n"
    "SAFETY & HONESTY\n"
    "- Don’t guess numbers, dates, or names. If unsure, say so and propose how I’d verify.\n"
    "- Summarize sensitive content neutrally and avoid speculation about people’s motives.\n\n"
    "FORMAT\n"
    "- Start with a one-line thesis/answer.\n"
    "- Follow with concise bullets (facts, impact, decisions, metrics).\n"
    "- End with a tiny “Sources” line when you used references.\n"
)


def build_system_prompt(mode: str = "minimal") -> str:
    mode = (mode or "minimal").lower()
    prefix = ""
    if mode == "minimal":
        prefix = "Be ultra-concise (5–8 lines). Answer first in 1–2 lines, then bullets for evidence/impact. Same grounding and first-person rules.\n"
    elif mode == "concise":
        prefix = "Cap at ~120 words. Answer → 3 bullets → Sources. Same grounding and first-person rules.\n"
    elif mode == "formal":
        prefix = "Polished executive tone. Clear sections: Summary, Context, My Work/Decision, Outcome, Risks/Next Steps. Same grounding and first-person rules.\n"
    elif mode == "deep":
        prefix = "Thorough multi-section analysis with trade-offs and opposing views. Include assumptions and open questions. Same grounding and first-person rules.\n"
    elif mode == "interview":
        prefix = "Use STAR. First sentence = result metric. Then Situation, Task, Action, Result in 4 tight bullets. Same grounding and first-person rules.\n"
    # Combine prefix + core
    return (prefix + "\n" + CORE_PROMPT).strip()


# ------------------------ HELPERS ------------------------
def _load_env() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv()
    except Exception:
        pass


def make_llm(temperature: float = 0.2):
    _load_env()
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


class _SearxTool(BaseTool):  # pragma: no cover - HTTP-backed search tool
    name: str = "web_search"
    description: str = (
        "Search the public web via SearxNG. Provide a plain-language query. "
        "The tool returns JSON with fields title, url, snippet for the top results."
    )

    top_k: int = 5

    def _run(self, query: str) -> str:  # type: ignore[override]
        results = searx_search(query, num_results=self.top_k)
        simplified = []
        for item in results:
            simplified.append(
                {
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "snippet": item.get("content", "")[:240],
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

    # Always include the searx web search tool for richer sourcing
    tools.append(_SearxTool())

    return tools


# ------------------------ GRAPH NODES ------------------------
def generate_query_or_respond(state: AgentState, k: int = 4):
    tools = make_tools(k=k)
    llm = make_llm(temperature=0.0).bind_tools(tools)
    # Decide to call a tool (retrieve or web_search) or respond directly
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


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
    return {"messages": [{"role": "user", "content": response.content}]}


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
    return {"messages": [response]}


# ------------------------ GRAPH BUILD/EXEC ------------------------
def build_agent_graph(k: int = 4, mode: str = "minimal"):
    workflow = StateGraph(AgentState)

    workflow.add_node("generate_query_or_respond", lambda s: generate_query_or_respond(s, k=k))
    workflow.add_node("retrieve", ToolNode(make_tools(k=k)))
    workflow.add_node("rewrite_question", rewrite_question)
    workflow.add_node("generate_answer", lambda s: generate_answer(s, mode=mode))

    workflow.add_edge(START, "generate_query_or_respond")

    # Decide whether to retrieve or finish
    workflow.add_conditional_edges(
        "generate_query_or_respond",
        tools_condition,
        {
            "tools": "retrieve",
            END: END,
        },
    )

    workflow.add_conditional_edges("retrieve", grade_documents)
    workflow.add_edge("generate_answer", END)
    workflow.add_edge("rewrite_question", "generate_query_or_respond")

    if _MEMORY_SAVER is not None:
        return workflow.compile(checkpointer=_MEMORY_SAVER)
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
