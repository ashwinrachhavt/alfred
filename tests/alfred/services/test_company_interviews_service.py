from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from alfred.schemas.company_insights import InterviewExperience, SourceInfo, SourceProvider
from alfred.schemas.company_interviews import InterviewProvider
from alfred.services.company_interviews import CompanyInterviewsService
from pymongo import UpdateOne


class _BulkResult:
    def __init__(self, *, upserted_count: int, modified_count: int) -> None:
        self.upserted_count = upserted_count
        self.modified_count = modified_count


class _FakeCursor:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def sort(self, sort_pairs):  # type: ignore[no-untyped-def]
        # Supports a single sort key for our tests.
        key, direction = sort_pairs[0]
        reverse = direction < 0
        self._rows.sort(key=lambda r: r.get(key), reverse=reverse)
        return self

    def skip(self, n: int):  # type: ignore[no-untyped-def]
        self._rows = self._rows[n:]
        return self

    def limit(self, n: int):  # type: ignore[no-untyped-def]
        self._rows = self._rows[:n]
        return self

    def __iter__(self):
        return iter(self._rows)


class _FakeCollection:
    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self.indexes: list[tuple[Any, dict[str, Any]]] = []

    def create_index(self, keys, **kwargs):  # type: ignore[no-untyped-def]
        self.indexes.append((keys, kwargs))
        return kwargs.get("name", "idx")

    def bulk_write(self, ops, ordered=False):  # type: ignore[no-untyped-def]
        upserted = 0
        modified = 0
        for op in ops:
            assert isinstance(op, UpdateOne)
            filt = op._filter  # noqa: SLF001
            doc = op._doc  # noqa: SLF001
            sid = filt.get("source_id")
            assert isinstance(sid, str)
            existing = self._docs.get(sid)
            if existing is None and op._upsert:  # noqa: SLF001
                new_doc = {}
                new_doc.update(doc.get("$setOnInsert", {}))
                new_doc.update(doc.get("$set", {}))
                self._docs[sid] = new_doc
                upserted += 1
            else:
                # Update in place
                if existing is None:
                    continue
                existing.update(doc.get("$set", {}))
                modified += 1
        return _BulkResult(upserted_count=upserted, modified_count=modified)

    def find(self, filt, projection):  # type: ignore[no-untyped-def]
        company = filt.get("company")
        provider = filt.get("provider")
        role = filt.get("role")
        rows: list[dict[str, Any]] = []
        for doc in self._docs.values():
            if company and doc.get("company") != company:
                continue
            if provider and doc.get("provider") != provider:
                continue
            if role and doc.get("role") != role:
                continue
            out = dict(doc)
            if projection.get("raw") == 0:
                out.pop("raw", None)
            rows.append(out)
        return _FakeCursor(rows)


class _FakeDatabase:
    def __init__(self, coll: _FakeCollection) -> None:
        self._coll = coll

    def get_collection(self, _name: str):  # type: ignore[no-untyped-def]
        return self._coll


@dataclass
class _FakeGlassdoorService:
    def get_interview_experiences_with_raw_sync(self, _company: str, *, max_interviews: int = 0):  # type: ignore[no-untyped-def]
        _ = max_interviews
        return [
            (
                InterviewExperience(
                    source=SourceProvider.glassdoor,
                    source_url="https://glassdoor.example/interview/1",
                    role="Backend Engineer",
                    process_summary="Phone + onsite",
                    questions=["Design a cache?"],
                ),
                {"job_title": "Backend Engineer", "link": "https://glassdoor.example/interview/1"},
            )
        ]


@dataclass
class _FakeBlindService:
    def search_interview_posts_sync(self, _company: str):  # type: ignore[no-untyped-def]
        return (
            [
                InterviewExperience(
                    source=SourceProvider.blind,
                    source_url="https://teamblind.example/post/abc",
                    role=None,
                    process_summary="Interview experience post",
                    questions=["Tell me about yourself?"],
                )
            ],
            [
                SourceInfo(
                    provider=SourceProvider.blind,
                    url="https://teamblind.example/post/abc",
                    title="Post",
                )
            ],
        )


def test_sync_inserts_and_lists_interviews_without_network():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = CompanyInterviewsService(
        database=db,  # type: ignore[arg-type]
        collection_name="company_interview_experiences",
        glassdoor_service=_FakeGlassdoorService(),
        blind_service=_FakeBlindService(),
    )

    svc.ensure_indexes()
    assert coll.indexes

    out = svc.sync_company_interviews(
        "ExampleCo",
        providers=(InterviewProvider.glassdoor, InterviewProvider.blind),
        refresh=True,
        max_items_per_provider=0,
    )
    assert out.company == "ExampleCo"
    assert out.inserted == 2
    assert out.total_seen == 2

    rows = svc.list_interviews(company="ExampleCo", limit=10, skip=0)
    assert len(rows) == 2
    assert {r["provider"] for r in rows} == {"glassdoor", "blind"}


def test_sync_is_idempotent_by_source_id():
    coll = _FakeCollection()
    db = _FakeDatabase(coll)
    svc = CompanyInterviewsService(
        database=db,  # type: ignore[arg-type]
        collection_name="company_interview_experiences",
        glassdoor_service=_FakeGlassdoorService(),
        blind_service=_FakeBlindService(),
    )

    svc.sync_company_interviews("ExampleCo", refresh=True)
    out2 = svc.sync_company_interviews("ExampleCo", refresh=True)
    # No new upserts after the first run (same URLs).
    assert out2.inserted == 0


def test_list_sorts_by_updated_at_desc():
    coll = _FakeCollection()
    now = datetime.now(timezone.utc)
    coll._docs["glassdoor|u1"] = {
        "company": "ExampleCo",
        "provider": "glassdoor",
        "updated_at": now,
    }
    coll._docs["blind|u2"] = {
        "company": "ExampleCo",
        "provider": "blind",
        "updated_at": now.replace(year=now.year - 1),
    }

    db = _FakeDatabase(coll)
    svc = CompanyInterviewsService(database=db, collection_name="company_interview_experiences")  # type: ignore[arg-type]
    rows = svc.list_interviews(company="ExampleCo", limit=10, skip=0)
    assert rows[0]["provider"] == "glassdoor"
