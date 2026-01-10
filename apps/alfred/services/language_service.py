from __future__ import annotations

import importlib.util
import logging
import math
from dataclasses import dataclass

from alfred.schemas.intelligence import LanguageDetectResponse

logger = logging.getLogger(__name__)

_LANGID_AVAILABLE = importlib.util.find_spec("langid") is not None
if _LANGID_AVAILABLE:  # pragma: no cover - environment dependent
    import langid  # type: ignore[import-not-found]
else:  # pragma: no cover - environment dependent
    langid = None  # type: ignore[assignment]


def _normalize_lang(code: str | None) -> str | None:
    if not code:
        return None
    c = str(code).strip().lower()
    if not c:
        return None
    # Normalize common separators and keep primary language subtag.
    c = c.replace("_", "-")
    primary = c.split("-", 1)[0]
    return primary or None


def _margin_to_confidence(margin: float) -> float:
    """Convert an unbounded margin into a stable 0..1 confidence value."""

    m = max(0.0, float(margin))
    # Saturating curve: small margins -> low confidence, large -> near 1.
    return 1.0 - math.exp(-m)


@dataclass(slots=True)
class LanguageService:
    """Offline-first language utilities (95+ languages when `langid` is installed)."""

    def detect(self, *, text: str) -> LanguageDetectResponse:
        s = (text or "").strip()
        if not s:
            return LanguageDetectResponse(language=None, confidence=None, provider="empty")

        if _LANGID_AVAILABLE and langid is not None:
            try:
                ranked = list(langid.rank(s))  # type: ignore[attr-defined]
                if not ranked:
                    return LanguageDetectResponse(language=None, confidence=None, provider="langid")

                top_lang, top_score = ranked[0]
                second_score = ranked[1][1] if len(ranked) > 1 else top_score - 1.0
                margin = float(top_score) - float(second_score)
                return LanguageDetectResponse(
                    language=_normalize_lang(top_lang),
                    confidence=_margin_to_confidence(margin),
                    provider="langid",
                )
            except Exception as exc:  # pragma: no cover - defensive
                logger.debug("langid detection failed: %s", exc)
                return LanguageDetectResponse(
                    language=None, confidence=None, provider="langid_error"
                )

        return LanguageDetectResponse(language=None, confidence=None, provider="unavailable")


__all__ = ["LanguageService"]
