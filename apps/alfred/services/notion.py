from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from notion_client import Client
from notion_client.errors import APIResponseError
from pydantic import BaseModel, ConfigDict
from tenacity import retry, stop_after_attempt, wait_exponential_jitter

from alfred.core.config import settings
from alfred.connectors.notion_history import NotionHistoryConnector


def _client() -> Client:
    if not settings.notion_token:
        raise HTTPException(500, "NOTION_TOKEN not configured")
    return Client(auth=settings.notion_token)


def _database_query(db_id: str, **payload: Any) -> dict:
    client = _client()
    query_fn = getattr(client.databases, "query", None)
    try:
        if callable(query_fn):
            try:
                return query_fn(database_id=db_id, **payload)
            except TypeError:
                # Older notion-client releases expect positional database_id
                return query_fn(db_id, **payload)  # type: ignore[misc]

        # Fallback for stripped-down builds: hit the REST endpoint directly.
        body = payload or None
        return client.request(
            path=f"databases/{db_id}/query",
            method="POST",
            body=body,
        )
    except APIResponseError as exc:  # bubble up clearer errors to HTTP clients
        status = getattr(exc, "status", None) or 502
        detail = getattr(exc, "message", None) or str(exc)
        raise HTTPException(status, detail) from exc


class NotionWriteInput(BaseModel):
    """Payload for creating or appending content in Notion."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = None
    page_id: str | None = None
    db_id: str | None = None
    parent_page_id: str | None = None
    title: str
    md: str


class NotionSyncInput(BaseModel):
    """Input for syncing database metadata from Notion."""

    model_config = ConfigDict(extra="forbid")

    profile_id: str | None = None
    db_id: str
    page_limit: int = 10


def _text_rich_text(text: str) -> Dict[str, Any]:
    return {"type": "text", "text": {"content": text}}


def _flush_paragraph(lines: List[str], blocks: List[Dict[str, Any]]) -> None:
    if not lines:
        return
    paragraph = "\n".join(lines).strip("\n")
    if paragraph:
        blocks.append(
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [_text_rich_text(paragraph)]},
            }
        )
    lines.clear()


def _flush_bullets(items: List[str], blocks: List[Dict[str, Any]]) -> None:
    if not items:
        return
    for item in items:
        blocks.append(
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [_text_rich_text(item)]},
            }
        )
    items.clear()


def _md_to_blocks(md: str) -> List[Dict[str, Any]]:
    """Convert a small markdown subset into Notion block payloads."""

    blocks: List[Dict[str, Any]] = []
    paragraph_lines: List[str] = []
    bullet_items: List[str] = []

    for raw in md.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        stripped = line.strip()

        if not stripped:
            _flush_bullets(bullet_items, blocks)
            _flush_paragraph(paragraph_lines, blocks)
            continue

        heading = None
        if stripped.startswith("# "):
            heading = ("heading_1", stripped[2:].strip())
        elif stripped.startswith("## "):
            heading = ("heading_2", stripped[3:].strip())
        elif stripped.startswith("### "):
            heading = ("heading_3", stripped[4:].strip())

        if heading:
            _flush_bullets(bullet_items, blocks)
            _flush_paragraph(paragraph_lines, blocks)
            level, content = heading
            blocks.append(
                {
                    "type": level,
                    level: {"rich_text": [_text_rich_text(content)]},
                }
            )
            continue

        if stripped.startswith("- ") or stripped.startswith("* "):
            _flush_paragraph(paragraph_lines, blocks)
            bullet_items.append(stripped[2:].strip())
            continue

        paragraph_lines.append(line)

    _flush_bullets(bullet_items, blocks)
    _flush_paragraph(paragraph_lines, blocks)
    return blocks


def _create_page_under_parent(parent_page_id: str, title: str, blocks: List[Dict[str, Any]]):
    return _client().pages.create(
        parent={"page_id": parent_page_id},
        properties={"title": {"title": [_text_rich_text(title)]}},
        children=blocks,
    )


def _create_page_in_db(db_id: str, title: str, blocks: List[Dict[str, Any]]):
    return _client().pages.create(
        parent={"database_id": db_id},
        properties={"Name": {"title": [_text_rich_text(title)]}},
        children=blocks,
    )


def _append_blocks(page_id: str, blocks: List[Dict[str, Any]]):
    if not blocks:
        return {"page_id": page_id, "status": "skipped", "reason": "no blocks"}
    return _client().blocks.children.append(block_id=page_id, children=blocks)


@retry(wait=wait_exponential_jitter(1, 5), stop=stop_after_attempt(5))
def write_to_notion(payload: NotionWriteInput) -> Dict[str, Any]:
    blocks = _md_to_blocks(payload.md)

    if payload.page_id:
        result = _append_blocks(payload.page_id, blocks)
        return {"mode": "append", "page_id": payload.page_id, "result": result}

    if payload.db_id:
        page = _create_page_in_db(payload.db_id, payload.title, blocks)
        return {"mode": "create_in_db", "page_id": page.get("id"), "result": page}

    parent = payload.parent_page_id or settings.notion_parent_page_id
    if not parent:
        raise HTTPException(400, "Provide parent_page_id or configure NOTION_PARENT_PAGE_ID")

    page = _create_page_under_parent(parent, payload.title, blocks)
    return {"mode": "create_under_parent", "page_id": page.get("id"), "result": page}


@retry(wait=wait_exponential_jitter(1, 5), stop=stop_after_attempt(5))
def create_simple_page(title: str, md: str):
    payload = NotionWriteInput(title=title, md=md)
    return write_to_notion(payload)["result"]


def sync_database(input: NotionSyncInput) -> Dict[str, Any]:
    page_size = max(1, min(100, input.page_limit))
    results = _database_query(input.db_id, page_size=page_size)
    pages = results.get("results", [])
    return {
        "count": len(pages),
        "pages": [{"id": page.get("id"), "url": page.get("url")} for page in pages],
        "next_cursor": results.get("next_cursor"),
        "has_more": results.get("has_more", False),
    }


def search(query: str, page_size: int = 25) -> dict:
    return _client().search(query=query, page_size=page_size)


def get_page(page_id: str) -> dict:
    return _client().pages.retrieve(page_id)


def list_block_children(block_id: str, page_size: int = 50) -> dict:
    return _client().blocks.children.list(block_id, page_size=page_size)


def query_database(
    db_id: str, filter: Optional[dict] = None, sorts: Optional[list] = None, page_size: int = 50
) -> dict:
    payload: dict[str, Any] = {"page_size": page_size}
    if filter:
        payload["filter"] = filter
    if sorts:
        payload["sorts"] = sorts
    return _database_query(db_id, **payload)


def list_clients() -> dict:
    if not settings.notion_clients_db_id:
        raise HTTPException(400, "NOTION_CLIENTS_DB_ID not configured")
    return query_database(settings.notion_clients_db_id)


def list_notes() -> dict:
    if settings.notion_notes_db_id:
        return query_database(settings.notion_notes_db_id)
    # Fallback: search for pages under parent page if database not set
    if not settings.notion_parent_page_id:
        raise HTTPException(400, "Set NOTION_NOTES_DB_ID or NOTION_PARENT_PAGE_ID")
    # Notion search cannot directly scope to a parent; return generic search for now
    return search(query="", page_size=25)


async def fetch_page_history(
    *,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    token: Optional[str] = None,
    limit: Optional[int] = None,
    include_content: bool = False,
) -> List[Dict[str, Any]]:
    """Fetch page histories using the async connector for deep exports."""

    notion_token = token or settings.notion_token
    if not notion_token:
        raise HTTPException(500, "NOTION_TOKEN not configured")

    async with NotionHistoryConnector(notion_token) as connector:
        return await connector.get_all_pages(
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            include_content=include_content,
        )


# Notion API rate limits: ~3 RPS avg; backoff handles 429s.


# ------------------------------
# Markdown conversion utilities
# ------------------------------


def _concat_rich_text(rich_list: list[dict]) -> str:
    def apply_annotations(text: str, ann: dict) -> str:
        # Order: code -> bold -> italic -> strikethrough; underline ignored
        if ann.get("code"):
            text = f"`{text}`"
        if ann.get("bold"):
            text = f"**{text}**"
        if ann.get("italic"):
            text = f"*{text}*"
        if ann.get("strikethrough"):
            text = f"~~{text}~~"
        return text

    parts: list[str] = []
    for rt in rich_list or []:
        t = rt.get("text", {})
        content = t.get("content", "")
        ann = rt.get("annotations", {}) or {}
        content = apply_annotations(content, ann)
        link = (t.get("link") or {}).get("url")
        if link:
            content = f"[{content}]({link})"
        parts.append(content)
    return "".join(parts).rstrip()


def _collect_children_all(block_id: str) -> list[dict]:
    """Fetch all children for a block, handling pagination."""
    items: list[dict] = []
    client = _client()
    cursor = None
    while True:
        kwargs = {"block_id": block_id, "page_size": 100}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.blocks.children.list(**kwargs)
        items.extend(resp.get("results", []))
        if not resp.get("has_more"):
            break
        cursor = resp.get("next_cursor")
        if not cursor:
            break
    return items


def _block_to_md(block: dict, depth: int = 0) -> list[str]:
    indent = "  " * depth
    t = block.get("type")
    data = block.get(t, {}) if t else {}
    lines: list[str] = []

    def handle_children():
        if block.get("has_children"):
            for ch in _collect_children_all(block["id"]):
                lines.extend(
                    _block_to_md(
                        ch,
                        depth
                        + (1 if t in ("bulleted_list_item", "numbered_list_item", "to_do") else 0),
                    )
                )

    if t in ("paragraph",):
        text = _concat_rich_text(data.get("rich_text", []))
        if text:
            lines.append(f"{indent}{text}")
        lines.append("")
        handle_children()
    elif t in ("heading_1", "heading_2", "heading_3"):
        level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[t]
        text = _concat_rich_text(data.get("rich_text", []))
        lines.append(f"{level} {text}".rstrip())
        lines.append("")
        handle_children()
    elif t == "bulleted_list_item":
        text = _concat_rich_text(data.get("rich_text", []))
        lines.append(f"{indent}- {text}".rstrip())
        handle_children()
    elif t == "numbered_list_item":
        text = _concat_rich_text(data.get("rich_text", []))
        lines.append(f"{indent}1. {text}".rstrip())
        handle_children()
    elif t == "to_do":
        text = _concat_rich_text(data.get("rich_text", []))
        checked = data.get("checked", False)
        mark = "x" if checked else " "
        lines.append(f"{indent}- [{mark}] {text}".rstrip())
        handle_children()
    elif t == "quote":
        text = _concat_rich_text(data.get("rich_text", []))
        for ln in text.splitlines() or [""]:
            lines.append(f"> {ln}")
        lines.append("")
        handle_children()
    elif t == "code":
        lang = data.get("language", "")
        text = _concat_rich_text(data.get("rich_text", []))
        lines.append(f"```{lang}".rstrip())
        lines.extend(text.splitlines())
        lines.append("```")
        lines.append("")
    elif t == "callout":
        text = _concat_rich_text(data.get("rich_text", []))
        icon = (data.get("icon") or {}).get("emoji") or "💡"
        lines.append(f"> {icon} {text}")
        lines.append("")
        handle_children()
    elif t == "divider":
        lines.append("---")
        lines.append("")
    elif t == "image":
        caption = _concat_rich_text(data.get("caption", []))
        if data.get("type") == "external":
            url = data.get("external", {}).get("url", "")
        else:
            url = data.get("file", {}).get("url", "")
        lines.append(f"![{caption}]({url})")
        lines.append("")
    elif t == "bookmark":
        url = data.get("url", "")
        caption = _concat_rich_text(data.get("caption", []))
        lines.append(f"[{caption or url}]({url})")
        lines.append("")
    else:
        # Fallback: try to render generic rich_text
        text = _concat_rich_text(data.get("rich_text", [])) if isinstance(data, dict) else ""
        if text:
            lines.append(f"{indent}{text}")
            lines.append("")
        handle_children()

    return lines


def fetch_database_as_markdown(database_id: str) -> str:
    """Fetch all pages and their block text as markdown from a Notion database."""
    try:
        results = _database_query(database_id, page_size=25)
        pages = results.get("results", [])
        markdown_sections: list[str] = []

        for p in pages:
            title_data = p["properties"].get("Name", {}).get("title", [])
            title = "".join(r["plain_text"] for r in title_data) or "(Untitled)"
            markdown_sections.append(f"# 🗒️ {title}")
            markdown_sections.append("")

            children = _collect_children_all(p["id"])
            for block in children:
                markdown_sections.extend(_block_to_md(block, depth=0))
            markdown_sections.append("\n" + "-" * 80 + "\n")

        return "\n".join(markdown_sections)
    except APIResponseError as e:
        return f"❌ Notion API error: {getattr(e, 'message', str(e))}"
    except Exception as e:
        return f"❌ Unexpected error while fetching Notion markdown: {e}"
