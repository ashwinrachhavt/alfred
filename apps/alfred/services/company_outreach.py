from __future__ import annotations

import importlib.util
import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph

from alfred.core.dependencies import get_company_research_service
from alfred.core.settings import LLMProvider, settings
from alfred.prompts import load_prompt
from alfred.services.agentic_rag import create_retriever_tool, make_llm, make_retriever
from alfred.services.contact_discovery import discover_contacts
from alfred.services.web_search import search_web


def _summarize_company_report(doc: dict[str, Any]) -> str:
    report = doc.get("report") or {}
    lines: list[str] = []
    exec_summary = report.get("executive_summary")
    if exec_summary:
        lines.append(f"Executive summary:\n{exec_summary}")
    sections = report.get("sections") or []
    for section in sections:
        name = section.get("name", "Untitled section")
        summary = section.get("summary", "")
        insights = section.get("insights") or []
        lines.append(f"\n## {name}\n{summary}")
        for insight in insights:
            lines.append(f"- {insight}")
    if report.get("risks"):
        lines.append("\nRisks:")
        for item in report["risks"]:
            lines.append(f"- {item}")
    if report.get("opportunities"):
        lines.append("\nOpportunities:")
        for item in report["opportunities"]:
            lines.append(f"- {item}")
    if report.get("recommended_actions"):
        lines.append("\nRecommended actions:")
        for item in report["recommended_actions"]:
            lines.append(f"- {item}")
    if report.get("references"):
        lines.append("\nReferences:")
        for ref in report["references"]:
            lines.append(f"- {ref}")
    return "\n".join(lines).strip() or "(empty report)"


class CompanyResearchTool(BaseTool):
    name: str = "company_research"
    description: str = (
        "Call the in-house company research agent. Input should be the exact company name. "
        "It returns a structured research report covering mission, products, GTM, funding, and risks."
    )

    def _run(self, company: str) -> str:  # type: ignore[override]
        try:
            doc = get_company_research_service().generate_report(company)
            return _summarize_company_report(doc)
        except Exception as exc:  # pragma: no cover - propagate friendly error
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


def _use_stub_outreach() -> bool:
    if os.getenv("ALFRED_OUTREACH_STUB") == "1":
        return True
    if settings.app_env in {"test", "ci"}:
        return True
    if settings.llm_provider == LLMProvider.openai and not settings.openai_api_key:
        return True
    return False


def _stub_outreach(company: str, role: str, personal_context: str) -> Dict[str, Any]:
    summary = (
        f"Offline outreach kit for {company} ({role}). Set OPENAI_API_KEY or ALFRED_OLLAMA_* to "
        "enable live generation."
    )
    outreach_email = (
        f"Hi there — quick intro about {company}. I focus on AI product delivery and I'd love to "
        f"discuss how my background maps to {role}. Happy to share a concise portfolio and adapt to your needs."
    )
    return {
        "summary": summary,
        "positioning": [
            "Hands-on builder with AI product + growth experience",
            "Comfortable shipping quickly with small teams",
            f"Motivated by {company}'s roadmap and recent launches",
        ],
        "suggested_topics": [
            "Current AI/automation initiatives",
            "Team's biggest hiring priority",
            "Where quick experiments could move the needle",
        ],
        "outreach_email": outreach_email,
        "follow_up": [
            "Follow up in 5-7 days with one concrete idea",
            "Share a short Loom/demo tailored to their product",
        ],
        "sources": ["stub/offline"],
        "contacts": [],
        "personal_context": personal_context,
    }


def _normalize_contact(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(item.get("name") or "").strip(),
        "title": str(item.get("title") or "").strip(),
        "email": str(item.get("email") or "").strip(),
        "confidence": float(item.get("confidence") or 0.0),
        "source": str(item.get("source") or "unknown").strip() or "unknown",
    }


def _normalize_outreach_payload(raw: Dict[str, Any], company: str, role: str) -> Dict[str, Any]:
    base: Dict[str, Any] = {
        "summary": "",
        "positioning": [],
        "suggested_topics": [],
        "outreach_email": "",
        "follow_up": [],
        "sources": [],
        "contacts": [],
    }
    base.update(raw or {})

    if not base.get("summary"):
        base["summary"] = f"Outreach kit for {company} targeting {role}."

    for key in ("positioning", "suggested_topics", "follow_up", "sources"):
        val = base.get(key) or []
        base[key] = [str(x).strip() for x in val if str(x).strip()]

    email_text = str(base.get("outreach_email") or "").strip()
    if not email_text:
        email_text = base["summary"]
    base["outreach_email"] = email_text

    contacts_raw = base.get("contacts") or []
    normalized_contacts = []
    if isinstance(contacts_raw, list):
        for item in contacts_raw:
            if isinstance(item, dict):
                normalized_contacts.append(_normalize_contact(item))
    base["contacts"] = normalized_contacts

    if not base.get("sources"):
        base["sources"] = ["company_outreach"]

    return base


@lru_cache(maxsize=1)
def _load_resume_context() -> str:
    pdf_path = Path(__file__).resolve().parents[3] / "data" / "ashwin_rachha_resume.pdf"
    if not pdf_path.is_file():
        return ""

    # Use Docling if available; otherwise, skip resume context.
    if importlib.util.find_spec("docling") is None:
        return ""

    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except Exception:
        return ""

    options = PdfPipelineOptions(
        do_ocr=False,
        do_table_structure=False,
        force_backend_text=True,
    )
    converter = DocumentConverter(
        format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}
    )
    result = converter.convert(str(pdf_path))
    text = result.document.export_to_text().strip()

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
        return {"messages": [*state["messages"], planner.invoke(state["messages"])]}

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
        return {"messages": [*state["messages"], msg]}

    def tools_condition_local(state: OutreachState):
        msgs = state.get("messages", [])
        if not msgs:
            return END
        last = msgs[-1]
        if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
            return "tools"
        return END

    def tools_node(state: OutreachState):
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

    graph = StateGraph(OutreachState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("finalize", finalize_node)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition_local, {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)

    return graph.compile()


def generate_company_outreach(
    company: str,
    role: str = "AI Engineer",
    *,
    personal_context: str = "",
    k: int = 6,
) -> Dict[str, Any]:
    if _use_stub_outreach():
        return _stub_outreach(company, role, personal_context)

    resume_context = _load_resume_context()
    job_description_context = _load_job_description_context(company, role)
    contacts = discover_contacts(company)

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
        for chunk in graph.stream(
            {
                "messages": [
                    SystemMessage(content=OUTREACH_SYSTEM_PROMPT),
                    HumanMessage(content=seed),
                ]
            },
            config={"recursion_limit": 40},
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
            parsed["contacts"] = parsed.get("contacts") or contacts
            return _normalize_outreach_payload(parsed, company, role)
    except json.JSONDecodeError:
        pass

    return _normalize_outreach_payload({"summary": final_text, "contacts": contacts}, company, role)


class OutreachState(TypedDict):
    messages: list[BaseMessage]
