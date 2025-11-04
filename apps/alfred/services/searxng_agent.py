"""
Searxng-powered web search agent for autocomplete suggestions.
Provides intelligent web search results for note-taking autocomplete.
"""

from __future__ import annotations

import logging
import os
from typing import List, TypedDict, Optional
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Configuration
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://localhost:8080")
SEARXNG_TIMEOUT = int(os.getenv("SEARXNG_TIMEOUT", "5"))
MAX_RESULTS = int(os.getenv("SEARXNG_MAX_RESULTS", "5"))


class SearchResult(TypedDict):
    """A single search result from Searxng."""
    title: str
    url: str
    content: str
    score: Optional[float]


class AutocompleteResult(TypedDict):
    """Autocomplete suggestion with context."""
    text: str
    source: str
    url: str
    snippet: str
    confidence: float


def search_web(query: str, num_results: int = MAX_RESULTS) -> List[SearchResult]:
    """
    Search the web using Searxng.

    Args:
        query: The search query
        num_results: Maximum number of results to return

    Returns:
        List of search results
    """
    try:
        params = {
            "q": query,
            "format": "json",
            "categories": "general",
            "language": "en",
        }

        response = requests.get(
            f"{SEARXNG_URL}/search",
            params=params,
            timeout=SEARXNG_TIMEOUT,
            headers={"Accept": "application/json"}
        )

        response.raise_for_status()
        data = response.json()

        results: List[SearchResult] = []
        for item in data.get("results", [])[:num_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "content": item.get("content", ""),
                "score": item.get("score"),
            })

        return results

    except requests.exceptions.Timeout:
        logger.warning(f"Searxng timeout for query: {query}")
        return []
    except requests.exceptions.RequestException as e:
        logger.error(f"Searxng request failed: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in search_web: {e}")
        return []


def get_autocomplete_suggestions(
    context: str,
    query: str,
    max_suggestions: int = 3
) -> List[AutocompleteResult]:
    """
    Get intelligent autocomplete suggestions based on context and query.

    Args:
        context: The surrounding text context (previous sentences)
        query: The partial query being typed
        max_suggestions: Maximum number of suggestions to return

    Returns:
        List of autocomplete suggestions with metadata
    """
    # If query is too short, don't search
    if len(query.strip()) < 3:
        return []

    # Combine context with query for better search results
    search_query = query
    if context:
        # Extract key terms from context (last 50 chars) to inform search
        context_terms = context[-50:].strip()
        if context_terms:
            search_query = f"{context_terms} {query}"

    # Search the web
    search_results = search_web(search_query, num_results=max_suggestions * 2)

    # Convert to autocomplete suggestions
    suggestions: List[AutocompleteResult] = []

    for idx, result in enumerate(search_results[:max_suggestions]):
        # Calculate confidence based on position and score
        base_confidence = 1.0 - (idx * 0.15)  # Decrease by position
        if result.get("score"):
            base_confidence = min(base_confidence, result["score"])

        # Extract a good snippet (first 150 chars of content)
        snippet = result.get("content", "")[:150]
        if len(result.get("content", "")) > 150:
            snippet += "..."

        suggestions.append({
            "text": result.get("title", ""),
            "source": extract_domain(result.get("url", "")),
            "url": result.get("url", ""),
            "snippet": snippet,
            "confidence": base_confidence,
        })

    return suggestions


def extract_domain(url: str) -> str:
    """Extract clean domain name from URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url


def format_suggestion_for_editor(suggestion: AutocompleteResult) -> str:
    """
    Format a suggestion for insertion into the editor.

    Returns:
        Formatted markdown text ready for insertion
    """
    title = suggestion["text"]
    url = suggestion["url"]
    snippet = suggestion["snippet"]

    # Format as markdown with link
    formatted = f"{title}"
    if snippet:
        formatted += f"\n{snippet}"
    if url:
        formatted += f"\n[Source]({url})"

    return formatted


def get_instant_facts(query: str) -> Optional[str]:
    """
    Get instant factual answers for common queries.
    Uses Searxng's answer feature if available.

    Args:
        query: The search query

    Returns:
        Instant answer if available, None otherwise
    """
    try:
        params = {
            "q": query,
            "format": "json",
        }

        response = requests.get(
            f"{SEARXNG_URL}/search",
            params=params,
            timeout=SEARXNG_TIMEOUT,
            headers={"Accept": "application/json"}
        )

        response.raise_for_status()
        data = response.json()

        # Check for instant answers
        answers = data.get("answers", [])
        if answers:
            return answers[0]

        # Check for infoboxes
        infoboxes = data.get("infoboxes", [])
        if infoboxes:
            content = infoboxes[0].get("content", "")
            if content:
                return content

        return None

    except Exception as e:
        logger.error(f"Error getting instant facts: {e}")
        return None
