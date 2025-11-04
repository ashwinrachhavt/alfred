"""Utilities for querying SearxNG to support research workflows."""

from __future__ import annotations

import logging
import os
from typing import List, Optional, TypedDict

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
            headers={"Accept": "application/json"},
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
load_dotenv()


__all__ = ["search_web", "SearchResult"]
