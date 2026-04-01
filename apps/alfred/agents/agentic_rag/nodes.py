from __future__ import annotations

from collections.abc import Iterable
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from pydantic import BaseModel, Field

from alfred.agents.agentic_rag.state import AgentState
from alfred.core.llm_factory import get_chat_model
from alfred.prompts import load_prompt


def make_llm(*, temperature: float = 0.2):
    # NOTE: temperature parameter is ignored; model always uses cfg.llm_temperature
    # Kept for backward compatibility but no longer affects behavior
    return get_chat_model()


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


def generate_query_or_respond(state: AgentState, *, tools, k: int = 4):
    llm = make_llm(temperature=0.0).bind_tools(tools)
    response = llm.invoke(state["messages"])
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


def generate_answer(state: AgentState, *, mode: str = "minimal"):
    question = state["messages"][0].content
    context = state["messages"][-1].content
    system = build_system_prompt(mode)
    pro = (
        system
        + "\n\nTask: Answer the user in MY first-person voice.\n\n"
        + f"Question:\n{question}\n\n"
        + f"Context (retrieved notes + optional web_search):\n{context}\n\n"
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


def stream_final_answer(graph, question: str) -> Iterable[str]:
    final = ""
    for chunk in graph.stream({"messages": [HumanMessage(content=question)]}):
        for _node, update in chunk.items():
            try:
                msg = update["messages"][-1]
                if hasattr(msg, "content"):
                    final = msg.content
            except Exception:
                continue
    yield enforce_first_person(final)
