from typing import List
from crewai.tools import tool

@tool("web_search_tool")
def web_search_tool(query: str) -> List[str]:
    """Return a small list of URLs for a given query."""
    # TODO: wire a real search provider
    return [
        f"https://example.com/search?q={query}",
        f"https://another.example.com/?q={query}"
    ]

@tool("style_writer_tool")
def style_writer_tool(topic: str, bullets: List[str]) -> str:
    """Compose a short, bulleted briefing email for the given topic."""
    return f"Subject: {topic}\n\n" + "\n".join(f"- {b}" for b in bullets)
