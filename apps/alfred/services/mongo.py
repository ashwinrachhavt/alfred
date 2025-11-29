"""High-level MongoDB service built on the Mongo connector."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from pymongo.collection import Collection

from alfred.connectors.mongo_connector import MongoConnector

SortPairs = Sequence[tuple[str, int]]


class MongoService:
    """Convenience helpers for common MongoDB CRUD operations."""

    def __init__(
        self,
        connector: MongoConnector | None = None,
        *,
        default_collection: str | None = None,
    ) -> None:
        self._connector = connector or MongoConnector()
        self._default_collection = default_collection

    def _collection(self, name: str | None) -> Collection:
        actual = (name or self._default_collection or "").strip()
        if not actual:
            raise ValueError("A collection name must be provided.")
        return self._connector.get_collection(actual)

    def ping(self) -> bool:
        return self._connector.ping()

    def insert_one(self, document: Mapping[str, Any], *, collection: str | None = None) -> str:
        result = self._collection(collection).insert_one(dict(document))
        return str(result.inserted_id)

    def insert_many(
        self,
        documents: Iterable[Mapping[str, Any]],
        *,
        collection: str | None = None,
        ordered: bool = True,
    ) -> list[str]:
        result = self._collection(collection).insert_many(
            [dict(doc) for doc in documents], ordered=ordered
        )
        return [str(obj_id) for obj_id in result.inserted_ids]

    def find_one(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        projection: Mapping[str, Any] | None = None,
        collection: str | None = None,
    ) -> dict[str, Any] | None:
        return self._collection(collection).find_one(filter_ or {}, projection)

    def find_many(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        projection: Mapping[str, Any] | None = None,
        sort: SortPairs | None = None,
        limit: int | None = None,
        collection: str | None = None,
    ) -> list[dict[str, Any]]:
        cursor = self._collection(collection).find(filter_ or {}, projection)
        if sort:
            cursor = cursor.sort(list(sort))
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)

    def update_one(
        self,
        filter_: Mapping[str, Any],
        update: Mapping[str, Any],
        *,
        upsert: bool = False,
        collection: str | None = None,
    ) -> dict[str, Any]:
        result = self._collection(collection).update_one(filter_, update, upsert=upsert)
        return {
            "matched_count": result.matched_count,
            "modified_count": result.modified_count,
            "upserted_id": str(result.upserted_id) if result.upserted_id else None,
        }

    def delete_one(
        self,
        filter_: Mapping[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        return self._collection(collection).delete_one(filter_).deleted_count

    def delete_many(
        self,
        filter_: Mapping[str, Any],
        *,
        collection: str | None = None,
    ) -> int:
        return self._collection(collection).delete_many(filter_).deleted_count

    def count(
        self,
        filter_: Mapping[str, Any] | None = None,
        *,
        collection: str | None = None,
    ) -> int:
        return self._collection(collection).count_documents(filter_ or {})

    def with_collection(self, name: str) -> "MongoService":
        return MongoService(self._connector, default_collection=name)
