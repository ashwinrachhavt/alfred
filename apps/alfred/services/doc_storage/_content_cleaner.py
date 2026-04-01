"""Heuristic content cleaner for web captures.

Removes common noise patterns like cookie banners, navigation, footers, CTAs.
Conservative approach: only strip very obvious noise patterns.
"""

import re

# Pre-compiled noise patterns (case-insensitive)
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    # Cookie banners
    re.compile(r'^.*(?:accept all cookies|we use cookies|cookie consent|cookie policy|cookies? to improve|cookies? to provide|cookies? to enhance).*$', re.IGNORECASE),
    # Skip to content links
    re.compile(r'^.*skip to (?:main )?content.*$', re.IGNORECASE),
    # Subscribe CTAs
    re.compile(r'^.*(?:subscribe to (?:our )?newsletter|enter your email.*sign up|sign up now|get (?:weekly|daily) updates).*$', re.IGNORECASE),
    # Share buttons
    re.compile(r'^.*(?:share on (?:twitter|facebook|linkedin)|copy link).*$', re.IGNORECASE),
    # Footer patterns
    re.compile(r'^©.*(?:all rights reserved|rights reserved).*$', re.IGNORECASE),
    re.compile(r'^.*all rights reserved\.?$', re.IGNORECASE),
    re.compile(r'^.*privacy policy.*terms of service.*$', re.IGNORECASE),
]

_NAV_KEYWORDS = frozenset({
    'about', 'contact', 'privacy', 'terms', 'policy',
    'login', 'signup', 'sitemap', 'faq', 'help', 'careers',
    'accessibility', 'disclaimer', 'legal',
})

_BLANK_LINE_COLLAPSE = re.compile(r'\n{3,}')

_MIN_CLEAN_LENGTH = 200
_MAX_NAV_WORDS = 3
_NAV_CLUSTER_THRESHOLD = 4
_NAV_MATCH_RATIO = 0.75


def clean_web_content(text: str) -> str:
    """Clean web content by removing common noise patterns.

    Args:
        text: Raw web content text

    Returns:
        Cleaned text with noise patterns removed
    """
    # Don't clean short content (< 200 chars)
    if len(text) < _MIN_CLEAN_LENGTH:
        return text

    lines = text.split('\n')

    # Phase 1: Remove specific noise patterns (whole lines only)
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            cleaned_lines.append(line)
            continue

        should_remove = any(pat.match(stripped) for pat in _NOISE_PATTERNS)

        # Check for pipe-separated navigation links
        if not should_remove and '|' in stripped:
            segments = [s.strip() for s in stripped.split('|')]
            if segments and all(len(seg.split()) <= _NAV_CLUSTER_THRESHOLD for seg in segments if seg):
                short_segments = all(len(seg.split()) <= _MAX_NAV_WORDS for seg in segments if seg)
                nav_segments = sum(
                    1 for seg in segments
                    if seg and any(w.lower() in _NAV_KEYWORDS for w in seg.split())
                )
                if short_segments and len(segments) > 0 and nav_segments / len(segments) >= _NAV_MATCH_RATIO:
                    should_remove = True

        if not should_remove:
            cleaned_lines.append(line)

    # Phase 2: Remove start-of-document navigation cluster
    lines = cleaned_lines
    nav_lines_indices = []
    found_real_content = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            continue

        if not found_real_content:
            words = stripped.split()
            is_nav_like = (
                len(words) <= _MAX_NAV_WORDS and
                len(words) > 0 and
                not any(p in stripped for p in ['.', ',', '!', '?', ';', ':'])
            )

            if is_nav_like:
                nav_lines_indices.append(i)
            else:
                found_real_content = True
                break
        else:
            break

    # Remove navigation cluster if we found 4+ nav lines at the start
    if len(nav_lines_indices) >= _NAV_CLUSTER_THRESHOLD:
        last_nav_index = nav_lines_indices[-1]
        lines = lines[last_nav_index + 1:]

    # Phase 3: Collapse excessive blank lines (3+ newlines → 2 newlines)
    text = '\n'.join(lines)
    text = _BLANK_LINE_COLLAPSE.sub('\n\n', text)

    return text.strip()
