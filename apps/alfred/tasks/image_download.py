"""Celery task: download images from captured page markdown and persist locally.

Extracts image URLs from markdown, validates against SSRF, downloads in parallel,
stores as DocumentAssetRow, and rewrites markdown URLs to local asset endpoints.
"""

from __future__ import annotations

import hashlib
import ipaddress
import logging
import re
import socket
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any
from urllib.parse import urlparse

import httpx
from celery import shared_task

logger = logging.getLogger(__name__)

# ── Limits ────────────────────────────────────────────────────────────

MAX_IMAGES_PER_DOC = 20
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5MB
DOWNLOAD_TIMEOUT = 10  # seconds per image
PARALLEL_WORKERS = 5

# ── Image URL extraction ──────────────────────────────────────────────

_IMAGE_URL_RE = re.compile(r"!\[([^\]]*)\]\((https?://[^)]+)\)")

ALLOWED_MIME_PREFIXES = ("image/png", "image/jpeg", "image/gif", "image/webp", "image/svg")


def extract_image_urls(markdown: str) -> list[tuple[str, str]]:
    """Extract (alt_text, url) pairs from markdown image syntax."""
    return _IMAGE_URL_RE.findall(markdown)[:MAX_IMAGES_PER_DOC]


# ── SSRF validation ──────────────────────────────────────────────────

_BLOCKED_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),  # IPv6 private
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]


def is_url_safe(url: str) -> bool:
    """Validate URL is safe to fetch (no SSRF to internal services).

    Checks:
    - Only http:// and https:// schemes
    - Resolves DNS and checks IP against private/reserved ranges
    - Blocks localhost, private IPs, link-local addresses
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Block obvious localhost patterns
    if hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        return False

    # Resolve DNS and check the actual IP
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _family, _type, _proto, _canonname, sockaddr in results:
            ip_str = sockaddr[0]
            ip = ipaddress.ip_address(ip_str)
            for network in _BLOCKED_NETWORKS:
                if ip in network:
                    logger.warning("SSRF blocked: %s resolved to private IP %s", url, ip_str)
                    return False
    except (socket.gaierror, OSError):
        # DNS resolution failed
        return False

    return True


# ── Single image download ─────────────────────────────────────────────

def _download_one(url: str, alt_text: str) -> dict[str, Any] | None:
    """Download a single image. Returns asset dict or None on failure."""
    if not is_url_safe(url):
        logger.info("Skipping unsafe URL: %s", url[:200])
        return None

    try:
        with httpx.Client(
            timeout=DOWNLOAD_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; Alfred/2.0)"},
        ) as client:
            resp = client.get(url)
            resp.raise_for_status()

            # Check content type
            content_type = resp.headers.get("content-type", "")
            if not any(content_type.startswith(prefix) for prefix in ALLOWED_MIME_PREFIXES):
                logger.info("Skipping non-image content type %s for %s", content_type, url[:200])
                return None

            data = resp.content
            if len(data) > MAX_IMAGE_BYTES:
                logger.info("Skipping oversized image (%d bytes): %s", len(data), url[:200])
                return None

            # Derive filename from URL
            path = urlparse(url).path
            file_name = path.split("/")[-1] or "image"
            if not any(file_name.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
                ext_map = {
                    "image/png": ".png",
                    "image/jpeg": ".jpg",
                    "image/gif": ".gif",
                    "image/webp": ".webp",
                    "image/svg+xml": ".svg",
                }
                ext = ext_map.get(content_type.split(";")[0].strip(), ".jpg")
                file_name += ext

            return {
                "original_url": url,
                "alt_text": alt_text,
                "file_name": file_name[:500],
                "mime_type": content_type.split(";")[0].strip()[:200],
                "size_bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "data": data,
            }
    except httpx.HTTPStatusError as exc:
        logger.info("HTTP %d downloading %s", exc.response.status_code, url[:200])
        return None
    except Exception:
        logger.info("Failed to download image: %s", url[:200], exc_info=True)
        return None


# ── Main task ─────────────────────────────────────────────────────────

@shared_task(
    name="alfred.tasks.image_download.download_document_images",
    bind=True,
    max_retries=0,
)
def download_document_images(self, doc_id: str) -> dict[str, Any]:
    """Download images from a document's raw_markdown and persist locally.

    Steps:
    1. Load document's raw_markdown
    2. Extract image URLs
    3. Download in parallel (5 workers)
    4. Store as DocumentAssetRow
    5. Rewrite markdown URLs to local endpoints
    6. Update document's raw_markdown
    """
    from sqlmodel import select

    from alfred.core.database import get_db_session
    from alfred.models.doc_storage import DocumentRow
    from alfred.models.document_assets import DocumentAssetRow

    session = get_db_session()

    try:
        doc = session.exec(
            select(DocumentRow).where(DocumentRow.id == uuid.UUID(doc_id))
        ).first()

        if not doc or not doc.raw_markdown:
            return {"doc_id": doc_id, "images_downloaded": 0, "status": "no_markdown"}

        image_urls = extract_image_urls(doc.raw_markdown)
        if not image_urls:
            return {"doc_id": doc_id, "images_downloaded": 0, "status": "no_images"}

        logger.info("Downloading %d images for doc %s", len(image_urls), doc_id)

        # Download in parallel
        downloaded: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=PARALLEL_WORKERS) as pool:
            futures = {
                pool.submit(_download_one, url, alt): (alt, url)
                for alt, url in image_urls
            }
            for future in as_completed(futures):
                result = future.result()
                if result:
                    downloaded.append(result)

        if not downloaded:
            return {"doc_id": doc_id, "images_downloaded": 0, "status": "all_failed"}

        # Store assets and build URL rewrite map
        rewrite_map: dict[str, str] = {}
        for item in downloaded:
            asset = DocumentAssetRow(
                doc_id=uuid.UUID(doc_id),
                original_url=item["original_url"],
                file_name=item["file_name"],
                mime_type=item["mime_type"],
                size_bytes=item["size_bytes"],
                sha256=item["sha256"],
                data=item["data"],
            )
            session.add(asset)
            session.flush()  # get the ID
            local_url = f"/api/documents/{doc_id}/assets/{asset.id}"
            rewrite_map[item["original_url"]] = local_url

        # Rewrite markdown URLs
        updated_markdown = doc.raw_markdown
        for original_url, local_url in rewrite_map.items():
            updated_markdown = updated_markdown.replace(original_url, local_url)

        doc.raw_markdown = updated_markdown
        session.add(doc)
        session.commit()

        logger.info(
            "Downloaded %d/%d images for doc %s",
            len(downloaded), len(image_urls), doc_id,
        )

        return {
            "doc_id": doc_id,
            "images_downloaded": len(downloaded),
            "images_failed": len(image_urls) - len(downloaded),
            "status": "success",
        }
    except Exception:
        session.rollback()
        logger.exception("Image download failed for doc %s", doc_id)
        return {"doc_id": doc_id, "images_downloaded": 0, "status": "error"}
    finally:
        session.close()
