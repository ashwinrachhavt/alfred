"""Postgres-backed document store (previously MongoService-compatible).

Implements a small subset of Mongo-style CRUD APIs used by the codebase.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import sqlalchemy as sa
from pydantic_core import to_jsonable_python
from sqlmodel import Session, select

from alfred.core.database import SessionLocal
from alfred.core.utils import utcnow
from alfred.models.datastore import DataStoreRow

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


def _jsonable_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a document to a JSON-serializable Python dict.

    Postgres JSON/JSONB columns require values that `json.dumps` can handle. We
    normalize common non-JSON types (e.g. datetime) to stable representations.
    """

    converted = to_jsonable_python(dict(document))
    if not isinstance(converted, dict):
        raise TypeError("Document must serialize to a JSON object.")
    return converted


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


def _json_path_expr(path: Sequence[str]) -> Any:
    expr: Any = DataStoreRow.data
    for part in path:
        expr = expr[part]
    return expr


def _json_scalar(expr: Any, value: Any) -> Any:
    if isinstance(value, bool):
        return expr.as_boolean()
    if isinstance(value, int) and not isinstance(value, bool):
        return expr.as_integer()
    if isinstance(value, float):
        return expr.as_float()
    return expr.as_string()


def _jsonable_scalar(value: Any) -> Any:
    """Convert a value to the scalar representation stored in JSON columns."""

    converted = to_jsonable_python(value)
    if isinstance(converted, (dict, list)):
        raise TypeError("Filter values must be scalar for SQL-backed filtering.")
    return converted


def _build_where_clause(filter_: Mapping[str, Any]) -> sa.ColumnElement[bool] | None:
    """Build a SQL WHERE clause for a small, safe subset of Mongo-style filters.

    Supported:
    - Exact matches on `_id` via `DataStoreRow.doc_id`
    - Exact matches on JSON fields (including dot-paths)
    - `$ne` on `_id` and JSON fields

    Anything else falls back to in-Python filtering to preserve behavior.
    """

    if not filter_:
        return None

    clauses: list[sa.ColumnElement[bool]] = []
    for key, cond in filter_.items():
        if key == "_id":
            if isinstance(cond, dict):
                if set(cond.keys()) != {"$ne"}:
                    return None
                clauses.append(DataStoreRow.doc_id != _normalize_id(cond["$ne"]))
            else:
                clauses.append(DataStoreRow.doc_id == _normalize_id(cond))
            continue

        path = key.split(".")
        expr = _json_path_expr(path)
        if isinstance(cond, dict):
            if set(cond.keys()) != {"$ne"}:
                return None
            try:
                value = _jsonable_scalar(cond["$ne"])
            except TypeError:
                return None
            clauses.append(_json_scalar(expr, value) != value)
        else:
            try:
                value = _jsonable_scalar(cond)
            except TypeError:
                return None
            clauses.append(_json_scalar(expr, value) == value)

    if not clauses:
        return None
    return sa.and_(*clauses)


class DataStoreService:
    """Lightweight document store emulating a subset of Mongo APIs on Postgres JSON."""

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
        row = DataStoreRow(collection=coll, doc_id=_id, data=_jsonable_document(doc))
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
        rows: list[DataStoreRow] = []
        for doc in documents:
            d = dict(doc)
            _id = _normalize_id(d.get("_id") or uuid.uuid4())
            d["_id"] = _id
            ids.append(_id)
            rows.append(DataStoreRow(collection=coll, doc_id=_id, data=_jsonable_document(d)))
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
        flt = filter_ or {}
        clause = _build_where_clause(flt)
        with self._session() as s:
            if clause is not None:
                row = s.exec(
                    select(DataStoreRow)
                    .where(DataStoreRow.collection == coll)
                    .where(clause)
                    .limit(1)
                ).first()
                return dict(row.data) if row else None

            rows = s.exec(select(DataStoreRow).where(DataStoreRow.collection == coll)).all()
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
        flt = filter_ or {}
        clause = _build_where_clause(flt)
        with self._session() as s:
            if clause is not None:
                stmt = select(DataStoreRow).where(DataStoreRow.collection == coll).where(clause)
                if sort:
                    order_by: list[Any] = []
                    for field, direction in sort:
                        if field == "_id":
                            col = DataStoreRow.doc_id
                        else:
                            col = _json_scalar(_json_path_expr(field.split(".")), "")
                        order_by.append(col.desc() if direction < 0 else col.asc())
                    stmt = stmt.order_by(*order_by)
                if limit:
                    stmt = stmt.limit(limit)
                rows = s.exec(stmt).all()
                return [dict(r.data) for r in rows]

            rows = s.exec(select(DataStoreRow).where(DataStoreRow.collection == coll)).all()
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
        clause = _build_where_clause(filter_)
        with self._session() as s:
            target = None
            if clause is not None:
                target = s.exec(
                    select(DataStoreRow)
                    .where(DataStoreRow.collection == coll)
                    .where(clause)
                    .limit(1)
                ).first()
            else:
                rows = s.exec(select(DataStoreRow).where(DataStoreRow.collection == coll)).all()
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
                new_row = DataStoreRow(collection=coll, doc_id=_id, data=_jsonable_document(base))
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
            target.data = _jsonable_document(doc)
            target.updated_at = utcnow()
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
            clause = _build_where_clause(filter_)
            if clause is not None:
                row = s.exec(
                    select(DataStoreRow)
                    .where(DataStoreRow.collection == coll)
                    .where(clause)
                    .limit(1)
                ).first()
                if row is None:
                    return 0
                s.delete(row)
                s.commit()
                return 1

            rows = s.exec(select(DataStoreRow).where(DataStoreRow.collection == coll)).all()
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
            clause = _build_where_clause(filter_)
            if clause is not None:
                rows = s.exec(
                    select(DataStoreRow).where(DataStoreRow.collection == coll).where(clause)
                ).all()
            else:
                rows = s.exec(select(DataStoreRow).where(DataStoreRow.collection == coll)).all()
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
        coll = self._collection(collection)
        flt = filter_ or {}
        clause = _build_where_clause(flt)
        if clause is None:
            return len(self.find_many(flt, collection=coll))
        with self._session() as s:
            return int(
                s.exec(
                    sa.select(sa.func.count())
                    .select_from(DataStoreRow)
                    .where(DataStoreRow.collection == coll)
                    .where(clause)
                ).one()
            )

    def with_collection(self, name: str) -> "DataStoreService":
        return DataStoreService(default_collection=name)

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
            # UpdateOne objects from previous Mongo layer store internals on private attrs
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
