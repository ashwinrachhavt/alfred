from __future__ import annotations

import re

_WS_RE = re.compile(r"\s+")
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")
_QUESTION_PREFIX_RE = re.compile(r"^\s*(?:q(?:uestion)?\s*[:.)-]+)\s*", flags=re.IGNORECASE)
_MARKDOWN_DECORATION_RE = re.compile(r"[*_`]+")
_LEETCODE_PREFIX_RE = re.compile(
    r"^\s*(?:lc|leetcode)\s*[:#-]?\s*(?:(?P<number>\d+)\s*)?(?P<title>.+)$",
    flags=re.IGNORECASE,
)


def _merge_markdown_wrapped_lines(text: str) -> list[str]:
    """Merge bullet list items that wrap onto indented continuation lines."""

    merged: list[str] = []
    buffer: list[str] = []
    bullet_indent: int | None = None

    def leading_indent_len(raw: str) -> int:
        count = 0
        for ch in raw:
            if ch == " ":
                count += 1
            elif ch == "\t":
                # Treat a tab as multiple spaces for indentation comparisons.
                count += 4
            else:
                break
        return count

    def flush() -> None:
        if not buffer:
            return
        merged.append(" ".join(buffer).strip())
        buffer.clear()
        nonlocal bullet_indent
        bullet_indent = None

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush()
            continue

        starts_list_item = _BULLET_PREFIX_RE.match(line) is not None

        if starts_list_item:
            flush()
            buffer.append(line.strip())
            bullet_indent = leading_indent_len(raw)
            continue

        if buffer and bullet_indent is not None and leading_indent_len(raw) > bullet_indent:
            buffer.append(line.strip())
            continue

        flush()
        merged.append(line.strip())

    flush()
    return merged


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
    cleaned = _QUESTION_PREFIX_RE.sub("", cleaned)
    cleaned = _MARKDOWN_DECORATION_RE.sub("", cleaned)
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
        "given ",
        "you are given ",
        "write ",
        "find ",
        "return ",
        "build ",
        "create ",
        "calculate ",
        "determine ",
        "compute ",
        "reverse ",
        "merge ",
        "sort ",
        "remove ",
        "add ",
        "insert ",
        "delete ",
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


def extract_questions_heuristic(
    text: str | None, *, max_questions: int = 12, max_line_chars: int = 360
) -> list[str]:
    """Extract likely interview questions from arbitrary scraped text.

    This is intentionally permissive: it accepts either explicit question marks or
    common question starters, and normalizes output to end in '?'.
    """

    if not text:
        return []

    extracted: list[str] = []
    seen: set[str] = set()

    for raw in _merge_markdown_wrapped_lines(text):
        line = _clean_candidate_line(raw)
        if not line:
            continue
        if "http" in line.lower():
            continue
        if len(line) > max(1, int(max_line_chars)):
            continue

        if not _looks_like_question(line):
            leet = _LEETCODE_PREFIX_RE.match(line)
            if leet:
                number = (leet.group("number") or "").strip()
                title = _WS_RE.sub(" ", (leet.group("title") or "").strip()).strip()
                title = title.lstrip("-:–— ").strip()
                if number:
                    title = f"{number} {title}".strip()
                if title:
                    line = f"Solve: {title}"
                else:
                    continue
            else:
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
