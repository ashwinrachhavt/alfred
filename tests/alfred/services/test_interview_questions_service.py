from __future__ import annotations

from dataclasses import dataclass

from alfred.connectors.firecrawl_connector import FirecrawlResponse
from alfred.connectors.web_connector import SearchHit, SearchResponse
from alfred.services.interview_questions import InterviewQuestionsService


@dataclass
class _FakeWeb:
    hits: list[SearchHit]

    def search(self, query: str, num_results: int = 8):  # type: ignore[override]
        _ = num_results
        if "coding" in query:
            return SearchResponse(
                provider="ddg",
                query=query,
                hits=self.hits,
                meta={"status": "ok"},
            )
        return SearchResponse(provider="ddg", query=query, hits=[], meta={"status": "ok"})


class _FakeFirecrawl:
    def search(self, query: str, max_results: int = 6):  # type: ignore[override]
        _ = max_results
        if "interview questions" in query:
            return FirecrawlResponse(
                success=True,
                data=[
                    {
                        "url": "https://example.com/post2",
                        "title": "Blind thread",
                        "content": "How would you design a feature store?",
                    }
                ],
            )
        return FirecrawlResponse(success=True, data=[])

    def scrape(self, url: str, render_js: bool = False):  # type: ignore[override]
        _ = render_js
        if "post1" in url:
            return FirecrawlResponse(
                success=True,
                markdown="- How would you design Uber?\n- Explain CAP theorem in distributed systems",
            )
        if "post2" in url:
            return FirecrawlResponse(
                success=True,
                markdown="Tell me about a conflict with a coworker",
            )
        return FirecrawlResponse(success=False, error="not found")


def test_generate_report_dedupes_and_categorizes_questions():
    hits = [
        SearchHit(
            title="Forum post",
            url="https://example.com/post1",
            snippet="Asked to design a cache? and talk about CAP theorem?",
            source="ddg",
            raw={},
        )
    ]
    web = _FakeWeb(hits=hits)
    firecrawl = _FakeFirecrawl()

    svc = InterviewQuestionsService(
        primary_search=web,
        fallback_search=web,
        firecrawl=firecrawl,
        search_results=5,
        firecrawl_search_results=2,
    )

    report = svc.generate_report("Acme", role="AI Engineer", max_sources=4, max_questions=10)

    assert report.company == "Acme"
    assert report.role == "AI Engineer"
    assert report.total_unique_questions >= 3
    questions = {q.question: q for q in report.questions}
    assert "How would you design Uber?" in questions
    assert "Explain CAP theorem in distributed systems?" in questions
    # Behavioral heuristic should tag general questions when no keyword matches
    conflict_q = next((q for q in report.questions if "conflict" in q.question.lower()), None)
    assert conflict_q is not None
    assert "behavioral" in conflict_q.categories or "general" in conflict_q.categories
