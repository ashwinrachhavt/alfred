"""Tests for content cleaner heuristics."""

from alfred.services.doc_storage._content_cleaner import clean_web_content


def test_removes_cookie_banners():
    """Should remove cookie consent banners."""
    text = """We use cookies to improve your experience. Accept all cookies to continue.

This is the actual article content that should remain.
It has multiple paragraphs and real information about technology and software development.

More content here with additional details to ensure we're over the 200 character threshold for content cleaning."""

    result = clean_web_content(text)
    assert "cookies" not in result.lower()
    assert "This is the actual article content" in result


def test_removes_navigation_noise():
    """Should remove navigation clusters at the start."""
    text = """Home
About
Services
Contact
Products
Blog
Login

This is the main article content with substantial information.
It contains real information about various technical topics and developments in the field.

More paragraphs here with additional context to meet the minimum character threshold."""

    result = clean_web_content(text)
    assert "Home\nAbout\nServices" not in result
    assert "This is the main article content" in result


def test_removes_footer_links():
    """Should remove copyright and footer patterns."""
    text = """This is good content about technology and software development practices.
It discusses various concepts in detail including architecture patterns and best practices.

More detailed information follows with examples and case studies.

© 2024 Company Name. All rights reserved.
Privacy Policy | Terms of Service | Contact Us"""

    result = clean_web_content(text)
    assert "©" not in result
    assert "Privacy Policy" not in result
    assert "This is good content" in result


def test_preserves_short_content():
    """Should NOT clean content under 200 chars."""
    short_text = "This is a short snippet. It has some cookies mention. © 2024 Company."

    result = clean_web_content(short_text)
    assert result == short_text  # unchanged


def test_removes_subscribe_ctas():
    """Should remove subscription CTAs."""
    text = """This is an interesting article about AI and machine learning developments.
It has valuable information covering neural networks, transformers, and modern architectures.

Subscribe to our newsletter for updates!
Enter your email below to sign up now.

More content continues here with technical deep dives and implementation details."""

    result = clean_web_content(text)
    assert "Subscribe" not in result
    assert "newsletter" not in result
    assert "This is an interesting article" in result


def test_removes_share_buttons_text():
    """Should remove social sharing button text."""
    text = """This article discusses machine learning fundamentals and advanced topics in artificial intelligence.

Share on Twitter | Share on Facebook | Copy link

The content explains key concepts including supervised learning, unsupervised learning, and reinforcement learning approaches."""

    result = clean_web_content(text)
    assert "Share on Twitter" not in result
    assert "Copy link" not in result
    assert "This article discusses machine learning" in result


def test_removes_skip_to_content():
    """Should remove 'skip to content' accessibility links."""
    text = """Skip to content
Skip to main content

This is the actual article with substantial information about web development and accessibility.
With real information covering best practices and implementation strategies for modern web applications."""

    result = clean_web_content(text)
    assert "Skip to content" not in result
    assert "This is the actual article" in result


def test_collapses_excessive_blank_lines():
    """Should collapse 3+ blank lines to 2."""
    text = """Paragraph one discusses important concepts in software architecture and design patterns.



Paragraph two explores implementation details and best practices for modern development workflows.






Paragraph three concludes with recommendations and next steps for improving your systems."""

    result = clean_web_content(text)
    # Should have max 2 newlines between content
    assert "\n\n\n" not in result
    assert "Paragraph one" in result
    assert "Paragraph two" in result


def test_removes_pipe_separated_nav_links():
    """Should remove pipe-separated navigation where all segments are ≤4 words."""
    text = """This is real content about software development and best practices in modern web applications.

Home | About Us | Contact | Privacy Policy

More real content here with detailed explanations of architectural patterns and implementation strategies."""

    result = clean_web_content(text)
    assert "Home | About Us | Contact" not in result
    assert "This is real content" in result


def test_preserves_pipe_separated_real_content():
    """Should NOT remove pipe-separated content if any segment is >4 words."""
    text = """This is real content.

The United States has long been | a beacon of democracy and freedom | in the world.

More real content here."""

    result = clean_web_content(text)
    assert "The United States has long been" in result
    assert "beacon of democracy" in result


def test_navigation_only_at_start():
    """Should only remove navigation clusters at the beginning."""
    text = """Home
About
Contact
Services

This is the main content with substantial information covering technical topics.

Section Title
Subsection
Details
Summary

More content with detailed explanations and examples to demonstrate the concepts."""

    result = clean_web_content(text)
    # Start navigation should be removed
    assert not result.startswith("Home")
    # Mid-document short lines should be preserved (could be headings)
    assert "Section Title" in result
    assert "Subsection" in result


def test_preserves_copyright_in_real_content():
    """Should only remove standalone copyright lines, not inline mentions."""
    text = """This article discusses copyright law and © symbols in legal contexts and their implications.
The concept of intellectual property is important in modern software development and content creation.

Additional paragraphs provide context and examples from real-world cases.

© 2024 All Rights Reserved"""

    result = clean_web_content(text)
    # Inline copyright mention should stay
    assert "copyright law and ©" in result
    # Footer copyright should be removed
    assert "© 2024 All Rights Reserved" not in result


def test_real_world_article():
    """Should clean a realistic article capture."""
    text = """We use cookies to provide you with a better experience. Accept all cookies

Home
Products
About
Contact

Skip to main content

The Future of AI: A Deep Dive

This article explores the fascinating world of artificial intelligence.
We examine cutting-edge developments and their implications.

Machine learning has transformed how we process data.
Neural networks enable unprecedented pattern recognition.

Subscribe to our newsletter!
Get weekly updates delivered to your inbox.

Share on Twitter | Share on Facebook | Share on LinkedIn

© 2024 Tech Blog. All rights reserved.
Privacy Policy | Terms of Service | Contact Us"""

    result = clean_web_content(text)

    # Noise should be gone
    assert "cookies" not in result.lower()
    assert "Home\nProducts" not in result
    assert "Skip to main" not in result
    assert "Subscribe" not in result
    assert "Share on Twitter" not in result
    assert "Privacy Policy" not in result

    # Content should remain
    assert "The Future of AI: A Deep Dive" in result
    assert "artificial intelligence" in result
    assert "Machine learning" in result


def test_preserves_pipe_content_with_nav_words():
    """Should NOT remove pipe content that uses nav words in real context."""
    text = """Article about business strategy.

Our services include: consulting | home office setup | product development | policy creation

More content here about the company's growth strategy and future plans that extends past the minimum."""
    result = clean_web_content(text)
    assert "consulting" in result
    assert "product development" in result
