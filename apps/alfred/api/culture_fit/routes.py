from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from starlette.concurrency import run_in_threadpool

from alfred.core.dependencies import get_company_insights_service, get_culture_fit_profile_service
from alfred.schemas.culture_fit import (
    CultureFitAnalysisResult,
    CultureFitAnalyzeRequest,
    CultureFitProfileRecord,
    CultureFitProfileUpsert,
    UserValuesProfile,
)
from alfred.services.company_insights import CompanyInsightsService
from alfred.services.culture_fit import CultureFitAnalyzer
from alfred.services.culture_fit_profiles import CultureFitProfileService

router = APIRouter(prefix="/api/culture-fit", tags=["culture_fit"])


def get_culture_fit_analyzer() -> CultureFitAnalyzer:
    return CultureFitAnalyzer()


def _collect_company_corpus_from_insights(
    report: dict[str, Any],
) -> tuple[list[str], list[str], list[str]]:
    reviews: list[str] = []
    discussions: list[str] = []
    keywords: list[str] = []

    for r in report.get("reviews") or []:
        if isinstance(r, dict):
            if isinstance(r.get("summary"), str):
                reviews.append(r["summary"])
            pros = r.get("pros")
            cons = r.get("cons")
            if isinstance(pros, list):
                reviews.extend([p for p in pros if isinstance(p, str)])
            if isinstance(cons, list):
                reviews.extend([c for c in cons if isinstance(c, str)])

    for p in report.get("posts") or []:
        if isinstance(p, dict):
            excerpt = p.get("excerpt")
            if isinstance(excerpt, str):
                discussions.append(excerpt)
            title = p.get("title")
            if isinstance(title, str):
                discussions.append(title)

    signals = report.get("signals") or {}
    if isinstance(signals, dict):
        kws = signals.get("culture_keywords")
        if isinstance(kws, list):
            keywords.extend([k for k in kws if isinstance(k, str)])
        mgmt = signals.get("management_notes")
        if isinstance(mgmt, str) and mgmt.strip():
            discussions.append(mgmt)
        wlb = signals.get("work_life_balance_indicators")
        if isinstance(wlb, list):
            discussions.extend([w for w in wlb if isinstance(w, str)])

    return reviews, discussions, keywords


@router.post("/profile")
def upsert_profile(
    payload: CultureFitProfileUpsert,
    svc: CultureFitProfileService = Depends(get_culture_fit_profile_service),
) -> dict[str, Any]:
    profile_id = svc.upsert(payload)
    return {"id": profile_id}


@router.get("/profile", response_model=CultureFitProfileRecord)
def get_profile(
    user_id: str | None = None,
    svc: CultureFitProfileService = Depends(get_culture_fit_profile_service),
) -> dict[str, Any]:
    record = svc.get_by_user_id(user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Culture fit profile not found")
    return record


@router.post("/analyze", response_model=CultureFitAnalysisResult)
async def analyze_culture_fit(
    payload: CultureFitAnalyzeRequest,
    analyzer: CultureFitAnalyzer = Depends(get_culture_fit_analyzer),
    profiles: CultureFitProfileService = Depends(get_culture_fit_profile_service),
    insights: CompanyInsightsService = Depends(get_company_insights_service),
) -> CultureFitAnalysisResult:
    company = (payload.company or "").strip()
    if not company:
        raise HTTPException(status_code=422, detail="company is required")

    user_profile: UserValuesProfile | None = payload.user_profile
    if user_profile is None:
        record = profiles.get_by_user_id(payload.user_id)
        if record is None:
            raise HTTPException(
                status_code=422,
                detail="user_profile is required (or create one via POST /api/culture-fit/profile)",
            )
        user_profile = UserValuesProfile.model_validate(record.get("profile") or {})

    reviews = list(payload.reviews or [])
    discussions = list(payload.discussions or [])
    extra_keywords: list[str] = []

    needs_fetch = payload.fetch_company_insights and (not reviews) and (not discussions)
    if needs_fetch:
        try:
            report = await run_in_threadpool(
                insights.generate_report,
                company,
                role=payload.role,
                refresh=bool(payload.refresh),
            )
            r, d, k = _collect_company_corpus_from_insights(report)
            reviews.extend(r)
            discussions.extend(d)
            extra_keywords.extend(k)
        except Exception as exc:
            extra_keywords.append("limited_data")
            discussions.append(f"Company insights fetch failed: {exc}")

    return analyzer.analyze(
        company=company,
        role=payload.role,
        user_profile=user_profile,
        reviews=reviews,
        discussions=discussions,
        extra_keywords=extra_keywords,
    )


__all__ = ["router", "get_culture_fit_analyzer"]
