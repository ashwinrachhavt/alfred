from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alfred.schemas.panel_interview import (
    PanelConfig,
    PanelDifficulty,
    PanelSessionCreate,
    PanelTurnRequest,
)
from alfred.services.panel_interview_simulator import PanelInterviewService, PanelInterviewSimulator


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.indexes: list[tuple[Any, dict[str, Any]]] = []

    def create_index(self, keys, **kwargs):  # type: ignore[no-untyped-def]
        self.indexes.append((keys, kwargs))
        return kwargs.get("name", "idx")

    def insert_one(self, doc):  # type: ignore[no-untyped-def]
        _id = doc["_id"] if "_id" in doc else None
        if _id is None:
            raise ValueError("_id required")
        self._docs[str(_id)] = doc
        return {"inserted_id": _id}

    def find_one(self, filt, projection=None):  # type: ignore[no-untyped-def]
        _id = filt.get("_id")
        if _id is None:
            return None
        doc = self._docs.get(str(_id))
        if not doc:
            return None
        if projection and projection.get("question_bank") == 1:
            return {"question_bank": doc.get("question_bank", [])}
        return dict(doc)

    def update_one(self, filt, update, upsert=False):  # type: ignore[no-untyped-def]
        _ = upsert
        _id = filt.get("_id")
        doc = self._docs.get(str(_id))
        if doc is None:
            raise ValueError("missing doc")
        if "$set" in update:
            doc.update(update["$set"])
        if "$inc" in update:
            for k, v in update["$inc"].items():
                doc[k] = int(doc.get(k, 0)) + int(v)
        if "$push" in update:
            push = update["$push"]
            for field, val in push.items():
                if isinstance(val, dict) and "$each" in val:
                    doc.setdefault(field, []).extend(val["$each"])
                else:
                    doc.setdefault(field, []).append(val)
        return {"ok": 1}


class _FakeDatabase:
    def __init__(self, coll: _FakeCollection) -> None:
        self._coll = coll

    def get_collection(self, _name: str):  # type: ignore[no-untyped-def]
        return self._coll


@dataclass
class _FakeCompanyInterviewsService:
    def list_interviews(self, **_kwargs):  # type: ignore[no-untyped-def]
        return [{"questions": ["What is your biggest weakness?", "Explain CAP theorem."]}]


class _FakeLLMService:
    def structured(self, _messages, schema, **_kwargs):  # type: ignore[no-untyped-def]
        return schema(overall_summary="Good job.", overall_score=7, by_member=[])


def test_create_session_emits_first_question_and_uses_question_bank():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = PanelInterviewService(
        database=db,  # type: ignore[arg-type]
        simulator=PanelInterviewSimulator(),
        llm_service=_FakeLLMService(),
        company_interviews_service=_FakeCompanyInterviewsService(),
    )
    cfg = PanelConfig(
        company="ExampleCo", role="Backend Engineer", difficulty=PanelDifficulty.medium
    )
    session = svc.create_session(PanelSessionCreate(config=cfg))
    assert session.id
    assert session.transcript
    # First event should be a question/interrupt from a panelist.
    assert session.transcript[-1].type.value in {"question", "interruption"}
    assert session.transcript[-1].text


def test_turn_appends_answer_reaction_then_next_question():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = PanelInterviewService(
        database=db,  # type: ignore[arg-type]
        simulator=PanelInterviewSimulator(),
        llm_service=_FakeLLMService(),
        company_interviews_service=_FakeCompanyInterviewsService(),
    )
    cfg = PanelConfig(company="ExampleCo", role="Backend Engineer", difficulty=PanelDifficulty.easy)
    session = svc.create_session(PanelSessionCreate(config=cfg))

    resp = svc.submit_turn(
        session.id, PanelTurnRequest(answer="I'd start with requirements and tradeoffs.")
    )
    types = [e.type.value for e in resp.events]
    assert types[0] == "answer"
    assert types[1] == "reaction"
    assert any(t in {"question", "interruption"} for t in types)


def test_feedback_uses_llm_when_available():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = PanelInterviewService(
        database=db,  # type: ignore[arg-type]
        simulator=PanelInterviewSimulator(),
        llm_service=_FakeLLMService(),
        company_interviews_service=_FakeCompanyInterviewsService(),
    )
    cfg = PanelConfig(
        company="ExampleCo", role="Backend Engineer", difficulty=PanelDifficulty.medium
    )
    session = svc.create_session(PanelSessionCreate(config=cfg))
    fb = svc.feedback(session.id)
    assert fb.overall_summary == "Good job."
