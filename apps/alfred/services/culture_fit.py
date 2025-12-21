from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from alfred.schemas.company_insights import SentimentLabel
from alfred.schemas.culture_fit import (
    DEFAULT_DIMENSIONS,
    CompanyCultureProfile,
    CultureDimension,
    CultureFitAnalysisResult,
    CultureVector,
    FitDimensionScore,
    FitScoreBreakdown,
    RadarChartData,
    TalkingPoint,
    TalkingPointType,
    UserValuesProfile,
)


def _clamp_0_100(value: float) -> int:
    return max(0, min(100, int(round(value))))


def _compact(text: str) -> str:
    return " ".join((text or "").split()).strip()


def _safe_excerpt(text: str, *, max_chars: int = 240) -> str | None:
    t = _compact(text)
    if not t:
        return None
    return t[:max_chars] + ("…" if len(t) > max_chars else "")


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        t = _compact(it)
        if not t or t in seen:
            continue
        seen.add(t)
        out.append(t)
    return out


_DIMENSION_KEYWORDS: dict[CultureDimension, dict[str, int]] = {
    CultureDimension.autonomy: {
        "ownership": 15,
        "autonomy": 15,
        "independent": 10,
        "micromanagement": -25,
        "bureaucracy": -15,
    },
    CultureDimension.collaboration: {
        "collaborative": 15,
        "teamwork": 12,
        "cross-functional": 10,
        "silo": -15,
        "politics": -10,
    },
    CultureDimension.structure: {
        "process": 10,
        "structured": 15,
        "clear expectations": 18,
        "ambiguity": -12,
        "chaos": -20,
    },
    CultureDimension.pace: {
        "fast-paced": 15,
        "high pressure": 12,
        "crunch": -30,
        "burnout": -25,
        "deadline": 10,
    },
    CultureDimension.learning: {
        "mentorship": 18,
        "learning": 12,
        "growth": 12,
        "career development": 18,
        "stagnant": -20,
    },
    CultureDimension.work_life_balance: {
        "work-life balance": 25,
        "wlb": 18,
        "flexible": 12,
        "late nights": -25,
        "weekend": -20,
        "on-call": -10,
    },
    CultureDimension.feedback: {
        "feedback": 15,
        "performance review": 12,
        "1:1": 12,
        "blame": -20,
        "toxic": -25,
    },
    CultureDimension.mission: {
        "mission": 12,
        "impact": 15,
        "customer obsessed": 12,
        "meaningful": 12,
        "pointless": -20,
    },
}

_SENTIMENT_TERMS: dict[SentimentLabel, set[str]] = {
    SentimentLabel.positive: {"great", "supportive", "excellent", "amazing", "good"},
    SentimentLabel.negative: {"toxic", "terrible", "awful", "burnout", "crunch"},
}


@dataclass(frozen=True)
class CultureFitAnalyzer:
    """Deterministic culture-fit engine (rule-based, test-friendly).

    This implementation is intentionally conservative: it produces stable results
    without relying on network access or LLMs. Higher-fidelity extraction can be
    layered on later (e.g., LLM refinement) behind an interface while keeping
    unit tests pure.
    """

    default_unknown_score: int = 50

    # -----------------
    # Profiles
    # -----------------
    def normalize_user_profile(self, profile: UserValuesProfile) -> UserValuesProfile:
        """Ensure the user profile has a dense values vector."""
        dense = profile.values.normalized(default_value=self.default_unknown_score)
        return UserValuesProfile(values=CultureVector(dimensions=dense), notes=profile.notes)

    def extract_company_profile(
        self,
        *,
        reviews: list[str],
        discussions: list[str],
        extra_keywords: list[str] | None = None,
    ) -> CompanyCultureProfile:
        """Infer a company culture profile from text corpora."""
        corpus = _dedupe_keep_order([*reviews, *discussions])
        text = "\n".join(corpus).lower()

        dim_scores: dict[CultureDimension, int] = {}
        evidence: list[str] = []
        keywords: list[str] = []

        for dim in DEFAULT_DIMENSIONS:
            score = self.default_unknown_score
            for kw, delta in _DIMENSION_KEYWORDS.get(dim, {}).items():
                if kw in text:
                    score = _clamp_0_100(score + delta)
                    ex = _safe_excerpt(kw)
                    if ex:
                        evidence.append(f"Matched '{kw}' for {dim.value}")
                        keywords.append(kw)
            dim_scores[dim] = score

        sentiment = self._infer_sentiment(text)
        if extra_keywords:
            keywords.extend(extra_keywords)

        return CompanyCultureProfile(
            culture=CultureVector(dimensions=dim_scores),
            keywords=_dedupe_keep_order(keywords)[:30],
            sentiment=sentiment,
            evidence_excerpts=_dedupe_keep_order(evidence)[:20],
        )

    # -----------------
    # Scoring
    # -----------------
    def calculate_fit(
        self,
        *,
        user: UserValuesProfile,
        company: CompanyCultureProfile,
    ) -> FitScoreBreakdown:
        """Compute alignment score in [0, 100] with per-dimension breakdown."""
        user_dense = user.values.normalized(default_value=self.default_unknown_score)
        company_dense = company.culture.normalized(default_value=self.default_unknown_score)

        by_dim: list[FitDimensionScore] = []
        total = 0.0
        for dim in DEFAULT_DIMENSIONS:
            u = int(user_dense[dim])
            c = int(company_dense[dim])
            delta = c - u
            score = _clamp_0_100(100 - abs(delta))
            by_dim.append(
                FitDimensionScore(
                    dimension=dim,
                    user=u,
                    company=c,
                    score=score,
                    delta=delta,
                )
            )
            total += score

        overall = _clamp_0_100(total / max(1, len(DEFAULT_DIMENSIONS)))
        return FitScoreBreakdown(overall=overall, by_dimension=by_dim)

    # -----------------
    # Output helpers
    # -----------------
    def build_radar(
        self, *, user: UserValuesProfile, company: CompanyCultureProfile
    ) -> RadarChartData:
        user_dense = user.values.normalized(default_value=self.default_unknown_score)
        company_dense = company.culture.normalized(default_value=self.default_unknown_score)
        labels = [dim.value.replace("_", " ").title() for dim in DEFAULT_DIMENSIONS]
        return RadarChartData(
            labels=labels,
            user_values=[int(user_dense[d]) for d in DEFAULT_DIMENSIONS],
            company_values=[int(company_dense[d]) for d in DEFAULT_DIMENSIONS],
        )

    def generate_talking_points(
        self,
        *,
        fit: FitScoreBreakdown,
        company: CompanyCultureProfile,
        max_strengths: int = 3,
        max_risks: int = 3,
        max_questions: int = 5,
    ) -> list[TalkingPoint]:
        strengths = sorted(
            [d for d in fit.by_dimension if d.score >= 80],
            key=lambda x: x.score,
            reverse=True,
        )[: max(0, int(max_strengths))]

        risks = sorted(
            [d for d in fit.by_dimension if d.score <= 60],
            key=lambda x: x.score,
        )[: max(0, int(max_risks))]

        points: list[TalkingPoint] = []

        for d in strengths:
            points.append(
                TalkingPoint(
                    type=TalkingPointType.strength,
                    dimension=d.dimension,
                    title=f"Strong match on {d.dimension.value.replace('_', ' ')}",
                    detail=(
                        f"Your preference ({d.user}/100) aligns with the likely company signal "
                        f"({d.company}/100). Use this to build rapport and show fit."
                    ),
                )
            )

        for d in risks:
            direction = "higher" if d.delta < 0 else "lower"
            points.append(
                TalkingPoint(
                    type=TalkingPointType.risk,
                    dimension=d.dimension,
                    title=f"Potential mismatch on {d.dimension.value.replace('_', ' ')}",
                    detail=(
                        f"The company signal ({d.company}/100) looks {direction} than your preference "
                        f"({d.user}/100). Validate early so you don’t accept a role with a hidden cost."
                    ),
                )
            )

        if company.sentiment in {SentimentLabel.negative, SentimentLabel.mixed}:
            points.append(
                TalkingPoint(
                    type=TalkingPointType.risk,
                    dimension=None,
                    title="Culture sentiment appears mixed/negative",
                    detail=(
                        "Signals include negative sentiment keywords. Treat this as a hypothesis and "
                        "ask targeted questions to confirm whether the team you’re joining differs."
                    ),
                )
            )

        questions = self._validation_questions(fit=fit, max_questions=max_questions)
        points.extend(questions)
        return points

    def analyze(
        self,
        *,
        company: str,
        role: str | None,
        user_profile: UserValuesProfile,
        reviews: list[str],
        discussions: list[str],
        extra_keywords: list[str] | None = None,
    ) -> CultureFitAnalysisResult:
        user_norm = self.normalize_user_profile(user_profile)
        company_profile = self.extract_company_profile(
            reviews=reviews,
            discussions=discussions,
            extra_keywords=extra_keywords,
        )
        fit = self.calculate_fit(user=user_norm, company=company_profile)
        radar = self.build_radar(user=user_norm, company=company_profile)
        talking = self.generate_talking_points(fit=fit, company=company_profile)
        return CultureFitAnalysisResult(
            company=company,
            role=role,
            user_profile=user_norm,
            company_profile=company_profile,
            fit=fit,
            radar=radar,
            talking_points=talking,
        )

    # -----------------
    # Internal helpers
    # -----------------
    def _infer_sentiment(self, text: str) -> SentimentLabel:
        t = text.lower()
        pos = sum(1 for w in _SENTIMENT_TERMS[SentimentLabel.positive] if w in t)
        neg = sum(1 for w in _SENTIMENT_TERMS[SentimentLabel.negative] if w in t)
        if pos and not neg:
            return SentimentLabel.positive
        if neg and not pos:
            return SentimentLabel.negative
        if pos and neg:
            return SentimentLabel.mixed
        return SentimentLabel.neutral

    def _validation_questions(
        self, *, fit: FitScoreBreakdown, max_questions: int
    ) -> list[TalkingPoint]:
        candidates = sorted(fit.by_dimension, key=lambda x: x.score)
        out: list[TalkingPoint] = []
        for d in candidates:
            if len(out) >= max(0, int(max_questions)):
                break
            dim_label = d.dimension.value.replace("_", " ")
            out.append(
                TalkingPoint(
                    type=TalkingPointType.question,
                    dimension=d.dimension,
                    title=f"Validate {dim_label}",
                    detail=self._question_template(d.dimension, delta=d.delta),
                )
            )
        return out

    @staticmethod
    def _question_template(dim: CultureDimension, *, delta: int) -> str:
        direction = "more" if delta > 0 else "less"
        if dim == CultureDimension.work_life_balance:
            return (
                "What does a typical week look like (hours, on-call, after-hours messages), "
                "and how do you protect sustainable pace?"
            )
        if dim == CultureDimension.pace:
            return "How do you plan work and handle deadlines—what happens when scope expands or timelines slip?"
        if dim == CultureDimension.autonomy:
            return "How are decisions made day-to-day—what is expected to be owned by an IC vs decided by leads?"
        if dim == CultureDimension.structure:
            return "How do you run projects (planning, docs, reviews), and how much process is expected?"
        if dim == CultureDimension.collaboration:
            return (
                "How do teams partner cross-functionally, and what are common points of friction?"
            )
        if dim == CultureDimension.learning:
            return "What does growth look like here (mentorship, feedback loops, opportunities to learn new areas)?"
        if dim == CultureDimension.feedback:
            return "How do you give feedback and run performance reviews—what does success look like in the first 90 days?"
        if dim == CultureDimension.mission:
            return (
                f"What part of the mission is this team closest to, and how do you measure impact? "
                f"(I’m looking for {direction} mission alignment.)"
            )
        return "What should I know about the team’s culture, and what type of person thrives here?"


__all__ = ["CultureFitAnalyzer"]
