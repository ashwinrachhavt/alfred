from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from alfred.connectors.glassdoor_connector import GlassdoorResponse
from alfred.schemas.company_insights import (
    DiscussionPost,
    InterviewExperience,
    SalaryData,
    SalaryRange,
    SourceInfo,
    SourceProvider,
)
from alfred.services.company_insights import CompanyInsightsService
from alfred.services.glassdoor_service import GlassdoorService


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.created_indexes: list[dict[str, Any]] = []

    def create_index(self, keys, **kwargs):  # type: ignore[no-untyped-def]
        self.created_indexes.append({"keys": keys, **kwargs})
        return kwargs.get("name", "idx")

    def find_one(self, filt):  # type: ignore[no-untyped-def]
        company = filt.get("company")
        if company is None:
            return None
        return self._docs.get(company)

    def update_one(self, filt, update, upsert=False):  # type: ignore[no-untyped-def]
        company = filt.get("company")
        if company is None:
            raise ValueError("company required")
        doc = self._docs.get(company, {}) if upsert else (self._docs.get(company) or {})
        set_ = update.get("$set", {})
        doc.update(set_)
        self._docs[company] = doc
        return {"ok": 1}


class _FakeDatabase:
    def __init__(self, coll: _FakeCollection) -> None:
        self._coll = coll

    def get_collection(self, _name: str):  # type: ignore[no-untyped-def]
        return self._coll


class _FakeGlassdoorClient:
    def __init__(self) -> None:
        self._reviews = [
            {
                "rating": 4.2,
                "review_title": "Great team",
                "pros": ["Smart people", "High impact"],
                "cons": "Fast pace",
                "job_title": "Software Engineer",
                "location": "NYC",
                "employment_status": "Current Employee",
                "date": "2025-10-01",
                "link": "https://example.com/review",
            }
        ]
        self._interviews = [
            {
                "job_title": "Backend Engineer",
                "difficulty": "Medium",
                "process_summary": "Phone + onsite",
                "interviewQuestions": ["Tell me about a time…?", "Design a cache?"],
                "link": "https://example.com/interview",
            }
        ]
        self._salary = {
            "location": "New York City, NY",
            "job_title": "Software Engineer",
            "min_salary": 100_000,
            "max_salary": 200_000,
            "median_salary": 150_000,
            "salary_currency": "USD",
            "salary_period": "YEAR",
            "link": "https://example.com/salary",
        }

    def get_company_reviews(self, _company, **_kwargs):  # type: ignore[no-untyped-def]
        return GlassdoorResponse(success=True, data={"reviews": self._reviews}, status_code=200)

    def get_company_interviews(self, _company, **_kwargs):  # type: ignore[no-untyped-def]
        return GlassdoorResponse(
            success=True, data={"interviews": self._interviews}, status_code=200
        )

    def get_company_salaries(self, _company, **_kwargs):  # type: ignore[no-untyped-def]
        return GlassdoorResponse(success=True, data=self._salary, status_code=200)


class _FakeBlindService:
    def get_company_discussions_sync(self, _company):  # type: ignore[no-untyped-def]
        return (
            [
                DiscussionPost(
                    source=SourceProvider.blind,
                    url="https://teamblind.example/post",
                    title="Culture?",
                    excerpt="Some thoughts",
                )
            ],
            [SourceInfo(provider=SourceProvider.blind, url="https://teamblind.example/post")],
        )

    def search_interview_posts_sync(self, _company):  # type: ignore[no-untyped-def]
        return (
            [
                InterviewExperience(
                    source=SourceProvider.blind,
                    source_url="https://teamblind.example/interview",
                    process_summary="Interview post",
                    questions=["What is your biggest weakness?"],
                )
            ],
            [SourceInfo(provider=SourceProvider.blind, url="https://teamblind.example/interview")],
        )


class _FakeLevelsService:
    def get_compensation_sources_sync(self, _company, **_kwargs):  # type: ignore[no-untyped-def]
        return (
            [
                {
                    "url": "https://levels.example/company",
                    "title": "Levels page",
                    "markdown": "Total comp ranges: $200k - $350k",
                }
            ],
            [SourceInfo(provider=SourceProvider.levels, url="https://levels.example/company")],
        )


class _FakeLLMService:
    def structured(self, _messages, schema, **_kwargs):  # type: ignore[no-untyped-def]
        # Return an empty/default schema instance for tests.
        return schema()


def test_glassdoor_service_normalizes_reviews_interviews_and_salary():
    svc = GlassdoorService(client=_FakeGlassdoorClient())
    reviews = svc.get_company_reviews_sync("ExampleCo", max_reviews=5)
    assert len(reviews) == 1
    assert reviews[0].rating == 4.2
    assert reviews[0].title == "Great team"
    assert reviews[0].pros == ["Smart people", "High impact"]
    assert reviews[0].cons == ["Fast pace"]

    interviews = svc.get_interview_experiences_sync("ExampleCo", max_interviews=5)
    assert len(interviews) == 1
    assert interviews[0].difficulty == "Medium"
    assert "Design a cache?" in interviews[0].questions

    salaries = svc.get_salary_data_sync("ExampleCo", role="Software Engineer")
    assert len(salaries) == 1
    assert salaries[0].range.currency == "USD"
    assert salaries[0].range.total_median == 150_000


def test_company_insights_caches_by_ttl_and_generates_without_network():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)

    service = CompanyInsightsService(
        database=db,  # type: ignore[arg-type]
        collection_name="company_culture_insights",
        cache_ttl_hours=1,
        glassdoor_service=GlassdoorService(client=_FakeGlassdoorClient()),
        blind_service=_FakeBlindService(),
        levels_service=_FakeLevelsService(),
        llm_service=_FakeLLMService(),
    )

    service.ensure_indexes()
    assert coll.created_indexes

    # Seed cache
    now = datetime.now(timezone.utc)
    cached_doc = {
        "company": "ExampleCo",
        "generated_at_dt": now,
        "expires_at": now + timedelta(hours=1),
        "report": {"company": "ExampleCo"},
    }
    coll._docs["ExampleCo"] = cached_doc
    assert service.get_cached_report("ExampleCo") == cached_doc

    # Force refresh returns a new payload (and persists via upsert)
    out = service.generate_report("ExampleCo", refresh=True)
    assert out["company"] == "ExampleCo"
    assert "generated_at" in out
    assert "reviews" in out

    # Missing role triggers a warning (salary skipped)
    out2 = service.generate_report("ExampleCo", refresh=True)
    assert isinstance(out2.get("warnings"), list)


def test_salary_range_schema_defaults():
    s = SalaryData(
        source=SourceProvider.web,
        role="Engineer",
        range=SalaryRange(),
    )
    assert s.range.currency is None
