from __future__ import annotations

from typing import Any, List, Sequence, Tuple

from alfred.services.interview_prep import InterviewPrepService


class _FakeCollection:
    def __init__(self) -> None:
        self.created: List[Tuple[Sequence[tuple[str, int]], str]] = []

    def create_index(self, keys: Sequence[tuple[str, int]], name: str) -> None:
        self.created.append((tuple(keys), name))


class _FakeDatabase:
    def __init__(self, coll: _FakeCollection) -> None:
        self._coll = coll

    def get_collection(self, _name: str):
        return self._coll


def test_interview_prep_ensure_indexes_best_effort():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = InterviewPrepService(  # type: ignore[arg-type]
        database=db,
        collection_name="interview_preps",
    )
    svc.ensure_indexes()

    names = {name for _keys, name in coll.created}
    assert {"job_app_id", "company", "interview_date", "generated_at_desc"} <= names


def test_interview_prep_ensure_indexes_swallow_errors():
    class _ExplodingCollection(_FakeCollection):
        def create_index(self, keys: Any, name: str) -> None:  # type: ignore[override]
            raise RuntimeError("boom")

    coll = _ExplodingCollection()
    db = _FakeDatabase(coll)
    svc = InterviewPrepService(  # type: ignore[arg-type]
        database=db,
        collection_name="interview_preps",
    )
    svc.ensure_indexes()  # should not raise
