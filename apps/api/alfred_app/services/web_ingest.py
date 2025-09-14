from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
from urllib.parse import urlparse

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os


@dataclass
class Page:
    url: str
    title: str
    text: str


def fetch_crawl4ai(url: str) -> Page | None:
    try:
        from crawl4ai import WebCrawler  # type: ignore
    except Exception:
        return None
    try:
        crawler = WebCrawler()
        crawler.warmup()
        result = crawler.run(url=url, output="markdown", screenshot=False, bypass_cache=True)
        text = (getattr(result, "markdown", None) or getattr(result, "content", None) or "").strip()
        title = (getattr(result, "title", None) or getattr(result, "metadata", {}).get("title") or "")
        if not text:
            return None
        return Page(url=url, title=title or url, text=text)
    except Exception:
        return None


class FetchError(Exception):
    pass


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)


DOMAIN_DELAYS = {
    "scholar.google.com": 3.0,
    "ieeexplore.ieee.org": 3.0,
}
DEFAULT_DELAY = 1.0
_last_request: Dict[str, float] = {}


def _rate_limit(url: str) -> None:
    dom = urlparse(url).netloc
    delay = DOMAIN_DELAYS.get(dom, DEFAULT_DELAY)
    now = time.time()
    last = _last_request.get(dom, 0.0)
    wait = last + delay - now
    if wait > 0:
        time.sleep(wait)
    _last_request[dom] = time.time()


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=6.0),
    retry=retry_if_exception_type(FetchError),
    reraise=True,
)
def _http_get_with_retry(url: str) -> httpx.Response:
    headers = {
        "user-agent": UA,
        "accept-language": "en-US,en;q=0.9",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    _rate_limit(url)
    resp = httpx.get(url, timeout=30.0, follow_redirects=True, headers=headers)
    # Retry on 429/5xx
    if resp.status_code == 429 or resp.status_code >= 500:
        raise FetchError(f"{resp.status_code} {resp.reason_phrase}")
    resp.raise_for_status()
    return resp


def _domain_extract(url: str, html: str) -> Optional[Page]:
    """Best-effort domain-specific extraction for tricky sites."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        BeautifulSoup = None  # type: ignore

    netloc = urlparse(url).netloc
    if not BeautifulSoup:
        return None
    soup = BeautifulSoup(html, "html.parser")

    # arXiv abstracts
    if "arxiv.org" in netloc:
        title = None
        h = soup.select_one("h1.title")
        if h:
            title = h.get_text(" ", strip=True).replace("Title:", "").strip()
        if not title:
            og = soup.find("meta", {"property": "og:title"})
            title = og.get("content") if og else (soup.title.get_text(strip=True) if soup.title else url)
        abs_el = soup.select_one("blockquote.abstract")
        if abs_el:
            text = abs_el.get_text(" ", strip=True).replace("Abstract:", "").strip()
            return Page(url=url, title=title or url, text=text)
        return Page(url=url, title=title or url, text=soup.get_text(" ", strip=True))

    # IEEE Xplore: use citation_* meta tags
    if "ieeexplore.ieee.org" in netloc:
        title = None
        mtitle = soup.find("meta", {"name": "citation_title"})
        if mtitle:
            title = mtitle.get("content")
        abst = soup.find("meta", {"name": "citation_abstract"})
        if title or abst:
            text = (abst.get("content") if abst else "") or soup.get_text(" ", strip=True)
            return Page(url=url, title=(title or url), text=text)
        # Fallback to visible text
        return Page(url=url, title=(soup.title.get_text(strip=True) if soup.title else url), text=soup.get_text(" ", strip=True))

    # Kaggle profiles often have og:description
    if "kaggle.com" in netloc:
        ogd = soup.find("meta", {"property": "og:description"})
        title = (soup.title.get_text(strip=True) if soup.title else url)
        if ogd and ogd.get("content"):
            return Page(url=url, title=title, text=ogd.get("content"))
        return Page(url=url, title=title, text=soup.get_text(" ", strip=True))

    # Google Scholar profiles often load dynamically; pick meta description if present
    if "scholar.google.com" in netloc:
        md = soup.find("meta", {"name": "description"})
        title = (soup.title.get_text(strip=True) if soup.title else url)
        text = (md.get("content") if md else None) or soup.get_text(" ", strip=True)
        return Page(url=url, title=title, text=text)

    # Medium typically works fine with readability; but fallback to og:description
    if "medium.com" in netloc:
        ogd = soup.find("meta", {"property": "og:description"})
        if ogd and ogd.get("content"):
            title = (soup.title.get_text(strip=True) if soup.title else url)
            return Page(url=url, title=title, text=ogd.get("content"))

    return None


DOMAIN_BLOCKED = {"www.linkedin.com", "linkedin.com"}


def fetch_fallback(url: str) -> Page:
    netloc = urlparse(url).netloc
    if netloc in DOMAIN_BLOCKED or netloc.endswith("linkedin.com"):
        raise FetchError("domain blocks scraping (LinkedIn)")

    r = _http_get_with_retry(url)
    # Domain-specific extraction first
    dom = _domain_extract(url, r.text)
    if dom and dom.text.strip():
        return dom
    # Try readability pipeline, otherwise fallback to simple BS4 extraction
    try:
        from readability import Document  # type: ignore
        doc = Document(r.text)
        title = doc.short_title() or url
        html = doc.summary()
        from bs4 import BeautifulSoup  # type: ignore
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ")
        if text.strip():
            return Page(url=url, title=title, text=text)
    except Exception:
        try:
            from bs4 import BeautifulSoup  # type: ignore
            soup = BeautifulSoup(r.text, "html.parser")
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else url
            text = soup.get_text(" ", strip=True)
            return Page(url=url, title=title, text=text)
        except Exception:
            # Last resort: return raw text
            return Page(url=url, title=url, text=r.text)


def crawl_urls(urls: List[str]) -> List[Page]:
    pages, _ = crawl_urls_with_status(urls)
    return pages


def crawl_urls_with_status(urls: List[str]) -> Tuple[List[Page], List[Dict[str, Any]]]:
    pages: List[Page] = []
    errors: List[Dict[str, Any]] = []
    for u in urls:
        try:
            page = fetch_crawl4ai(u) or fetch_fallback(u)
            if page and page.text.strip():
                pages.append(page)
            else:
                errors.append({"url": u, "error": "empty content"})
        except Exception as e:
            errors.append({"url": u, "error": str(e)})
    return pages, errors


def chunk_pages(pages: List[Page], chunk_size: int, overlap: int) -> List[Tuple[str, str, dict]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", ", ", " "]
    )
    items: List[Tuple[str, str, dict]] = []
    for p in pages:
        chunks = splitter.split_text(p.text)
        for i, ch in enumerate(chunks):
            doc_id = hashlib.md5(f"{p.url}#{i}".encode()).hexdigest()
            meta = {"source": p.url, "title": p.title, "chunk": i}
            items.append((doc_id, ch, meta))
    return items


def upsert_items(items: List[Tuple[str, str, dict]], collection: str, embed_model: str) -> int:
    """Upsert documents into a persistent Chroma collection.

    Uses env CHROMA_PATH (default ./chroma_store) for persistence.
    """
    persist_dir = os.getenv("CHROMA_PATH", "./chroma_store")
    os.makedirs(persist_dir, exist_ok=True)
    emb = OpenAIEmbeddings(model=embed_model)
    vs = Chroma(
        collection_name=collection,
        persist_directory=persist_dir,
        embedding_function=emb,
    )
    texts = [t for (_, t, __) in items]
    metas = [m for (_, __, m) in items]
    ids = [i for (i, __, ___) in items]
    vs.add_texts(texts=texts, metadatas=metas, ids=ids)
    # Ensure data is flushed to disk
    try:
        vs.persist()
    except Exception:
        pass
    return len(items)
