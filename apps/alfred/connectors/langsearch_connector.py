import json
import requests
from tinydb import TinyDB, Query
from IPython.display import display, Markdown
from textwrap import shorten
from urllib.parse import urlparse

DEFAULT_BASE_URL = Config.BASE_URL
DEFAULT_DB_PATH  = Config.DB_PATH


def _safe(s: str | None, fallback: str = "") -> str:
    return (s or fallback).strip()


def _pretty_host(u: str | None) -> str:
    if not u:
        return ""
    try:
        host = urlparse(u).netloc
        return host.replace("www.", "")
    except Exception:
        return ""


class LangSearchClient:
    def __init__(self, api_key: str, db_path: str = DEFAULT_DB_PATH, endpoint: str | None = DEFAULT_BASE_URL):
        """
        Initialize client with API key, TinyDB path, and optional endpoint override.
        """
        if endpoint is None:
            raise ValueError("Missing BASE_URL. Pass endpoint=... or define Config.BASE_URL.")
        self.api_key = api_key
        self.db = TinyDB(db_path)
        self.endpoint = endpoint

    def search(self, query: str, count: int = 10, freshness: str = "noLimit", summary: bool = True):
        payload = {
            "query": query,
            "count": count,
            "freshness": freshness,
            "summary": summary,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        r = requests.post(self.endpoint, headers=headers, json=payload, timeout=45)
        if r.status_code != 200:
            raise RuntimeError(f"API error {r.status_code}: {r.text}")

        data = r.json()
        results = data.get("data", {}).get("webPages", {}).get("value", []) or []
        if not results:
            print("No results found.")
            return []

        entries = []
        for res in results:
            record = {
                "query": query,
                "name": _safe(res.get("name"), "Untitled Result"),
                "url": _safe(res.get("url")),
                "displayUrl": _safe(res.get("displayUrl"), _safe(res.get("url"))),
                "snippet": _safe(res.get("snippet")),
                "summary": _safe(res.get("summary")),
            }
            self.db.insert(record)
            entries.append(record)

        print(f"Stored {len(entries)} results for '{query}'")
        return entries

    def display_results(self, query: str, limit: int = 10, show_snippet: bool = True, show_summary: bool = True):
        """
        Display stored search results in clean, structured Markdown.
        - Renders once (no duplicate prints)
        - Handles empty fields gracefully
        - Truncates very long summaries
        """
        Q = Query()
        rows = self.db.search(Q.query == query)
        if not rows:
            print(f"No stored results found for '{query}'.")
            return

        rows = sorted(rows, key=lambda r: (r.get("name") or "", r.get("url") or ""))[:limit]

        md = []
        md.append(f"# 🔍 Results for **{query}**")
        md.append("")
        md.append(f"*Showing {len(rows)} stored result(s).*")
        md.append("")

        for i, r in enumerate(rows, 1):
            title = _safe(r.get("name"), "Untitled Result")
            url = _safe(r.get("url"))
            durl = _safe(r.get("displayUrl"), url)
            host = _pretty_host(url)
            snippet = _safe(r.get("snippet"))
            summary = _safe(r.get("summary"))


            md.append(f"---")
            md.append(f"### {i}. [{title}]({url})")
            if host:
                md.append(f"*{host}*  ")
            else:
                md.append("")

            if url:
                md.append(f"**🌐 URL:** [{durl}]({url})")
            else:
                md.append("**🌐 URL:** _(missing)_")

            if show_snippet and snippet:
                md.append("")
                md.append("**Snippet**")
                md.append(f"> {snippet}")

            if show_summary and summary:
                md.append("")
                md.append("**Summary**")
                md.append(f"> {summary}")

            md.append("")

        display(Markdown("\n".join(md)))

    def clear(self):
        self.db.truncate()
        print("🧹 Database cleared.")

    def list_queries(self):
        return sorted({r.get("query") for r in self.db.all() if r.get("query")})
