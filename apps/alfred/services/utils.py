from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def normalize_question(text: str) -> str:
    """Normalize an interview question string.

    - Collapses whitespace.
    - Strips trailing '.', '!', ':'.
    - Ensures the string ends with a '?'.
    """

    question = _WS_RE.sub(" ", (text or "").strip()).strip()
    while question.endswith((".", "!", ":")):
        question = question[:-1].rstrip()
    if question and not question.endswith("?"):
        question += "?"
    return question


def _clean_candidate_line(line: str) -> str:
    cleaned = _BULLET_PREFIX_RE.sub("", line.strip())
    cleaned = cleaned.strip(" \t-–—•*")
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    return cleaned


def _looks_like_question(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False
    if "?" in candidate:
        return True

    lower = candidate.lower()
    starters = (
        "how ",
        "what ",
        "why ",
        "when ",
        "where ",
        "which ",
        "who ",
        "explain ",
        "describe ",
        "tell me ",
        "walk me ",
        "talk me ",
        "give an example",
        "can you ",
        "could you ",
        "would you ",
        "design ",
        "implement ",
        "compare ",
        "define ",
    )
    return lower.startswith(starters)


def extract_questions_heuristic(text: str | None, *, max_questions: int = 12) -> list[str]:
    """Extract likely interview questions from arbitrary scraped text.

    This is intentionally permissive: it accepts either explicit question marks or
    common question starters, and normalizes output to end in '?'.
    """

    if not text:
        return []

    extracted: list[str] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = _clean_candidate_line(raw)
        if not line:
            continue
        if "http" in line.lower():
            continue
        if len(line) > 220:
            continue
        if not _looks_like_question(line):
            continue

        question = normalize_question(line)
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        extracted.append(question)
        if len(extracted) >= max(1, int(max_questions)):
            break

    return extracted


def extract_questions_qmark_only(
    text: str | None, *, max_questions: int = 12, max_body_chars: int = 180
) -> list[str]:
    """Extract short question-mark-containing lines (best-effort).

    This is tuned for public forum posts where questions are usually explicit and short.
    It preserves the raw line content (no normalization) and de-dupes while preserving
    order.
    """

    if not text:
        return []

    lines = [ln.strip(" \t-*•").strip() for ln in text.splitlines()]
    candidates: list[str] = []
    for line in lines:
        if not line or "http" in line.lower():
            continue
        if "?" not in line:
            continue
        if len(line) > max_body_chars and not (
            line.endswith("\\") and len(line) <= max_body_chars + 1
        ):
            continue
        candidates.append(line)
        if len(candidates) >= max(1, int(max_questions)):
            break

    # De-dupe preserving order
    seen: set[str] = set()
    out: list[str] = []
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


__all__ = [
    "extract_questions_heuristic",
    "extract_questions_qmark_only",
    "normalize_question",
]
