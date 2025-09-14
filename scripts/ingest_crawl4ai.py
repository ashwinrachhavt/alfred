#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[1]
API_DIR = ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from alfred_app.services.web_ingest import crawl_urls, chunk_pages
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

STATIC_URLS: List[str] = [
    "https://ashwinrachha.vercel.app/",
    "https://www.linkedin.com/in/ashwinrachha/",
    "https://medium.com/@ashwin_rachha",
    "https://medium.com/@ashwin_rachha/about",
    "https://scholar.google.com/citations?user=opsMRzEAAAAJ&hl=en",
    "https://www.kaggle.com/ashwinrachha1",
    "https://vtechworks.lib.vt.edu/items/3d08a8cd-effe-4e41-9830-0204637e53da",
    "https://arxiv.org/abs/2012.07587",
    "https://ieeexplore.ieee.org/document/10893211",
    "https://ieeexplore.ieee.org/document/10115140",
]


def load_urls_file(path: str) -> List[str]:
    out: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            out.append(s)
    return out


def parse_args():
    p = argparse.ArgumentParser(description="Ingest URLs into a persistent Chroma collection")
    p.add_argument("--urls-file", help="Path to a text file containing URLs (one per line)")
    p.add_argument("--url", action="append", help="URL to ingest (repeatable)")
    p.add_argument("--no-defaults", action="store_true", help="Do not include built-in static URLs")
    p.add_argument("--collection", default=os.getenv("CHROMA_COLLECTION", os.getenv("QDRANT_COLLECTION", "personal_kb")))
    p.add_argument("--chroma-path", default=os.getenv("CHROMA_PATH", "./chroma_store"))
    p.add_argument("--chunk-size", type=int, default=1200)
    p.add_argument("--overlap", type=int, default=200)
    p.add_argument("--embed-model", default=os.getenv("EMBED_MODEL", "text-embedding-3-small"))
    return p.parse_args()




def main():
    args = parse_args()

    urls: List[str] = [] if args.no_defaults else list(STATIC_URLS)
    if args.urls_file:
        urls.extend(load_urls_file(args.urls_file))
    if args.url:
        urls.extend(args.url)

    seen = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]
    urls = [u for u in urls if u]
    if not urls:
        print("No URLs provided.", file=sys.stderr)
        return 1

    print(f"Crawling {len(urls)} URL(s)…")
    pages = crawl_urls(urls)
    print(f"Fetched {len(pages)} page(s). Chunking…")
    items = chunk_pages(pages, chunk_size=args.chunk_size, overlap=args.overlap)
    os.makedirs(args.chroma_path, exist_ok=True)
    print(f"Upserting {len(items)} chunks into Chroma collection '{args.collection}' at '{args.chroma_path}'…")
    texts = [t for (_, t, __) in items]
    metadatas = [m for (_, __, m) in items]
    ids = [i for (i, __, ___) in items]

    embeddings = OpenAIEmbeddings(model=args.embed_model)
    vectordb = Chroma(
        collection_name=args.collection,
        persist_directory=args.chroma_path,
        embedding_function=embeddings,
    )
    vectordb.add_texts(texts=texts, metadatas=metadatas, ids=ids)
    try:
        vectordb.persist()
    except Exception:
        pass
    print(f"Done. Upserted {len(items)} chunks. Persisted to {args.chroma_path}.")
    # Quick hint if coverage seems low
    if len(items) < len(urls):
        missing = len(urls) - len(items)
        print(f"Note: Some URLs may have blocked or yielded little text. Consider enabling Crawl4AI and Playwright for JS-heavy sites.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
