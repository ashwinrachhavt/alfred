"""Render Notion page blocks into Markdown.

This is intentionally "good enough" Markdown for Alfred ingestion:
- Preserves headings, lists, checkboxes, code blocks, quotes, callouts, and links.
- Avoids embedding Notion-hosted presigned file URLs (they expire); uses placeholders.

The importer fetches a full block tree (with `children`) so rendering does not
perform network calls.
"""

from __future__ import annotations

from typing import Any


class NotionMarkdownRenderer:
    """Convert Notion API objects (pages + blocks) into Markdown strings."""

    def page_title(self, page: dict[str, Any]) -> str:
        """Extract a human-readable title from a Notion page object."""

        properties = page.get("properties", {}) or {}
        for _name, prop in properties.items():
            if prop.get("type") == "title":
                fragments = prop.get("title", []) or []
                if fragments:
                    title = " ".join(f.get("plain_text", "") for f in fragments).strip()
                    if title:
                        return title
        return f"Untitled page ({page.get('id', 'unknown')})"

    def render_blocks(self, blocks: list[dict[str, Any]]) -> str:
        """Render a list of Notion blocks (with nested children) into Markdown."""

        lines: list[str] = []
        for block in blocks or []:
            lines.extend(self._block_to_lines(block, depth=0))
        return "\n".join(lines).rstrip()

    # ------------------------------
    # Internal rendering utilities
    # ------------------------------

    def _block_to_lines(self, block: dict[str, Any], *, depth: int) -> list[str]:
        indent = "  " * max(0, depth)
        t = block.get("type")
        data = block.get(t, {}) if t else {}
        lines: list[str] = []

        def children_lines() -> list[str]:
            out: list[str] = []
            for ch in block.get("children", []) or []:
                out.extend(
                    self._block_to_lines(
                        ch,
                        depth=depth
                        + (1 if t in ("bulleted_list_item", "numbered_list_item", "to_do") else 0),
                    )
                )
            return out

        if t == "paragraph":
            text = self._rich_text_to_md(data.get("rich_text", []))
            if text:
                lines.append(f"{indent}{text}")
            lines.append("")
            lines.extend(children_lines())
            return lines

        if t in ("heading_1", "heading_2", "heading_3"):
            level = {"heading_1": "#", "heading_2": "##", "heading_3": "###"}[t]
            text = self._rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{level} {text}".rstrip())
            lines.append("")
            lines.extend(children_lines())
            return lines

        if t == "bulleted_list_item":
            text = self._rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{indent}- {text}".rstrip())
            lines.extend(children_lines())
            return lines

        if t == "numbered_list_item":
            text = self._rich_text_to_md(data.get("rich_text", []))
            lines.append(f"{indent}1. {text}".rstrip())
            lines.extend(children_lines())
            return lines

        if t == "to_do":
            text = self._rich_text_to_md(data.get("rich_text", []))
            checked = bool(data.get("checked", False))
            mark = "x" if checked else " "
            lines.append(f"{indent}- [{mark}] {text}".rstrip())
            lines.extend(children_lines())
            return lines

        if t == "quote":
            text = self._rich_text_to_md(data.get("rich_text", []))
            for ln in text.splitlines() or [""]:
                lines.append(f"> {ln}".rstrip())
            lines.append("")
            lines.extend(children_lines())
            return lines

        if t == "code":
            lang = (data.get("language") or "").strip()
            text = self._rich_text_to_md(data.get("rich_text", []), in_code_block=True)
            lines.append(f"```{lang}".rstrip())
            lines.extend(text.splitlines() if text else [])
            lines.append("```")
            lines.append("")
            return lines

        if t == "callout":
            text = self._rich_text_to_md(data.get("rich_text", []))
            icon = ((data.get("icon") or {}) if isinstance(data, dict) else {}).get("emoji") or "💡"
            lines.append(f"> {icon} {text}".rstrip())
            lines.append("")
            lines.extend(children_lines())
            return lines

        if t == "divider":
            lines.append("---")
            lines.append("")
            return lines

        if t == "image":
            caption = self._rich_text_to_md(data.get("caption", []))
            if data.get("type") == "external":
                url = (data.get("external") or {}).get("url", "")
                if url:
                    lines.append(f"![{caption}]({url})".rstrip())
                else:
                    lines.append(f"[External Image] {caption}".rstrip())
            else:
                # Notion-hosted presigned URLs expire; don't persist them in markdown.
                lines.append(f"[Notion Image] {caption}".rstrip())
            lines.append("")
            return lines

        if t == "bookmark":
            url = (data.get("url") or "").strip()
            caption = self._rich_text_to_md(data.get("caption", []))
            label = caption or url
            if url:
                lines.append(f"[{label}]({url})".rstrip())
            elif label:
                lines.append(label)
            lines.append("")
            return lines

        if t == "embed":
            url = (data.get("url") or "").strip()
            if url:
                lines.append(url)
                lines.append("")
            lines.extend(children_lines())
            return lines

        if t == "toggle":
            text = self._rich_text_to_md(data.get("rich_text", []))
            lines.append(f"▶ {text}".rstrip())
            lines.append("")
            lines.extend(children_lines())
            return lines

        if t == "equation":
            expr = (data.get("expression") or "").strip()
            if expr:
                lines.append(f"${expr}$")
                lines.append("")
            return lines

        if t == "table":
            # Children should contain table_row blocks.
            rows: list[list[str]] = []
            for row in block.get("children", []) or []:
                if row.get("type") != "table_row":
                    continue
                cells = (row.get("table_row") or {}).get("cells", []) or []
                rows.append([self._rich_text_to_md(cell) for cell in cells])
            lines.extend(self._render_table(rows))
            lines.extend(children_lines())
            return lines

        if t in ("child_page", "child_database"):
            title = (data.get("title") or "").strip()
            if title:
                lines.append(f"{indent}- {title}".rstrip())
            lines.extend(children_lines())
            return lines

        # Fallback: try generic rich_text extraction.
        rich = data.get("rich_text") if isinstance(data, dict) else None
        text = self._rich_text_to_md(rich or [])
        if text:
            lines.append(f"{indent}{text}")
            lines.append("")
        lines.extend(children_lines())
        return lines

    def _render_table(self, rows: list[list[str]]) -> list[str]:
        if not rows:
            return []
        # Use first row as header for readability (Notion table headers are optional).
        header = rows[0]
        body = rows[1:]
        sep = ["---"] * len(header)

        out = [
            "| " + " | ".join(header) + " |",
            "| " + " | ".join(sep) + " |",
        ]
        for row in body:
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            out.append("| " + " | ".join(row[: len(header)]) + " |")
        out.append("")
        return out

    def _rich_text_to_md(
        self, rich_list: list[dict[str, Any]], *, in_code_block: bool = False
    ) -> str:
        def apply_annotations(text: str, ann: dict[str, Any]) -> str:
            if in_code_block:
                return text
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
            rt_type = rt.get("type")
            ann = rt.get("annotations", {}) or {}

            if rt_type == "text":
                t = rt.get("text", {}) or {}
                content = t.get("content", "")
                content = apply_annotations(content, ann)
                link = (t.get("link") or {}).get("url") or rt.get("href")
                if link and not in_code_block:
                    content = f"[{content}]({link})"
                parts.append(content)
                continue

            # Mentions/equations/etc: fall back to plain_text.
            plain = rt.get("plain_text", "")
            if plain:
                parts.append(apply_annotations(plain, ann))

        return "".join(parts).rstrip()


__all__ = ["NotionMarkdownRenderer"]
