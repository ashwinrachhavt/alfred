from __future__ import annotations

from alfred.services.utils import (
    extract_questions_heuristic,
    extract_questions_qmark_only,
)


def test_extract_questions_heuristic_normalizes_and_dedupes():
    text = """
    - Explain CAP theorem in distributed systems
    - Explain CAP theorem in distributed systems?
    - https://example.com/ignore-me
    Tell me about a conflict with a coworker
    """

    questions = extract_questions_heuristic(text, max_questions=10)

    assert "Explain CAP theorem in distributed systems?" in questions
    assert sum(1 for q in questions if q.lower().startswith("explain cap theorem")) == 1
    assert any("conflict" in q.lower() for q in questions)
    assert all(q.endswith("?") for q in questions)


def test_extract_questions_qmark_only_keeps_short_qmark_lines():
    too_long = ("a" * 180) + "?"
    allowed_trailing_backslash = ("a" * 179) + "?\\"
    text = f"""
    - How would you design Uber?
    - Any tips? Thanks.
    - Not a question
    - See http://example.com/ignore?foo=bar
    - {too_long}
    - {allowed_trailing_backslash}
    """

    questions = extract_questions_qmark_only(text, max_questions=20, max_body_chars=180)

    assert "How would you design Uber?" in questions
    assert "Any tips? Thanks." in questions
    assert too_long not in questions
    assert allowed_trailing_backslash in questions
