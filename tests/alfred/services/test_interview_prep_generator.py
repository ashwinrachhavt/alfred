from __future__ import annotations

from datetime import datetime, timezone

import pytest
from alfred.schemas.interview_prep import PrepDoc
from alfred.services.interview_prep_generator import InterviewPrepDocGenerator


class _FakeLLM:
    def __init__(self, *, structured_ok: bool) -> None:
        self.structured_ok = structured_ok

    def structured(self, *, messages, schema):  # noqa: ANN001
        if not self.structured_ok:
            raise RuntimeError("structured not available")
        return PrepDoc(
            company_overview="Company",
            role_analysis="Role",
            star_stories=[],
            likely_questions=[],
            technical_topics=[],
        )

    def chat(self, *, messages):  # noqa: ANN001
        return (
            "{"
            '"company_overview":"Company",'
            '"role_analysis":"Role",'
            '"star_stories":[],'
            '"likely_questions":[],'
            '"technical_topics":[]'
            "}"
        )


class _FakeCompanyResearch:
    def get_cached_report(self, company: str):  # noqa: ANN001
        return {"company": company, "report": {"executive_summary": "x"}}


class _FakeDocStorage:
    def list_notes(self, *, q: str, skip: int, limit: int):  # noqa: ANN001
        return {"items": [{"text": f"note for {q}"}]}


def test_generator_uses_structured_when_available():
    gen = InterviewPrepDocGenerator(
        llm=_FakeLLM(structured_ok=True),
        company_research_service=_FakeCompanyResearch(),
        doc_storage=_FakeDocStorage(),
    )
    doc = gen.generate_prep_doc(
        company="ExampleCo",
        role="Backend Engineer",
        interview_type="phone",
        interview_date=datetime(2026, 1, 5, tzinfo=timezone.utc),
        candidate_background="Worked on X.",
    )
    assert isinstance(doc, PrepDoc)
    assert doc.company_overview


def test_generator_falls_back_to_chat_json():
    gen = InterviewPrepDocGenerator(
        llm=_FakeLLM(structured_ok=False),
        company_research_service=_FakeCompanyResearch(),
        doc_storage=_FakeDocStorage(),
    )
    doc = gen.generate_prep_doc(company="ExampleCo", role="Backend Engineer")
    assert doc.role_analysis == "Role"


def test_generator_requires_company_and_role():
    gen = InterviewPrepDocGenerator(
        llm=_FakeLLM(structured_ok=True),
        company_research_service=_FakeCompanyResearch(),
        doc_storage=_FakeDocStorage(),
    )
    with pytest.raises(ValueError):
        gen.generate_prep_doc(company=" ", role="Backend Engineer")
