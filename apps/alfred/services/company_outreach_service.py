"""Company outreach feature implementation.

This is the canonical module for the "company outreach" feature.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, TypedDict

import requests
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from sqlmodel import Session, select

from alfred.connectors import ApolloClient, HunterClient
from alfred.core.database import get_session
from alfred.core.dependencies import get_company_research_service
from alfred.core.settings import LLMProvider, settings
from alfred.prompts import load_prompt
from alfred.schemas.outreach import OutreachContact, OutreachMessage, OutreachRun
from alfred.services.agentic_rag import create_retriever_tool, make_llm, make_retriever
from alfred.services.web_service import search_web

logger = logging.getLogger(__name__)


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


TARGET_TITLES = [
    "vp",
    "head",
    "director",
    "cto",
    "cpo",
    "engineering",
    "product",
    "ai",
]


@dataclass
class Contact:
    name: str
    title: str
    email: str
    confidence: float
    source: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "confidence": self.confidence,
            "source": self.source,
        }


class ContactProvider(str, Enum):
    """Supported contact discovery providers."""

    HUNTER = "hunter"
    APOLLO = "apollo"
    SNOV = "snov"


def _guess_domain(company: str) -> Optional[str]:
    slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
    if slug and "." not in slug:
        return f"{slug}.com"
    return slug or None


def _join_name(first: str | None, last: str | None) -> str:
    parts = [part.strip() for part in (first or "", last or "") if part and part.strip()]
    return " ".join(parts)


def _confidence_from_status(status: str | None) -> float:
    if not status:
        return 0.5
    status = status.lower()
    if status in {"verified", "deliverable"}:
        return 0.95
    if status in {"valid", "trusted"}:
        return 0.85
    if status in {"accept_all", "risky"}:
        return 0.65
    if status in {"webmail", "disposable"}:
        return 0.45
    if status in {"unknown"}:
        return 0.5
    if status in {"invalid", "undeliverable", "block", "blocked"}:
        return 0.1
    return 0.5


def _confidence_from_score(raw_score: Any) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def _merge_confidence(base: float, *, status: str | None = None, score: Any = None) -> float:
    candidates = [base]
    if score is not None:
        candidates.append(_confidence_from_score(score))
    if status:
        candidates.append(_confidence_from_status(status))
    return max(candidates)


class ContactDiscoveryService:
    """Aggregates contacts from Apollo, Hunter, and Snov (best-effort)."""

    def __init__(
        self,
        *,
        cache_path: str | None = None,
        cache_ttl_hours: int = 24,
        session: Session | None = None,
    ) -> None:
        self.cache_path = cache_path
        self.cache_ttl_hours = max(0, int(cache_ttl_hours))
        self.apollo_api_key = settings.apollo_api_key
        self.hunter_api_key = settings.hunter_api_key
        self.hunter_timeout_seconds = settings.hunter_timeout_seconds
        self.hunter_verify_top_n = settings.hunter_verify_top_n
        self.snov_client_id = settings.snov_client_id
        self.snov_client_secret = settings.snov_client_secret
        self.session = session

    def discover(
        self,
        company: str,
        *,
        limit: int = 20,
        providers: Sequence[ContactProvider] | None = None,
    ) -> list[dict[str, Any]]:
        company = (company or "").strip()
        if not company:
            return []

        domain = _guess_domain(company)
        contacts: list[Contact] = []

        selected = {p.value for p in providers} if providers else None
        if selected is None or ContactProvider.HUNTER.value in selected:
            contacts.extend(self._hunter_search(company, domain, limit=limit))
        if selected is None or ContactProvider.APOLLO.value in selected:
            contacts.extend(self._apollo_search(company, domain, limit=limit))
        if selected is None or ContactProvider.SNOV.value in selected:
            contacts.extend(self._snov_search(company, domain, limit=limit))

        deduped = self._dedupe_and_rank(contacts, limit=limit)
        payload = [c.model_dump() for c in deduped]
        self._log_run(company, source="fresh", contacts=payload)
        return payload

    def _hunter_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        api_key = self.hunter_api_key
        if not api_key:
            return []

        client = HunterClient(api_key=api_key, timeout_seconds=self.hunter_timeout_seconds)
        try:
            # Free email-count endpoint lets us skip paid lookups when no data exists.
            count = client.email_count(domain=domain, company=company)
            if count is not None:
                if count <= 0:
                    return []
                limit = min(limit, count)
        except Exception as exc:  # pragma: no cover - network path
            logger.debug("Hunter email-count check failed: %s", exc)

        try:
            emails = client.domain_search(domain=domain, company=company, limit=limit)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Hunter lookup failed: %s", exc)
            return []

        contacts: list[Contact] = []
        for item in emails:
            email = (item.get("value") or "").strip()
            if not email:
                continue
            verification = item.get("verification") or {}
            contact = Contact(
                name=_join_name(item.get("first_name"), item.get("last_name")),
                title=str(item.get("position") or ""),
                email=email,
                confidence=_merge_confidence(
                    float(item.get("confidence") or 0) / 100.0,
                    status=verification.get("status"),
                    score=verification.get("score"),
                ),
                source="hunter",
            )
            contacts.append(contact)

        if self.hunter_verify_top_n > 0:
            budget = min(self.hunter_verify_top_n, len(contacts))
            for contact in contacts[:budget]:
                try:
                    verification = client.verify_email(contact.email)
                except Exception as exc:  # pragma: no cover - network path
                    logger.debug("Hunter verification failed: %s", exc)
                    continue
                if not verification:
                    continue
                contact.confidence = _merge_confidence(
                    contact.confidence,
                    status=verification.get("status"),
                    score=verification.get("score"),
                )

        return contacts

    def _apollo_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        """Query Apollo using the supported api_search endpoint (free-plan safe)."""

        api_key = self.apollo_api_key
        if not api_key:
            return []

        payload: dict[str, Any] = {
            "page": 1,
            "per_page": max(1, min(limit, 100)),
            "person_titles": TARGET_TITLES,
            "person_seniorities": ["c-suite", "vp", "head", "director"],
        }
        if domain:
            payload["q_organization_domains"] = [domain]
        else:
            payload["q_organization_names"] = [company]

        client = ApolloClient(api_key=api_key, timeout_seconds=20)

        try:
            status, data = client.mixed_people_search(payload)
            if status >= 400:
                raise Exception(f"status {status}")
            return self._parse_apollo_people(data)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Apollo lookup failed: %s", exc)
            return []

    @staticmethod
    def _parse_apollo_people(data: dict[str, Any]) -> list[Contact]:
        people = data.get("people") or data.get("contacts") or []
        out: list[Contact] = []
        for p in people:
            email = (p.get("email") or p.get("email_personal") or "").strip()
            out.append(
                Contact(
                    name=str(p.get("name") or p.get("full_name") or "").strip(),
                    title=str(p.get("title") or ""),
                    email=email,
                    confidence=_confidence_from_status(p.get("email_status")),
                    source="apollo",
                )
            )
        return out

    def _snov_token(self) -> str | None:
        if not (self.snov_client_id and self.snov_client_secret):
            return None
        try:
            resp = requests.post(
                "https://api.snov.io/v1/oauth/access_token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.snov_client_id,
                    "client_secret": self.snov_client_secret,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return (resp.json() or {}).get("access_token")
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Snov token fetch failed: %s", exc)
            return None

    def _snov_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        token = self._snov_token()
        if not token:
            return []
        # Use lightweight domain emails endpoint; best-effort only.
        actual_domain = domain or _guess_domain(company)
        if not actual_domain:
            return []

        try:
            count = self._snov_domain_email_count(domain=actual_domain, token=token)
            if count is not None:
                if count <= 0:
                    return []
                limit = min(limit, count)
        except Exception as exc:  # pragma: no cover - network path
            logger.debug("Snov domain count lookup failed: %s", exc)

        try:
            start = requests.post(
                "https://api.snov.io/v2/domain-search/domain-emails/start",
                headers={"Authorization": f"Bearer {token}"},
                json={"domain": actual_domain, "limit": limit},
                timeout=15,
            )
            start.raise_for_status()
            task = (start.json() or {}).get("links", {}).get("result")
            if not task:
                return []
            result = requests.get(task, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            result.raise_for_status()
            emails = (result.json() or {}).get("data") or []
            out: list[Contact] = []
            for row in emails:
                email = (row.get("email") or "").strip()
                if not email:
                    continue
                out.append(
                    Contact(
                        name=str(row.get("name") or "").strip(),
                        title=str(row.get("position") or ""),
                        email=email,
                        confidence=0.6,
                        source="snov",
                    )
                )
            return out
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Snov lookup failed: %s", exc)
            return []

    def _snov_domain_email_count(self, domain: str, token: str) -> int | None:
        """Use the free Snov get-domain-emails-count endpoint before spending credits."""

        resp = requests.post(
            "https://api.snov.io/v1/get-domain-emails-count",
            data={"domain": domain, "access_token": token},
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json() or {}
        # Endpoint returns various shapes across docs; pick the first usable integer.
        for key in ("emails", "emails_count", "total", "count"):
            value = payload.get(key)
            if isinstance(value, dict):
                for nested in ("all", "total", "total_emails"):
                    nested_value = value.get(nested)
                    if isinstance(nested_value, (int, float)):
                        return int(nested_value)
            if isinstance(value, (int, float)):
                return int(value)
        return None

    def _dedupe_and_rank(self, contacts: Iterable[Contact], *, limit: int = 20) -> List[Contact]:
        seen: set[str] = set()
        cleaned: list[Contact] = []
        for contact in contacts:
            email_key = contact.email.lower().strip()
            if email_key and email_key in seen:
                continue
            if email_key:
                seen.add(email_key)
            cleaned.append(contact)

        cleaned.sort(key=lambda x: x.confidence, reverse=True)
        return cleaned[:limit]

    def _log_run(self, company: str, *, source: str, contacts: list[dict[str, Any]]) -> None:
        try:
            sess_ctx = self.session or next(get_session())
            with sess_ctx as db:
                run = OutreachRun(company=company, source=source, count=len(contacts))
                db.add(run)
                db.flush()
                rows = [
                    OutreachContact(
                        run_id=run.id or 0,
                        company=company,
                        name=str(contact.get("name", "")),
                        title=str(contact.get("title", "")),
                        email=str(contact.get("email", "")),
                        confidence=float(contact.get("confidence", 0.0)),
                        source=str(contact.get("source", "")),
                    )
                    for contact in contacts
                ]
                db.add_all(rows)
                db.commit()
        except Exception:
            logger.debug("Failed to log outreach run", exc_info=True)


def _row_to_dict(contact: OutreachContact) -> dict[str, Any]:
    return {
        "name": contact.name,
        "title": contact.title,
        "email": contact.email,
        "confidence": contact.confidence,
        "source": contact.source,
    }


class OutreachService:
    """Handles contact discovery caching and outbound outreach message logging/sending."""

    def __init__(self, *, session: Session | None = None) -> None:
        self.session = session

    # -------- contacts --------
    def list_contacts(
        self,
        company: str,
        *,
        limit: int = 20,
        role_filter: str | None = None,
        refresh: bool = False,
        providers: Sequence[ContactProvider] | None = None,
    ) -> list[dict[str, Any]]:
        if not refresh:
            cached = self._get_cached_contacts(
                company, role_filter=role_filter, limit=limit, providers=providers
            )
            if cached:
                return cached

        contacts = ContactDiscoveryService(session=self.session).discover(
            company, limit=limit, providers=providers
        )
        if role_filter:
            role_l = role_filter.lower()
            contacts = [c for c in contacts if role_l in (c.get("title") or "").lower()]
        return contacts[:limit]

    def _get_cached_contacts(
        self,
        company: str,
        *,
        role_filter: str | None,
        limit: int,
        providers: Sequence[ContactProvider] | None,
    ) -> list[dict[str, Any]]:
        ttl_hours = max(0, int(getattr(settings, "outreach_cache_ttl_hours", 0)))
        cutoff = (dt.datetime.utcnow() - dt.timedelta(hours=ttl_hours)) if ttl_hours > 0 else None
        selected = {p.value for p in providers} if providers else None

        sess_ctx = self.session or next(get_session())
        with sess_ctx as db:
            stmt = select(OutreachContact).where(OutreachContact.company == company)
            if cutoff is not None:
                stmt = stmt.where(OutreachContact.created_at >= cutoff)
            stmt = stmt.order_by(OutreachContact.confidence.desc()).limit(limit * 2)
            rows: Iterable[OutreachContact] = db.exec(stmt).all()
            if not rows:
                return []
            items = [_row_to_dict(row) for row in rows]
            if selected is not None:
                items = [
                    contact
                    for contact in items
                    if (contact.get("source") or "").lower().strip() in selected
                ]
            if role_filter:
                role_l = role_filter.lower()
                items = [c for c in items if role_l in (c.get("title") or "").lower()]
            return items[:limit]

    # -------- sending --------
    def send_email(
        self,
        *,
        company: str,
        contact_email: str,
        subject: str,
        body: str,
        contact_name: str = "",
        contact_title: str = "",
        dry_run: bool = False,
    ) -> OutreachMessage:
        message = OutreachMessage(
            company=company,
            contact_email=contact_email,
            contact_name=contact_name,
            contact_title=contact_title,
            subject=subject,
            body=body,
            provider="smtp",
            status="queued",
            meta={"dry_run": dry_run},
        )

        sess_ctx = self.session or next(get_session())
        with sess_ctx as db:
            db.add(message)
            db.flush()

            should_send = (
                settings.outreach_send_enabled
                and not dry_run
                and settings.smtp_host
                and settings.smtp_from_email
            )
            if should_send:
                try:
                    self._send_via_smtp(
                        to_email=contact_email,
                        subject=subject,
                        body=body,
                        reply_to=settings.smtp_from_email,
                    )
                    message.status = "sent"
                    message.sent_at = dt.datetime.utcnow()
                except Exception as exc:  # pragma: no cover - network path
                    logger.warning("SMTP send failed: %s", exc)
                    message.status = "failed"
                    message.error_message = str(exc)
            else:
                message.status = "skipped"
                message.error_message = message.error_message or "sending disabled or dry_run"

            db.add(message)
            db.commit()
            db.refresh(message)
            return message

    def _send_via_smtp(self, *, to_email: str, subject: str, body: str, reply_to: str) -> None:
        msg = EmailMessage()
        msg["From"] = reply_to
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = reply_to
        msg.set_content(body)

        host = settings.smtp_host
        port = settings.smtp_port
        if not host:
            raise RuntimeError("SMTP_HOST not configured")

        server = smtplib.SMTP(host, port, timeout=20)
        try:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:  # pragma: no cover - best effort cleanup
                pass


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

    contacts: list[dict[str, Any]] = []
    try:
        contacts = OutreachService().list_contacts(
            company, limit=20, role_filter=None, refresh=False
        )
    except Exception:
        contacts = []

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
