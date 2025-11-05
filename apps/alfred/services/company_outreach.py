from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Dict, Optional, TypedDict
from uuid import uuid4

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import AnyMessage, add_messages

from alfred.prompts import load_prompt
from alfred.services.agentic_rag import create_retriever_tool, make_llm, make_retriever
from alfred.services.company_researcher import research_company
from alfred.services.langgraph_compat import ToolNode, tools_condition
from alfred.services.langgraph_runtime import get_checkpointer, get_store
from alfred.services.web_search import search_web


class CompanyResearchTool(BaseTool):
    name: str = "company_research"
    description: str = (
        "Call the in-house company research agent. Input should be the exact company name. "
        "It returns a long-form research report covering mission, products, GTM, funding, and risks."
    )

    def _run(self, company: str) -> str:  # type: ignore[override]
        try:
            return research_company(company)
        except Exception as exc:  # surface friendly error for the planner
            return f"(error) company research failed: {exc}"

    async def _arun(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return self._run(*args, **kwargs)


def make_tools(k: int = 6):
    retriever = create_retriever_tool(
        make_retriever(k=k),
        name="profile_search",
        description=(
            "Search Ashwin's personal notes and resume for background, accomplishments, and skills. "
            "Use this before drafting outreach or tailoring the pitch."
        ),
    )
    return [retriever, CompanyResearchTool()]


OUTREACH_SYSTEM_PROMPT = load_prompt("company_outreach", "system.md")
_FINAL_PROMPT_TEMPLATE = load_prompt("company_outreach", "final_template.md")
_SEED_PROMPT = load_prompt("company_outreach", "seed.md")


try:  # pragma: no cover - optional checkpointer
    _CHECKPOINTER = get_checkpointer()
except Exception as exc:  # pragma: no cover
    logging.getLogger(__name__).warning("Company outreach checkpointer disabled: %s", exc)
    _CHECKPOINTER = None

try:  # pragma: no cover - optional store
    _STORE = get_store()
except Exception as exc:  # pragma: no cover
    logging.getLogger(__name__).warning("Company outreach store unavailable: %s", exc)
    _STORE = None


@lru_cache(maxsize=1)
def _load_resume_context() -> str:
    pdf_path = Path(__file__).resolve().parents[3] / "data" / "ashwin_rachha_resume.pdf"
    if not pdf_path.is_file():
        return ""

    try:
        from docling.backend.docling_parse_v4_backend import DoclingParseV4DocumentBackend
        from docling.datamodel.base_models import InputFormat
        from docling.document_converter import DocumentConverter, FormatOption
        from docling.pipeline.standard_pdf_pipeline import PdfPipelineOptions, StandardPdfPipeline
    except Exception as exc:  # pragma: no cover - docling optional import guard
        return f"(resume parsing unavailable: {exc})"

    try:
        options = PdfPipelineOptions(
            do_ocr=False,
            do_table_structure=False,
            force_backend_text=True,
        )
        converter = DocumentConverter(
            format_options={
                InputFormat.PDF: FormatOption(
                    backend=DoclingParseV4DocumentBackend,
                    pipeline_cls=StandardPdfPipeline,
                    pipeline_options=options,
                )
            }
        )
        result = converter.convert(str(pdf_path))
        text = result.document.export_to_text().strip()
    except Exception as exc:  # pragma: no cover - docling runtime fallback
        return f"(resume parsing failed: {exc})"

    max_chars = 6000
    if len(text) > max_chars:
        return f"{text[:max_chars].rstrip()}...\n(truncated)"
    return text


def _format_job_search_results(hits: list[dict], *, limit: int = 5) -> str:
    if not hits:
        return ""

    formatted: list[str] = []
    for hit in hits[:limit]:
        title = (hit.get("title") or "Untitled").strip()
        url = (hit.get("url") or "").strip()
        snippet = (hit.get("snippet") or "").strip().replace("\n", " ")
        source = (hit.get("source") or "").strip()
        meta = f"{title}"
        if source and source.lower() not in url.lower():
            meta += f" [{source}]"
        if url:
            meta += f" | {url}"
        if snippet:
            meta += f"\n  {snippet}"
        formatted.append(meta)
    return "\n".join(formatted)


def _load_job_description_context(company: str, role: str) -> str:
    query = f"{company} {role} job description"
    try:
        result = search_web(query, mode="auto")
    except Exception as exc:  # pragma: no cover - network/runtime guard
        return f"(job search failed: {exc})"

    return _format_job_search_results(result.get("hits", []))


def build_company_outreach_graph(company: str, role: str, personal_context: str, k: int = 6):
    tools = make_tools(k=k)
    planner = make_llm(temperature=0.0).bind_tools(tools)

    def agent_node(state: OutreachState):
        return {"messages": [planner.invoke(state["messages"])]}

    def finalize_node(state: OutreachState):
        synth = make_llm(temperature=0.2)
        final_prompt = _FINAL_PROMPT_TEMPLATE.format(
            company=company,
            role=role,
            personal_context=personal_context or "(none provided)",
        )
        convo = [
            SystemMessage(content=OUTREACH_SYSTEM_PROMPT),
            *state["messages"],
            HumanMessage(content=final_prompt),
        ]
        msg = synth.invoke(convo)
        return {"messages": [msg]}

    graph = StateGraph(OutreachState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    compile_kwargs: Dict[str, Any] = {}
    if _CHECKPOINTER is not None:
        compile_kwargs["checkpointer"] = _CHECKPOINTER
    if _STORE is not None:
        compile_kwargs["store"] = _STORE

    return graph.compile(**compile_kwargs)


def generate_company_outreach(
    company: str,
    role: str = "AI Engineer",
    *,
    personal_context: str = "",
    k: int = 6,
) -> Dict[str, Any]:
    resume_context = _load_resume_context()
    job_description_context = _load_job_description_context(company, role)

    graph = build_company_outreach_graph(
        company=company, role=role, personal_context=personal_context, k=k
    )
    seed = _SEED_PROMPT
    if resume_context:
        seed += f"\n\n=== Resume (Docling parsed) ===\n{resume_context}"
    if job_description_context:
        seed += f"\n\n=== Job Description Search Highlights ===\n{job_description_context}"

    final_text: Optional[str] = None

    try:
        stream_config: Dict[str, Any] = {"recursion_limit": 40}
        if _CHECKPOINTER is not None:
            stream_config.setdefault("configurable", {})["thread_id"] = (
                f"company-outreach-{uuid4()}"
            )

        for chunk in graph.stream(
            {"messages": [SystemMessage(content=OUTREACH_SYSTEM_PROMPT), HumanMessage(content=seed)]},
            config=stream_config,
        ):
            for update in chunk.values():
                messages = update.get("messages")
                if not messages:
                    continue
                last = messages[-1]
                content = getattr(last, "content", None)
                if isinstance(content, str):
                    final_text = content
    except Exception as exc:
        final_text = json.dumps(
            {
                "summary": "Company outreach agent encountered an error.",
                "error": str(exc),
                "positioning": [],
                "suggested_topics": [],
                "outreach_email": "",
                "follow_up": [],
                "sources": [],
            }
        )

    if not final_text:
        raise RuntimeError("Failed to generate outreach content")

    try:
        parsed = json.loads(final_text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    return {"summary": final_text}


class OutreachState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
