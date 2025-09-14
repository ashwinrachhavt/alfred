#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List, Iterable
from hashlib import md5

from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_qdrant import QdrantVectorStore
from langchain_community.document_loaders import RecursiveUrlLoader

from dotenv import load_dotenv
load_dotenv()

# Ensure a reasonable default User-Agent to avoid warnings and improve acceptance
os.environ.setdefault(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; AlfredBot/1.0; +https://github.com/alfred)"
)


ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

# Note: per request, use WebBaseLoader/RecursiveUrlLoader instead of custom crawler

# ---- Defaults (you can keep your STATIC_URLS here) ----
STATIC_URLS: List[str] = [
    "https://ashwinrachha.vercel.app/",
    "https://www.linkedin.com/in/ashwin_rachha/",
    "https://medium.com/@ashwin_rachha",
    "https://medium.com/@ashwin_rachha/about",
    "https://scholar.google.com/citations?user=opsMRzEAAAAJ&hl=en",
    "https://www.kaggle.com/ashwinrachha1",
    "https://vtechworks.lib.vt.edu/items/3d08a8cd-effe-4e41-9830-0204637e53da",
    "https://arxiv.org/abs/2012.07587",
    "https://ieeexplore.ieee.org/document/10893211",
    "https://ieeexplore.ieee.org/document/10115140",
]

def parse_args():
    p = argparse.ArgumentParser(description="Load Web/PDF docs and index to Qdrant Cloud")
    p.add_argument("--urls-file", help="Path to a text file with URLs (one per line)")
    p.add_argument("--url", action="append", help="URL to ingest (repeatable)")
    p.add_argument("--no-defaults", action="store_true", help="Do not include built-in static URLs")
    p.add_argument("--datadir", type=str, default=str(ROOT / "data"))
    p.add_argument("--collection", default=os.getenv("QDRANT_COLLECTION", "personal_kb"))
    p.add_argument("--chunk-size", type=int, default=12000)
    p.add_argument("--overlap", type=int, default=200)
    p.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-small"))
    return p.parse_args()

def load_urls_file(path: str) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out

def _hash_id(text: str, src: str, i: int) -> str:
    # Stable IDs per (source, chunk) so re-ingest replaces instead of duplicating
    return md5(f"{src}::{i}".encode("utf-8")).hexdigest()

def chunk_docs(docs: List[Document], chunk_size: int, overlap: int) -> List[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=overlap)
    out: List[Document] = []
    for d in docs:
        chunks = splitter.split_documents([d])
        for i, ch in enumerate(chunks):
            meta = dict(ch.metadata or {})
            meta.setdefault("source", d.metadata.get("source"))
            meta.setdefault("title", d.metadata.get("title"))
            meta["chunk"] = i
            ch.metadata = meta
            ch.id = _hash_id(ch.page_content, meta.get("source", "unknown"), i)
            out.append(ch)
    return out

def load_web(urls: List[str]) -> List[Document]:
    if not urls:
        return []
    docs: List[Document] = []
    # 1) Direct fetch of provided URLs
    header_template = {
        "User-Agent": os.getenv("USER_AGENT", "Mozilla/5.0 (compatible; AlfredBot/1.0)"),
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        from langchain_community.document_loaders import WebBaseLoader
        loader = WebBaseLoader(urls, header_template=header_template)
        docs.extend(loader.load())
    except Exception as e:
        print(f"[ingest] WebBaseLoader error: {e}")

    # 2) Optional recursive crawl for more coverage (controlled via env)
    depth = int(os.getenv("RECURSIVE_DEPTH", "0"))
    if depth > 0:
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            BeautifulSoup = None  # type: ignore
        for u in urls:
            try:
                extractor = None
                if BeautifulSoup is not None:
                    extractor = lambda html: BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
                rloader = RecursiveUrlLoader(url=u, max_depth=depth, extractor=extractor)
                docs.extend(rloader.load())
            except Exception as e:
                print(f"[ingest] RecursiveUrlLoader error for {u}: {e}")

    # Normalize metadata
    normed: List[Document] = []
    for d in docs:
        meta = dict(d.metadata or {})
        src = meta.get("source") or meta.get("url") or meta.get("web_path") or "unknown"
        title = meta.get("title") or src
        meta["type"] = meta.get("type", "web")
        meta["source"] = src
        meta["title"] = title
        d.metadata = meta
        normed.append(d)
    return normed

def load_pdfs(directory: str) -> List[Document]:
    docs: List[Document] = []
    if not os.path.isdir(directory):
        return docs
    for name in os.listdir(directory):
        fp = os.path.join(directory, name)
        if not fp.lower().endswith(".pdf"):
            continue
        # PyPDFLoader yields one Document per page with page metadata. :contentReference[oaicite:5]{index=5}
        loader = PyPDFLoader(file_path=fp)
        page_docs = loader.load()
        for d in page_docs:
            d.metadata["type"] = "pdf"
            d.metadata["path"] = fp
            d.metadata["source"] = d.metadata.get("source", fp)
            # Keep filename as a coarse title
            d.metadata["title"] = d.metadata.get("title") or Path(fp).name
        docs.extend(page_docs)
    return docs

def main():
    args = parse_args()

    urls: List[str] = [] if args.no_defaults else list(STATIC_URLS)
    if args.urls_file:
        urls.extend(load_urls_file(args.urls_file))
    if args.url:
        urls.extend(args.url)
    # dedupe
    urls = list(dict.fromkeys([u for u in urls if u]))

    # 1) Load
    web_docs = load_web(urls) if urls else []
    pdf_docs = load_pdfs(args.datadir)
    base_docs = web_docs + pdf_docs
    if not base_docs:
        print("No documents found from web or PDFs.")
        return 0

    # 2) Chunk
    docs = chunk_docs(base_docs, args.chunk_size, args.overlap)

    # 3) Embed + Upsert to Qdrant Cloud
    qdrant_url = os.environ["QDRANT_URL"]
    qdrant_key = os.environ["QDRANT_API_KEY"]
    collection = args.collection

    embeddings = OpenAIEmbeddings(model=args.embed_model)
    # Ensure collection implicitly via vectorstore; Qdrant will require matching size & distance. :contentReference[oaicite:6]{index=6}
    # Deterministic IDs for upsert stability
    ids = [
        _hash_id(
            d.page_content,
            (d.metadata.get("source") if isinstance(d.metadata, dict) else "unknown"),
            int(d.metadata.get("chunk", 0)) if isinstance(d.metadata, dict) else 0,
        )
        for d in docs
    ]

    store = QdrantVectorStore.from_documents(
        documents=docs,
        embedding=embeddings,
        url=qdrant_url,
        api_key=qdrant_key,
        collection_name=collection,
        ids=ids,
    )
    print(f"Indexed {len(docs)} chunks into Qdrant collection '{collection}'.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
