from __future__ import annotations

from alfred.services.web_capture import (
    build_document_chat_context,
    build_source_capture,
    classify_page_kind,
)

EDGE_MARKDOWN = """# The SMILE Curve Has Come for Software

### Why software value is migrating to the edges, just like hardware did decades ago

![Curve](https://substackcdn.com/image/fetch/chart.png)

## The Middle of the Stack Is Collapsing in Real Time

Software is following the same arc hardware did.

[Entrepreneur's Edge](https://www.edge.ceo/)
"""


def test_build_source_capture_extracts_substack_article_metadata() -> None:
    metadata = {
        "og:type": "article",
        "og:url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
        "og:title": "The SMILE Curve Has Come for Software",
        "description": "Why software value is migrating to the edges",
        "author": "Ryan Waliany",
        "og:image": "https://substackcdn.com/cover.png",
        "sourceURL": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
        "statusCode": 200,
        "contentType": "text/html; charset=utf-8",
        "scrapeId": "scrape-1",
    }

    capture = build_source_capture(
        url="https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
        markdown=EDGE_MARKDOWN,
        html="<article></article>",
        metadata=metadata,
    )

    assert capture["kind"] == "blog_article"
    assert capture["platform"] == "substack"
    assert capture["title"] == "The SMILE Curve Has Come for Software"
    assert capture["subtitle"] == "Why software value is migrating to the edges"
    assert capture["author"] == "Ryan Waliany"
    assert (
        capture["canonical_url"]
        == "https://www.edge.ceo/p/the-smile-curve-has-come-for-software"
    )
    assert capture["cover_image_url"] == "https://substackcdn.com/cover.png"
    assert capture["headings"] == [
        {"level": 1, "text": "The SMILE Curve Has Come for Software"},
        {
            "level": 3,
            "text": (
                "Why software value is migrating to the edges, "
                "just like hardware did decades ago"
            ),
        },
        {"level": 2, "text": "The Middle of the Stack Is Collapsing in Real Time"},
    ]
    assert capture["images"] == [
        {
            "url": "https://substackcdn.com/image/fetch/chart.png",
            "alt": "Curve",
            "position": 0,
        }
    ]
    assert capture["links"] == [
        {"url": "https://www.edge.ceo/", "text": "Entrepreneur's Edge", "position": 0}
    ]
    assert capture["firecrawl"] == {
        "scrape_id": "scrape-1",
        "status_code": 200,
        "content_type": "text/html; charset=utf-8",
    }


def test_classify_page_kind_detects_documentation_and_chapter() -> None:
    assert (
        classify_page_kind(
            url="https://docs.example.com/sdk/authentication",
            metadata={"title": "Authentication - SDK Docs"},
            markdown="# Authentication\n\n## API keys\n\n## Examples",
        )
        == "documentation"
    )
    assert (
        classify_page_kind(
            url="https://book.example.com/chapter-4",
            metadata={"title": "Chapter 4: Markets"},
            markdown="# Chapter 4\n\n## Section 1",
        )
        == "chapter"
    )


def test_build_document_chat_context_prefers_summary_and_source_structure() -> None:
    text = "A " * 5000
    context = build_document_chat_context(
        {
            "title": "The SMILE Curve Has Come for Software",
            "source_url": "https://www.edge.ceo/p/the-smile-curve-has-come-for-software",
            "cleaned_text": text,
            "summary": {"short": "Software value is moving to scarce edges."},
            "enrichment": {
                "source_analysis": {
                    "thesis": "The middle of SaaS is commoditizing.",
                    "argument_flow": [
                        "Hardware had a smile curve.",
                        "Software now has one too.",
                    ],
                }
            },
            "metadata": {
                "source_capture": {
                    "kind": "blog_article",
                    "author": "Ryan Waliany",
                    "headings": [
                        {
                            "level": 2,
                            "text": "The Same Curve is Emerging in Software",
                        }
                    ],
                }
            },
        },
        max_chars=900,
    )

    assert "Document: The SMILE Curve Has Come for Software" in context
    assert "Kind: blog_article" in context
    assert "Author: Ryan Waliany" in context
    assert "Summary: Software value is moving to scarce edges." in context
    assert "Thesis: The middle of SaaS is commoditizing." in context
    assert "The Same Curve is Emerging in Software" in context
    assert len(context) <= 900
