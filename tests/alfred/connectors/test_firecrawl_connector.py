from __future__ import annotations

from unittest.mock import Mock

from alfred.connectors.firecrawl_connector import FirecrawlClient


def test_firecrawl_response_extracts_metadata() -> None:
    client = FirecrawlClient()
    response = Mock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = {
        "success": True,
        "data": {
            "markdown": "# Title",
            "html": "<article>Title</article>",
            "metadata": {"title": "Title", "sourceURL": "https://example.com"},
        },
    }

    unwrapped = client._unwrap_firecrawl(response)

    assert unwrapped.success is True
    assert unwrapped.markdown == "# Title"
    assert unwrapped.html == "<article>Title</article>"
    assert unwrapped.metadata == {"title": "Title", "sourceURL": "https://example.com"}


def test_scrape_rich_requests_markdown_and_html(monkeypatch) -> None:
    captured: dict = {}
    client = FirecrawlClient(base_url="http://firecrawl.test/v1")

    def fake_post(endpoint: str, payload: dict):
        captured["endpoint"] = endpoint
        captured["payload"] = payload
        return "ok"

    monkeypatch.setattr(client, "post", fake_post)

    assert client.scrape_rich("https://example.com/post") == "ok"
    assert captured == {
        "endpoint": "/scrape",
        "payload": {
            "url": "https://example.com/post",
            "formats": ["markdown", "html"],
            "render_js": False,
        },
    }
