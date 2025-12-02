from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests
from alfred.connectors.firecrawl_connector import FirecrawlClient
from alfred.core.config import settings
from alfred.services.mongo import MongoService
from bson import ObjectId
from tqdm.auto import tqdm


def _is_http_url(url: Optional[str]) -> bool:
    if not url:
        return False
    try:
        p = urlparse(url)
        return p.scheme in {"http", "https"}
    except Exception:
        return False


def _iter_docs(
    mongo: MongoService, collection: str, batch_size: int, filt: Dict[str, Any]
) -> Iterable[List[Dict[str, Any]]]:
    coll = mongo._connector.get_collection(collection)  # type: ignore[attr-defined]
    cursor = coll.find(filt).batch_size(max(1, batch_size))
    try:
        batch: List[Dict[str, Any]] = []
        for doc in cursor:
            batch.append(doc)
            if len(batch) >= batch_size:
                yield batch
                batch = []
        if batch:
            yield batch
    finally:
        cursor.close()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Populate raw_markdown for documents using Firecrawl"
    )
    parser.add_argument("--collection", default="documents")
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="JSON query filter (default selects missing raw_markdown)",
    )
    parser.add_argument(
        "--render-js", action="store_true", help="Use JS rendering in Firecrawl scrape"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="Force refresh even when raw_markdown exists"
    )
    parser.add_argument("--sleep", type=float, default=0.0, help="Sleep between requests (seconds)")
    parser.add_argument(
        "--timeout", type=int, default=None, help="Override Firecrawl timeout (seconds)"
    )
    parser.add_argument(
        "--no-extract-fallback",
        action="store_true",
        help="Disable fallback to /extract when /scrape returns empty",
    )
    parser.add_argument(
        "--html-fallback",
        action="store_true",
        help="If no markdown is returned, store HTML content into raw_markdown",
    )
    parser.add_argument(
        "--direct-http-fallback",
        action="store_true",
        help="If Firecrawl fails, fetch page HTML directly and convert to text/markdown",
    )
    parser.add_argument(
        "--debug", action="store_true", help="Print debug info about responses and decisions"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    mongo = MongoService()
    if not mongo.ping():
        print("Mongo ping failed", file=sys.stderr)
        return 1

    coll = mongo._connector.get_collection(args.collection)  # type: ignore[attr-defined]

    # Default filter: source_url http(s) and raw_markdown missing/empty
    if args.query:
        try:
            filt: Dict[str, Any] = json.loads(args.query)
        except Exception as exc:
            print(f"Invalid --query JSON: {exc}", file=sys.stderr)
            return 2
    else:
        filt = {
            "$or": [
                {"raw_markdown": {"$exists": False}},
                {"raw_markdown": None},
                {"raw_markdown": ""},
            ]
        }

    timeout = args.timeout if args.timeout is not None else settings.firecrawl_timeout
    client = FirecrawlClient(base_url=settings.firecrawl_base_url, timeout=timeout)

    total_docs = coll.count_documents(filt)
    updated = 0
    skipped = 0
    errors = 0

    with tqdm(
        total=total_docs,
        desc="Backfill raw_markdown",
        unit="doc",
        dynamic_ncols=True,
        mininterval=0.1,
    ) as pbar:
        for batch in _iter_docs(mongo, args.collection, args.batch_size, filt):
            for doc in batch:
                _id = doc.get("_id")
                if not isinstance(_id, ObjectId):
                    skipped += 1
                    pbar.update(1)
                    continue
                url = doc.get("source_url") or ""
                if not _is_http_url(url):
                    skipped += 1
                    tqdm.write(f"[SKIP] {_id} invalid source_url: {url!r}")
                    pbar.update(1)
                    continue
                if not args.refresh:
                    rm = doc.get("raw_markdown")
                    if isinstance(rm, str) and rm.strip():
                        skipped += 1
                        pbar.update(1)
                        continue

                try:
                    resp = client.scrape(url, render_js=args.render_js)
                    if args.debug:
                        tqdm.write(
                            f"[DBG] {_id} /scrape status={resp.status_code} success={resp.success}"
                        )
                    if not resp.success:
                        errors += 1
                        tqdm.write(f"[ERR] {_id} scrape failed: {resp.error}")
                        pbar.update(1)
                        continue
                    md = (resp.markdown or "").strip()
                    if not md and not args.no_extract_fallback:
                        # Fallback attempt 1: extract endpoint
                        tqdm.write(f"[FALLBACK] {_id} trying /extract")
                        ex = client.extract([url], render_js=args.render_js)
                        if args.debug:
                            tqdm.write(
                                f"[DBG] {_id} /extract status={ex.status_code} success={ex.success}"
                            )
                        if ex.success and ex.markdown and ex.markdown.strip():
                            md = ex.markdown.strip()
                    if not md and not args.render_js:
                        # Fallback attempt 2: try render_js=True
                        tqdm.write(f"[FALLBACK] {_id} retry with render_js")
                        resp2 = client.scrape(url, render_js=True)
                        if args.debug:
                            tqdm.write(
                                f"[DBG] {_id} /scrape(render_js) status={resp2.status_code} success={resp2.success}"
                            )
                        if resp2.success and resp2.markdown and resp2.markdown.strip():
                            md = resp2.markdown.strip()
                    if not md and (not args.no_extract_fallback) and (not args.render_js):
                        # Fallback attempt 3: extract with render_js=True
                        tqdm.write(f"[FALLBACK] {_id} try /extract with render_js")
                        ex2 = client.extract([url], render_js=True)
                        if args.debug:
                            tqdm.write(
                                f"[DBG] {_id} /extract(render_js) status={ex2.status_code} success={ex2.success}"
                            )
                        if ex2.success and ex2.markdown and ex2.markdown.strip():
                            md = ex2.markdown.strip()
                    if not md:
                        html_candidate = None
                        # Prefer most recent response's HTML
                        if "resp2" in locals() and getattr(resp2, "html", None):
                            html_candidate = resp2.html
                        if not html_candidate and "ex2" in locals() and getattr(ex2, "html", None):
                            html_candidate = ex2.html
                        if not html_candidate and "ex" in locals() and getattr(ex, "html", None):
                            html_candidate = ex.html
                        if not html_candidate and getattr(resp, "html", None):
                            html_candidate = resp.html

                        if args.html_fallback and html_candidate and html_candidate.strip():
                            md = html_candidate.strip()
                            tqdm.write(f"[HTML FALLBACK] {_id} using HTML content (len={len(md)})")
                        elif args.direct_http_fallback:
                            try:
                                tqdm.write(f"[FALLBACK] {_id} direct GET")
                                headers = {
                                    "User-Agent": (
                                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0 Safari/537.36"
                                    ),
                                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                                    "Accept-Language": "en-US,en;q=0.9",
                                }
                                r = requests.get(url, headers=headers, timeout=timeout)
                                r.raise_for_status()
                                html_text = r.text
                                # very light HTML→text conversion
                                text = re.sub(
                                    r"<script[\s\S]*?</script>|<style[\s\S]*?</style>",
                                    " ",
                                    html_text,
                                    flags=re.IGNORECASE,
                                )
                                text = (
                                    text.replace("<br>", "\n")
                                    .replace("<br/>", "\n")
                                    .replace("<p>", "\n")
                                )
                                text = re.sub(r"<[^>]+>", " ", text)
                                text = htmllib.unescape(text)
                                text = re.sub(r"\s+", " ", text).strip()
                                if len(text) > 0:
                                    md = text
                                    tqdm.write(
                                        f"[DIRECT FALLBACK] {_id} used direct HTTP content (len={len(md)})"
                                    )
                            except Exception as exc2:
                                if args.debug:
                                    tqdm.write(f"[DBG] {_id} direct fallback failed: {exc2}")
                        else:
                            skipped += 1
                            tqdm.write(f"[SKIP] {_id} no markdown returned")
                            pbar.update(1)
                            continue
                    if args.dry_run:
                        tqdm.write(f"[DRY] Would set raw_markdown for {_id} (len={len(md)})")
                    else:
                        now = datetime.utcnow().replace(tzinfo=timezone.utc)
                        coll.update_one(
                            {"_id": _id}, {"$set": {"raw_markdown": md, "updated_at": now}}
                        )
                        updated += 1
                    if args.sleep > 0:
                        time.sleep(args.sleep)
                except Exception as exc:
                    errors += 1
                    tqdm.write(f"[ERR] {_id} exception: {exc}")
                finally:
                    pbar.update(1)

    print(f"Updated: {updated}  Skipped: {skipped}  Errors: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
