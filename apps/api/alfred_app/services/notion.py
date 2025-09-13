from __future__ import annotations

from typing import Any, Optional
from notion_client import Client
from tenacity import retry, wait_exponential_jitter, stop_after_attempt
from fastapi import HTTPException

from alfred_app.core.config import settings


def _client() -> Client:
    if not settings.notion_token:
        raise HTTPException(500, "NOTION_TOKEN not configured")
    return Client(auth=settings.notion_token)


@retry(wait=wait_exponential_jitter(1, 5), stop=stop_after_attempt(5))
def create_simple_page(title: str, md: str):
    if not settings.notion_parent_page_id:
        raise HTTPException(500, "NOTION_PARENT_PAGE_ID not configured")
    parent = {"page_id": settings.notion_parent_page_id}
    return _client().pages.create(
        parent=parent,
        properties={"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        children=[
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{"type": "text", "text": {"content": md}}]
                },
            }
        ],
    )


def search(query: str, page_size: int = 25) -> dict:
    return _client().search(query=query, page_size=page_size)


def get_page(page_id: str) -> dict:
    return _client().pages.retrieve(page_id)


def list_block_children(block_id: str, page_size: int = 50) -> dict:
    return _client().blocks.children.list(block_id, page_size=page_size)


def query_database(db_id: str, filter: Optional[dict] = None, sorts: Optional[list] = None, page_size: int = 50) -> dict:
    payload: dict[str, Any] = {"page_size": page_size}
    if filter:
        payload["filter"] = filter
    if sorts:
        payload["sorts"] = sorts
    return _client().databases.query(db_id, **payload)


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
                lines.extend(_block_to_md(ch, depth + (1 if t in ("bulleted_list_item", "numbered_list_item", "to_do") else 0)))

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


def page_to_markdown(page_id: str) -> str:
    blocks = _collect_children_all(page_id)
    lines: list[str] = []
    for b in blocks:
        lines.extend(_block_to_md(b, depth=0))
    # Remove excessive trailing blank lines
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
