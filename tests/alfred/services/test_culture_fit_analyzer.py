from __future__ import annotations

from alfred.schemas.culture_fit import CultureDimension, UserValuesProfile
from alfred.services.culture_fit import CultureFitAnalyzer


def test_analyzer_scores_and_radar_are_stable():
    analyzer = CultureFitAnalyzer()

    user = UserValuesProfile(
        values={
            "dimensions": {
                CultureDimension.work_life_balance: 80,
                CultureDimension.autonomy: 70,
            }
        },
        notes="Prefer calm, high-trust teams.",
    )

    result = analyzer.analyze(
        company="ExampleCo",
        role="Backend Engineer",
        user_profile=user,
        reviews=[
            "Great work-life balance and flexible hours.",
            "Lots of ownership and autonomy.",
        ],
        discussions=[
            "Some teams struggle with micromanagement.",
            "Supportive managers, good feedback culture.",
        ],
        extra_keywords=["ownership", "flexible"],
    )

    assert result.company == "ExampleCo"
    assert result.role == "Backend Engineer"
    assert result.fit.overall >= 0
    assert len(result.fit.by_dimension) > 0
    assert (
        len(result.radar.labels)
        == len(result.radar.user_values)
        == len(result.radar.company_values)
    )

    by_dim = {d.dimension: d for d in result.fit.by_dimension}
    assert by_dim[CultureDimension.work_life_balance].company >= 75
    assert by_dim[CultureDimension.autonomy].company <= 60
