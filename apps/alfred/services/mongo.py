"""Postgres-backed drop-in replacement for the previous MongoService.

Implements a small subset of Mongo-style CRUD APIs used by the codebase.
"""

from __future__ import annotations

import uuid
from typing import Any, Iterable, Mapping, Sequence

import sqlalchemy as sa
from sqlmodel import Session, select

from alfred.core.database import SessionLocal
from alfred.models.mongo_store import MongoDocRow

SortPairs = Sequence[tuple[str, int]]


def _ensure_collection(name: str | None) -> str:
    actual = (name or "").strip()
    if not actual:
        raise ValueError("A collection name must be provided.")
    return actual


def _normalize_id(value: Any) -> str:
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def _match_filter(doc: dict[str, Any], flt: Mapping[str, Any]) -> bool:
    for key, cond in flt.items():
        if key == "_id":
            if isinstance(cond, dict) and "$ne" in cond:
                if doc.get("_id") == _normalize_id(cond["$ne"]):
                    return False
            elif doc.get("_id") != _normalize_id(cond):
                return False
            continue
        # dot path support
        parts = key.split(".")
        val = doc
        for p in parts:
            if not isinstance(val, dict) or p not in val:
                val = None
                break
            val = val[p]
        if isinstance(cond, dict):
            if "$ne" in cond:
                if val == cond["$ne"]:
                    return False
            elif "$regex" in cond:
                import re

                pattern = cond["$regex"]
                opts = cond.get("$options", "")
                flags = re.IGNORECASE if "i" in opts else 0
                if not isinstance(val, str) or re.search(pattern, val, flags=flags) is None:
                    return False
            else:
                # unsupported operator
                return False
        else:
            if val != cond:
                return False
    return True


class MongoService:
    """Lightweight emulation of Mongo collections using Postgres JSONB."""

    def __init__(self, connector: None = None, *, default_collection: str | None = None) -> None:
        self._default_collection = default_collection

    # ------------- helpers -------------
    def _session(self) -> Session:
        return SessionLocal()

    def _collection(self, name: str | None) -> str:
        return _ensure_collection(name or self._default_collection)

    # ------------- ops -------------
    def ping(self) -> bool:
        with self._session() as s:
            s.exec(sa.text("SELECT 1")).one()
        return True

    def insert_one(self, document: Mapping[str, Any], *, collection: str | None = None) -> str:
        coll = self._collection(collection)
        doc = dict(document)
        _id = _normalize_id(doc.get("_id") or uuid.uuid4())
        doc["_id"] = _id
        row = MongoDocRow(collection=coll, doc_id=_id, data=doc)
        with self._session() as s:
            s.add(row)
            s.commit()
        return _id

    def insert_many(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        collection: str | None = None,
        ordered: bool = True,
    ) -> list[str]:
        coll = self._collection(collection)
        ids: list[str] = []
        rows: list[MongoDocRow] = []
        for doc in documents:
            d = dict(doc)
            _id = _normalize_id(d.get("_id") or uuid.uuid4())
            d["_id"] = _id
            ids.append(_id)
            rows.append(MongoDocRow(collection=coll, doc_id=_id, data=d))
        with self._session() as s:
            s.add_all(rows)
            s.commit()
        return ids

    def find_one(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        projection: Mapping[str, Any] | None = None,
        collection: str | None = None,
    ) -> dict[str, Any] | None:
        coll = self._collection(collection)
        with self._session() as s:
            rows = s.exec(select(MongoDocRow).where(MongoDocRow.collection == coll)).all()
        flt = filter_ or {}
        for row in rows:
            doc = dict(row.data)
            if _match_filter(doc, flt):
                return doc
        return None

    def find_many(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        projection: Mapping[str, Any] | None = None,
        sort: SortPairs | None = None,
        limit: int | None = None,
        collection: str | None = None,
    ) -> list[dict[str, Any]]:
        coll = self._collection(collection)
        with self._session() as s:
            rows = s.exec(select(MongoDocRow).where(MongoDocRow.collection == coll)).all()
        flt = filter_ or {}
        docs = [dict(r.data) for r in rows if _match_filter(r.data, flt)]
        if sort:
            for field, direction in reversed(sort):
                reverse = direction < 0
                docs.sort(key=lambda d: d.get(field), reverse=reverse)
        if limit:
            docs = docs[:limit]
        return docs

    def update_one(
        self,
        filter_: Mapping[str, Any],
        update: Mapping[str, Any],
        *,
        upsert: bool = False,
        collection: str | None = None,
    ) -> dict[str, Any]:
        coll = self._collection(collection)
        with self._session() as s:
            rows = s.exec(select(MongoDocRow).where(MongoDocRow.collection == coll)).all()
            target = None
            for row in rows:
                if _match_filter(row.data, filter_):
                    target = row
                    break
            if target is None and upsert:
                # create new doc applying $set and $setOnInsert
                base: dict[str, Any] = {}
                set_on_insert = update.get("$setOnInsert") or {}
                set_doc = update.get("$set") or {}
                base.update(set_on_insert)
                base.update(set_doc)
                _id = _normalize_id(base.get("_id") or uuid.uuid4())
                base["_id"] = _id
                new_row = MongoDocRow(collection=coll, doc_id=_id, data=base)
                s.add(new_row)
                s.commit()
                return {"matched_count": 0, "modified_count": 0, "upserted_id": _id}

            if target is None:
                return {"matched_count": 0, "modified_count": 0, "upserted_id": None}

            doc = dict(target.data)
            modified = 0
            if "$set" in update:
                for k, v in update["$set"].items():
                    parts = k.split(".")
                    ref = doc
                    for p in parts[:-1]:
                        if p not in ref or not isinstance(ref[p], dict):
                            ref[p] = {}
                        ref = ref[p]
                    if ref.get(parts[-1]) != v:
                        modified += 1
                    ref[parts[-1]] = v
            if "$push" in update:
                for k, v in update["$push"].items():
                    parts = k.split(".")
                    ref = doc
                    for p in parts[:-1]:
                        if p not in ref or not isinstance(ref[p], dict):
                            ref[p] = {}
                        ref = ref[p]
                    arr = ref.get(parts[-1])
                    if not isinstance(arr, list):
                        arr = []
                    arr.append(v)
                    ref[parts[-1]] = arr
                    modified += 1
            # $setOnInsert is ignored on updates (Mongo behavior)
            target.data = doc
            s.add(target)
            s.commit()
            return {
                "matched_count": 1,
                "modified_count": modified,
                "upserted_id": None,
            }

    def delete_one(
        self,
        filter_: Mapping[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        coll = self._collection(collection)
        with self._session() as s:
            rows = s.exec(select(MongoDocRow).where(MongoDocRow.collection == coll)).all()
            for row in rows:
                if _match_filter(row.data, filter_):
                    s.delete(row)
                    s.commit()
                    return 1
        return 0

    def delete_many(
        self,
        filter_: Mapping[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        coll = self._collection(collection)
        deleted = 0
        with self._session() as s:
            rows = s.exec(select(MongoDocRow).where(MongoDocRow.collection == coll)).all()
            for row in rows:
                if _match_filter(row.data, filter_):
                    s.delete(row)
                    deleted += 1
            if deleted:
                s.commit()
        return deleted

    def count(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        collection: str | None = None,
    ) -> int:
        return len(self.find_many(filter_, collection=collection))

    def with_collection(self, name: str) -> "MongoService":
        return MongoService(default_collection=name)

    def bulk_write(
        self,
        operations: Iterable[Any],
        *,
        ordered: bool = True,
        collection: str | None = None,
    ) -> dict[str, Any]:
        """Simplified bulk_write supporting UpdateOne operations."""
        coll = self._collection(collection)
        modified = 0
        upserted = 0
        for op in operations:
            # pymongo UpdateOne stores internals on private attrs
            flt = getattr(op, "_filter", None)
            update = getattr(op, "_doc", None)
            upsert = getattr(op, "_upsert", False)
            if flt is None or update is None:
                continue
            res = self.update_one(flt, update, upsert=upsert, collection=coll)
            modified += res.get("modified_count", 0)
            if res.get("upserted_id"):
                upserted += 1
        return {
            "matched_count": None,  # not tracked
            "modified_count": modified,
            "upserted_count": upserted,
        }
