from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

from alfred.services.mind_palace.models import Hyperlink


class ExtractionService:
    """Lightweight text extraction utilities used by MindPalace.

    Groups related helpers for readability instead of scattering standalone
    functions across modules.
    """

    _HREF_RE = re.compile(r"https?://[^\s)\]]+", re.IGNORECASE)

    def compute_word_count(self, text: str) -> int:
        return len([t for t in (text or "").split() if t.strip()])

    def _domain(self, url: str | None) -> str | None:
        if not url:
            return None
        try:
            return urlparse(url).netloc.lower() or None
        except Exception:
            return None

    def extract_hyperlinks(
        self, html: Optional[str], raw_text: str, base_url: Optional[str]
    ) -> List[dict]:
        """Extract hyperlinks from HTML when available; fall back to regex on text.

        Returns a list of dicts matching the MindPalaceDocument.hyperlinks shape.
        """
        links: list[Hyperlink] = []
        base_domain = self._domain(base_url)

        if html:
            try:
                from bs4 import BeautifulSoup  # type: ignore

                soup = BeautifulSoup(html, "html.parser")
                for i, a in enumerate(soup.find_all("a")):
                    href = a.get("href")
                    if not href or not href.startswith("http"):
                        continue
                    dom = self._domain(href)
                    links.append(
                        Hyperlink(
                            url=href,
                            text=(a.text or None) if a.text else None,
                            is_internal=(dom == base_domain) if dom else False,
                            position=i,
                        )
                    )
            except Exception:
                # Fall back to regex below
                pass

        if not links:
            matches = list(self._HREF_RE.finditer(raw_text or ""))
            for i, m in enumerate(matches):
                href = m.group(0)
                dom = self._domain(href)
                links.append(
                    Hyperlink(
                        url=href,
                        text=None,
                        is_internal=(dom == base_domain) if dom else False,
                        position=m.start() if m else i,
                    )
                )

        return [link.__dict__ for link in links]
