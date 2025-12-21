from __future__ import annotations

import html
import time
from dataclasses import dataclass
from typing import Any

from alfred.prompts import load_prompt
from alfred.schemas.brand import (
    ExperienceInventory,
    InventoryRequest,
    OutreachRequest,
    OutreachResponse,
    PortfolioModel,
    StarStory,
    StoriesRequest,
    StoriesResponse,
)
from alfred.services.agentic_rag import get_context_chunks
from alfred.services.company_researcher import CompanyResearchService
from alfred.services.llm_service import LLMService

_SYSTEM = load_prompt("personal_brand", "system.md")
_INVENTORY = load_prompt("personal_brand", "inventory.md")
_STORIES = load_prompt("personal_brand", "stories.md")
_OUTREACH = load_prompt("personal_brand", "outreach.md")
_PORTFOLIO = load_prompt("personal_brand", "portfolio.md")


def _join_nonempty(*parts: str) -> str:
    return "\n\n".join(p.strip() for p in parts if (p or "").strip()).strip()


def _kb_context(query: str, *, k: int) -> str:
    try:
        chunks = get_context_chunks(query, k=k)
    except Exception:
        return ""
    lines: list[str] = []
    for idx, item in enumerate(chunks, start=1):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        title = (item.get("title") or "").strip()
        source = (item.get("source") or "").strip()
        meta = " | ".join(x for x in [title, source] if x)
        header = f"[KB {idx}] {meta}".strip()
        lines.append(header)
        lines.append(text)
        lines.append("")
    return "\n".join(lines).strip()


def build_experience_inventory(payload: InventoryRequest) -> ExperienceInventory:
    provided = _join_nonempty(
        f"=== Resume ===\n{payload.resume_text}" if payload.resume_text.strip() else "",
        f"=== LinkedIn ===\n{payload.linkedin_text}" if payload.linkedin_text.strip() else "",
        f"=== GitHub ===\n{payload.github_text}" if payload.github_text.strip() else "",
        f"=== Projects ===\n{payload.projects_text}" if payload.projects_text.strip() else "",
        f"=== Extra Context ===\n{payload.extra_context}" if payload.extra_context.strip() else "",
    )
    retrieved = (
        "" if provided else _kb_context("resume projects impact skills technologies", k=payload.k)
    )
    context = _join_nonempty(provided, retrieved)

    if not context:
        return ExperienceInventory(
            headline="AI Engineer",
            highlights=[],
            skills=[],
            technologies=[],
            experiences=[],
        )

    return LLMService().structured(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _join_nonempty(_INVENTORY, f"=== Context ===\n{context}")},
        ],
        schema=ExperienceInventory,
    )


def generate_star_stories(payload: StoriesRequest) -> StoriesResponse:
    if not payload.job_description.strip():
        raise ValueError("job_description is required")

    inv = build_experience_inventory(
        InventoryRequest(
            resume_text=payload.resume_text,
            linkedin_text=payload.linkedin_text,
            github_text=payload.github_text,
            projects_text=payload.projects_text,
            extra_context=payload.extra_context,
            k=payload.k,
        )
    )

    if not inv.experiences and not (
        payload.resume_text or payload.linkedin_text or payload.github_text
    ):
        raise ValueError(
            "No profile context found. Provide resume/linkedin/github text or ingest your profile into the KB."
        )

    return LLMService().structured(
        [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": _join_nonempty(
                    _STORIES,
                    f"=== Job Description ===\n{payload.job_description.strip()}",
                    f"=== Inventory JSON ===\n{inv.model_dump_json()}",
                ),
            },
        ],
        schema=StoriesResponse,
    )


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
    for key, label in (
        ("risks", "Risks"),
        ("opportunities", "Opportunities"),
        ("recommended_actions", "Recommended actions"),
    ):
        items = report.get(key) or []
        if items:
            lines.append(f"\n{label}:")
            for item in items:
                lines.append(f"- {item}")
    return "\n".join(lines).strip() or "(empty report)"


def generate_outreach(payload: OutreachRequest) -> OutreachResponse:
    company = (payload.company or "").strip()
    if not company:
        raise ValueError("company is required")

    inv = build_experience_inventory(
        InventoryRequest(
            resume_text=payload.resume_text,
            linkedin_text=payload.linkedin_text,
            github_text=payload.github_text,
            projects_text=payload.projects_text,
            extra_context=payload.extra_context,
            k=payload.k,
        )
    )
    if not (inv.experiences or inv.highlights or inv.skills or inv.technologies):
        raise ValueError(
            "No profile context found. Provide resume/linkedin/github text to /api/brand/inventory or ingest your profile into the KB."
        )
    stories: list[StarStory] = []
    if payload.job_description.strip():
        try:
            stories_resp = generate_star_stories(
                StoriesRequest(
                    job_description=payload.job_description,
                    resume_text=payload.resume_text,
                    linkedin_text=payload.linkedin_text,
                    github_text=payload.github_text,
                    projects_text=payload.projects_text,
                    extra_context=payload.extra_context,
                    k=payload.k,
                )
            )
            stories = stories_resp.stories
        except Exception:
            stories = []

    company_report = ""
    sources: list[str] = []
    try:
        doc = CompanyResearchService().generate_report(company)
        company_report = _summarize_company_report(doc)
        try:
            refs = (doc.get("report") or {}).get("references") or []
            sources.extend([str(x) for x in refs if x])
        except Exception:
            pass
    except Exception:
        company_report = ""

    kb_company = _kb_context(f"{company} products mission AI", k=min(8, payload.k))
    if kb_company:
        sources.append("personal_kb")

    recipient_line = ""
    if payload.recipient_name.strip() or payload.recipient_title.strip():
        recipient_line = (
            f"Recipient: {payload.recipient_name.strip()} ({payload.recipient_title.strip()})"
        ).strip()

    prompt = _join_nonempty(
        _OUTREACH,
        f"Company: {company}",
        f"Role: {payload.role.strip() if payload.role else 'AI Engineer'}",
        recipient_line,
        f"Channel: {payload.channel}",
        f"=== Company Research Summary ===\n{company_report}" if company_report else "",
        f"=== Job Description ===\n{payload.job_description.strip()}"
        if payload.job_description
        else "",
        f"=== Best-Fit Stories JSON ===\n{StoriesResponse(stories=stories).model_dump_json()}",
        f"=== Inventory JSON ===\n{inv.model_dump_json()}",
        f"=== Additional KB Context ===\n{kb_company}" if kb_company else "",
    )

    resp = LLMService().structured(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
        schema=OutreachResponse,
    )

    # Merge sources (LLM may include its own list; ensure it's present and stable)
    merged_sources = list(dict.fromkeys([*(resp.sources or []), *sources]))
    linkedin_message = (resp.linkedin_message or "").strip()
    if len(linkedin_message) > 300:
        linkedin_message = linkedin_message[:297].rstrip() + "..."
    return resp.model_copy(update={"sources": merged_sources, "linkedin_message": linkedin_message})


def generate_portfolio_model(inv: ExperienceInventory) -> PortfolioModel:
    return LLMService().structured(
        [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": _join_nonempty(_PORTFOLIO, inv.model_dump_json())},
        ],
        schema=PortfolioModel,
    )


def render_portfolio_html(
    model: PortfolioModel, *, inventory: ExperienceInventory | None = None
) -> str:
    title = html.escape(model.title)
    tagline = html.escape(model.tagline)
    about = html.escape(model.about)

    def _ul(items: list[str]) -> str:
        safe = [f"<li>{html.escape(x)}</li>" for x in (items or []) if (x or "").strip()]
        return "<ul>" + "".join(safe) + "</ul>" if safe else "<p class='muted'>—</p>"

    inv_block = ""
    if inventory and inventory.highlights:
        inv_block = "<section><h2>Highlights</h2>" + _ul(inventory.highlights) + "</section>"

    generated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title}</title>
  <style>
    :root {{
      --bg: #0b1020;
      --card: rgba(255,255,255,0.06);
      --text: rgba(255,255,255,0.92);
      --muted: rgba(255,255,255,0.68);
      --accent: #60a5fa;
      --border: rgba(255,255,255,0.12);
      --shadow: 0 10px 30px rgba(0,0,0,0.35);
      --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
      --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, "Apple Color Emoji", "Segoe UI Emoji";
    }}
    html, body {{ background: radial-gradient(1200px 700px at 10% 10%, rgba(96,165,250,0.18), transparent 60%), var(--bg); color: var(--text); font-family: var(--sans); }}
    a {{ color: var(--accent); text-decoration: none; }}
    .wrap {{ max-width: 960px; margin: 0 auto; padding: 48px 20px; }}
    header {{ padding: 28px 28px; border: 1px solid var(--border); border-radius: 16px; background: var(--card); box-shadow: var(--shadow); }}
    h1 {{ margin: 0; font-size: 34px; letter-spacing: -0.02em; }}
    .tagline {{ margin-top: 10px; font-size: 16px; color: var(--muted); }}
    .about {{ margin-top: 18px; font-size: 16px; line-height: 1.55; }}
    section {{ margin-top: 22px; padding: 22px 22px; border: 1px solid var(--border); border-radius: 16px; background: rgba(255,255,255,0.04); }}
    h2 {{ margin: 0 0 10px 0; font-size: 18px; letter-spacing: -0.01em; }}
    ul {{ margin: 10px 0 0 0; padding-left: 18px; color: var(--text); }}
    li {{ margin: 6px 0; }}
    .muted {{ color: var(--muted); }}
    footer {{ margin-top: 24px; color: var(--muted); font-size: 12px; }}
    code {{ font-family: var(--mono); font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>{title}</h1>
      <div class="tagline">{tagline}</div>
      <div class="about">{about}</div>
    </header>

    {inv_block}

    <section>
      <h2>Featured Projects</h2>
      {_ul(model.featured_projects)}
    </section>
    <section>
      <h2>Publications</h2>
      {_ul(model.publications)}
    </section>
    <section>
      <h2>Talks</h2>
      {_ul(model.talks)}
    </section>
    <section>
      <h2>Articles</h2>
      {_ul(model.articles)}
    </section>

    <footer>
      Generated by Alfred • <span class="muted">last update</span> <code>{generated_at}</code>
    </footer>
  </div>
</body>
</html>"""


@dataclass
class PortfolioCache:
    html: str
    generated_at_s: float


_PORTFOLIO_CACHE: PortfolioCache | None = None


def get_portfolio_html(*, refresh: bool = False) -> str:
    global _PORTFOLIO_CACHE
    ttl_s = 5 * 60
    now = time.time()
    if not refresh and _PORTFOLIO_CACHE and (now - _PORTFOLIO_CACHE.generated_at_s) < ttl_s:
        return _PORTFOLIO_CACHE.html

    try:
        inv = build_experience_inventory(InventoryRequest(k=14))
        model = generate_portfolio_model(inv)
        html_str = render_portfolio_html(model, inventory=inv)
        _PORTFOLIO_CACHE = PortfolioCache(html=html_str, generated_at_s=now)
        return html_str
    except Exception as exc:
        # Render a friendly fallback page so /ai stays useful even when LLM/KB is unconfigured.
        msg = html.escape(str(exc))
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Portfolio • Alfred</title>
  <style>
    :root {{ --bg:#0b1020; --text:rgba(255,255,255,0.92); --muted:rgba(255,255,255,0.68); --border:rgba(255,255,255,0.12); --card:rgba(255,255,255,0.06); }}
    html,body {{ background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial; }}
    .wrap {{ max-width: 860px; margin: 0 auto; padding: 48px 20px; }}
    .card {{ border: 1px solid var(--border); border-radius: 16px; background: var(--card); padding: 22px; }}
    h1 {{ margin: 0 0 10px 0; font-size: 22px; }}
    p {{ margin: 8px 0; color: var(--muted); line-height: 1.5; }}
    code {{ color: var(--text); }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Portfolio generation isn’t configured yet</h1>
      <p>To enable the auto-generated portfolio, configure an LLM provider (e.g. <code>OPENAI_API_KEY</code>) and ingest your profile into Alfred’s knowledge base.</p>
      <p>Error: <code>{msg}</code></p>
      <p>Try: <code>POST /api/brand/inventory</code> (with resume/linkedin/github text) and refresh this page.</p>
    </div>
  </div>
</body>
</html>"""
