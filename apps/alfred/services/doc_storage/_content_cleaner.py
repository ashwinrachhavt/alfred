"""Heuristic content cleaner for web captures.

Removes common noise patterns like cookie banners, navigation, footers, CTAs.
Conservative approach: only strip very obvious noise patterns.
"""

import re


def clean_web_content(text: str) -> str:
    """Clean web content by removing common noise patterns.

    Args:
        text: Raw web content text

    Returns:
        Cleaned text with noise patterns removed
    """
    # Don't clean short content (< 200 chars)
    if len(text) < 200:
        return text

    lines = text.split('\n')

    # Phase 1: Remove specific noise patterns (whole lines only)
    # Do this FIRST so they don't interfere with navigation detection

    # Cookie banners
    cookie_patterns = [
        r'^.*(?:accept all cookies|we use cookies|cookie consent|cookie policy|cookies? to improve|cookies? to provide|cookies? to enhance).*$',
    ]

    # Skip to content links
    skip_patterns = [
        r'^.*skip to (?:main )?content.*$',
    ]

    # Subscribe CTAs
    subscribe_patterns = [
        r'^.*(?:subscribe to (?:our )?newsletter|enter your email.*sign up|sign up now|get (?:weekly|daily) updates).*$',
    ]

    # Share buttons
    share_patterns = [
        r'^.*(?:share on (?:twitter|facebook|linkedin)|copy link).*$',
    ]

    # Footer patterns (only if the whole line matches)
    footer_patterns = [
        r'^©.*(?:all rights reserved|rights reserved).*$',
        r'^.*all rights reserved\.?$',
        r'^.*privacy policy.*terms of service.*$',
    ]

    # Combine all patterns
    all_patterns = (
        cookie_patterns +
        skip_patterns +
        subscribe_patterns +
        share_patterns +
        footer_patterns
    )

    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        should_remove = False

        if not stripped:
            cleaned_lines.append(line)
            continue

        # Check against all patterns (case insensitive)
        for pattern in all_patterns:
            if re.match(pattern, stripped, re.IGNORECASE):
                should_remove = True
                break

        # Check for pipe-separated navigation links
        if not should_remove and '|' in stripped:
            segments = [s.strip() for s in stripped.split('|')]
            # All segments must be ≤4 words to be considered nav
            if segments and all(len(seg.split()) <= 4 for seg in segments if seg):
                # Additional check: segments must look like pure navigation links
                # (each segment is ≤2 words AND 75%+ match nav keywords)
                nav_keywords = {'about', 'contact', 'privacy', 'terms', 'policy',
                               'login', 'signup', 'sitemap', 'faq', 'help', 'careers',
                               'accessibility', 'disclaimer', 'legal'}
                short_segments = all(len(seg.split()) <= 3 for seg in segments if seg)
                nav_segments = sum(
                    1 for seg in segments
                    if seg and any(w.lower() in nav_keywords for w in seg.split())
                )
                if short_segments and len(segments) > 0 and nav_segments / len(segments) >= 0.75:
                    should_remove = True

        if not should_remove:
            cleaned_lines.append(line)

    # Phase 2: Remove start-of-document navigation cluster
    # Now that obvious noise is gone, look for nav clusters at the start
    lines = cleaned_lines
    nav_lines_indices = []
    found_real_content = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if not stripped:
            # Blank line - track but continue
            continue

        if not found_real_content:
            # Check if this looks like navigation (short, no punctuation)
            words = stripped.split()
            is_nav_like = (
                len(words) <= 3 and
                len(words) > 0 and
                not any(p in stripped for p in ['.', ',', '!', '?', ';', ':'])
            )

            if is_nav_like:
                nav_lines_indices.append(i)
            else:
                # Found substantial content - stop looking for nav
                found_real_content = True
                break
        else:
            break

    # Remove navigation cluster if we found 4+ nav lines at the start
    if len(nav_lines_indices) >= 4:
        # Find the first non-blank line after the nav cluster
        last_nav_index = nav_lines_indices[-1]
        # Skip all lines up to and including the last nav line
        lines = lines[last_nav_index + 1:]

    # Phase 3: Collapse excessive blank lines (3+ newlines → 2 newlines)
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()
