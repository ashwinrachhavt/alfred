from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alfred.connectors.glassdoor_connector import GlassdoorClient, GlassdoorResponse
from alfred.core.exceptions import ServiceUnavailableError
from alfred.schemas.company_insights import (
    InterviewExperience,
    Review,
    SalaryData,
    SalaryRange,
    SourceInfo,
    SourceProvider,
)


def _first_str(obj: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def _first_float(obj: dict[str, Any], *keys: str) -> float | None:
    for k in keys:
        v = obj.get(k)
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v)
            except ValueError:
                continue
    return None


def _as_str_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        out: list[str] = []
        for x in val:
            if isinstance(x, str) and x.strip():
                out.append(x.strip())
        return out
    if isinstance(val, str) and val.strip():
        # Many sources return pros/cons as a single blob; split into lightweight bullets.
        raw = val.strip()
        if "\n" in raw:
            return [ln.strip("-• ").strip() for ln in raw.splitlines() if ln.strip()]
        return [raw]
    return []


def _normalize_review(item: dict[str, Any]) -> Review:
    return Review(
        source=SourceProvider.glassdoor,
        source_url=_first_str(item, "link", "url", "review_link", "reviewUrl"),
        rating=_first_float(item, "rating", "overall_rating", "overallRating"),
        title=_first_str(item, "title", "headline", "review_title", "reviewTitle"),
        summary=_first_str(item, "summary", "review", "text", "body"),
        pros=_as_str_list(item.get("pros")),
        cons=_as_str_list(item.get("cons")),
        job_title=_first_str(item, "job_title", "jobTitle", "position"),
        location=_first_str(item, "location", "location_name", "locationName"),
        employment_status=_first_str(
            item, "employment_status", "employmentStatus", "employeeStatus"
        ),
        review_date=_first_str(
            item, "date", "review_date", "reviewDate", "created_at", "createdAt"
        ),
    )


def _normalize_interview(item: dict[str, Any]) -> InterviewExperience:
    questions = _as_str_list(item.get("questions") or item.get("interview_questions"))
    if not questions:
        questions = _as_str_list(
            item.get("interviewQuestions") or item.get("interview_questions_text")
        )
    return InterviewExperience(
        source=SourceProvider.glassdoor,
        source_url=_first_str(item, "link", "url", "interview_link", "interviewUrl"),
        role=_first_str(item, "job_title", "jobTitle", "role", "position"),
        location=_first_str(item, "location", "location_name", "locationName"),
        interview_date=_first_str(item, "date", "interview_date", "created_at", "createdAt"),
        difficulty=_first_str(item, "difficulty", "difficulty_label", "difficultyLabel"),
        outcome=_first_str(item, "outcome", "result", "offer_status", "offerStatus"),
        process_summary=_first_str(item, "process", "process_summary", "summary", "experience"),
        questions=questions,
    )


def _normalize_salary(payload: dict[str, Any], *, company: str, role: str) -> SalaryData:
    currency = _first_str(payload, "salary_currency", "currency")
    period = _first_str(payload, "salary_period", "period")
    rng = SalaryRange(
        currency=currency,
        period=period,
        total_min=_first_float(payload, "min_salary", "minSalary"),
        total_max=_first_float(payload, "max_salary", "maxSalary"),
        total_median=_first_float(payload, "median_salary", "medianSalary"),
        base_min=_first_float(payload, "min_base_salary", "minBaseSalary"),
        base_max=_first_float(payload, "max_base_salary", "maxBaseSalary"),
        base_median=_first_float(payload, "median_base_salary", "medianBaseSalary"),
    )
    return SalaryData(
        source=SourceProvider.glassdoor,
        source_url=_first_str(payload, "link", "url"),
        role=role,
        location=_first_str(payload, "location"),
        level=None,
        range=rng,
    )


@dataclass
class GlassdoorService:
    """Access Glassdoor data through the OpenWeb Ninja API (preferred, ToS-friendly)."""

    client: GlassdoorClient | None = None

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = GlassdoorClient()

    def _unwrap_leaf(self, resp: GlassdoorResponse) -> dict[str, Any]:
        if not (resp.success and resp.data and isinstance(resp.data, dict)):
            raise ServiceUnavailableError(resp.error or "Glassdoor API request failed")
        return resp.data

    def _coerce_list(self, leaf: dict[str, Any], *keys: str) -> list[dict[str, Any]]:
        for k in keys:
            val = leaf.get(k)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]
        return []

    def get_sources_for_company(self, company_name: str) -> list[SourceInfo]:
        # OpenWeb Ninja API does not provide a single canonical company URL in all responses.
        # We keep sources at the request-level elsewhere; return empty here for now.
        _ = company_name
        return []

    def get_company_reviews_sync(self, company_name: str, *, max_reviews: int = 50) -> list[Review]:
        resp = self.client.get_company_reviews(
            company_name, max_reviews=max_reviews, sort="MOST_RECENT"
        )
        leaf = self._unwrap_leaf(resp)
        items = self._coerce_list(leaf, "reviews", "data")
        return [_normalize_review(it) for it in items]

    def get_interview_experiences_sync(
        self, company_name: str, *, max_interviews: int = 50
    ) -> list[InterviewExperience]:
        max_interviews = int(max_interviews)
        resp = self.client.get_company_interviews(
            company_name,
            max_interviews=max_interviews,
            sort="MOST_RECENT",
        )
        leaf = self._unwrap_leaf(resp)
        items = self._coerce_list(leaf, "interviews", "reviews", "data")
        return [_normalize_interview(it) for it in items]

    def get_interview_experiences_with_raw_sync(
        self, company_name: str, *, max_interviews: int = 50
    ) -> list[tuple[InterviewExperience, dict[str, Any]]]:
        """Return normalized interview experiences along with the raw upstream dict."""
        max_interviews = int(max_interviews)
        resp = self.client.get_company_interviews(
            company_name,
            max_interviews=max_interviews,
            sort="MOST_RECENT",
        )
        leaf = self._unwrap_leaf(resp)
        items = self._coerce_list(leaf, "interviews", "reviews", "data")
        out: list[tuple[InterviewExperience, dict[str, Any]]] = []
        for it in items:
            out.append((_normalize_interview(it), it))
        return out

    def get_salary_data_sync(
        self,
        company_name: str,
        *,
        role: str,
        location: str | None = None,
        location_type: str = "ANY",
        years_of_experience: str = "ALL",
    ) -> list[SalaryData]:
        # Prefer company-linked salary aggregates when we have a company and job title.
        # If location is missing, the upstream endpoint may still return global aggregates.
        resp = self.client.get_company_salaries(
            company_name,
            job_title=role,
            location=location,
            location_type=location_type,
            years_of_experience=years_of_experience,
        )
        leaf = self._unwrap_leaf(resp)

        # Some payloads return an object, not a list. Normalize as a single entry.
        if any(k in leaf for k in ("min_salary", "median_salary", "max_salary")):
            return [_normalize_salary(leaf, company=company_name, role=role)]

        # Fall back to list-like payloads when available.
        items = self._coerce_list(leaf, "salaries", "data")
        out: list[SalaryData] = []
        for it in items:
            out.append(_normalize_salary(it, company=company_name, role=role))
        return out
