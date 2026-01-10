from __future__ import annotations


def _rt(
    text: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    link: str | None = None,
) -> dict:
    return {
        "type": "text",
        "text": {"content": text, "link": {"url": link} if link else None},
        "annotations": {
            "bold": bold,
            "italic": italic,
            "strikethrough": False,
            "underline": False,
            "code": code,
            "color": "default",
        },
        "plain_text": text,
        "href": link,
    }


def test_page_title_extraction() -> None:
    from alfred.services.notion_markdown import NotionMarkdownRenderer

    renderer = NotionMarkdownRenderer()
    page = {
        "id": "page-1",
        "properties": {
            "Name": {
                "type": "title",
                "title": [{"plain_text": "Command Center"}],
            }
        },
    }

    assert renderer.page_title(page) == "Command Center"


def test_markdown_renders_common_blocks() -> None:
    from alfred.services.notion_markdown import NotionMarkdownRenderer

    renderer = NotionMarkdownRenderer()
    blocks = [
        {
            "type": "heading_1",
            "heading_1": {"rich_text": [_rt("Hello")]},
            "children": [],
        },
        {
            "type": "paragraph",
            "paragraph": {"rich_text": [_rt("World", bold=True, link="https://example.com")]},
            "children": [],
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [_rt("Parent")]},
            "children": [
                {
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {"rich_text": [_rt("Child")]},
                    "children": [],
                }
            ],
        },
        {
            "type": "to_do",
            "to_do": {"rich_text": [_rt("Task")], "checked": True},
            "children": [],
        },
        {
            "type": "code",
            "code": {"rich_text": [_rt("print('hi')")], "language": "python"},
            "children": [],
        },
        {
            "type": "image",
            "image": {"type": "file", "caption": [_rt("caption")]},
            "children": [],
        },
    ]

    md = renderer.render_blocks(blocks)
    assert "# Hello" in md
    assert "[**World**](https://example.com)" in md
    assert "- Parent" in md
    assert "  - Child" in md
    assert "- [x] Task" in md
    assert "```python" in md
    assert "print('hi')" in md
    assert "[Notion Image] caption" in md


def test_markdown_renders_table() -> None:
    from alfred.services.notion_markdown import NotionMarkdownRenderer

    renderer = NotionMarkdownRenderer()
    blocks = [
        {
            "type": "table",
            "table": {},
            "children": [
                {
                    "type": "table_row",
                    "table_row": {"cells": [[_rt("A")], [_rt("B")]]},
                    "children": [],
                },
                {
                    "type": "table_row",
                    "table_row": {"cells": [[_rt("1")], [_rt("2")]]},
                    "children": [],
                },
            ],
        }
    ]

    md = renderer.render_blocks(blocks)
    assert "| A | B |" in md
    assert "| 1 | 2 |" in md
