"""Postgres-backed stand-in for the old Mongo connector."""

from __future__ import annotations

from typing import Any, ContextManager, Iterable, Mapping, Sequence

from alfred.services.mongo import MongoService


class ProxyCollection:
    """Minimal collection wrapper delegating to MongoService."""

    def __init__(self, service: MongoService, name: str):
        self._service = service
        self._name = name

    # CRUD
    def insert_one(self, document: Mapping[str, Any]):
        inserted_id = self._service.insert_one(document, collection=self._name)

        class Result:
            def __init__(self, _id: str):
                self.inserted_id = _id

        return Result(inserted_id)

    def insert_many(self, documents: Iterable[Mapping[str, Any]], ordered: bool = True):
        ids = self._service.insert_many(documents, collection=self._name, ordered=ordered)

        class Result:
            def __init__(self, _ids):
                self.inserted_ids = _ids

        return Result(ids)

    def find_one(self, filter_: Mapping[str, Any] | None = None, projection=None):
        return self._service.find_one(filter_, projection=projection, collection=self._name)

    def find(self, filter_: Mapping[str, Any] | None = None, projection=None):
        docs = self._service.find_many(filter_, projection=projection, collection=self._name)

        class Cursor(list):
            def sort(self, sort_pairs: Sequence[tuple[str, int]]):
                res = self
                for key, direction in reversed(sort_pairs):
                    reverse = direction < 0
                    res.sort(key=lambda d: d.get(key), reverse=reverse)
                return res

            def skip(self, n: int):
                return Cursor(self[n:])

            def limit(self, n: int):
                return Cursor(self[:n])

        return Cursor(docs)

    def update_one(
        self, filter_: Mapping[str, Any], update: Mapping[str, Any], upsert: bool = False
    ):
        class Result:
            def __init__(self, payload: dict[str, Any]):
                self.matched_count = payload.get("matched_count", 0)
                self.modified_count = payload.get("modified_count", 0)
                self.upserted_id = payload.get("upserted_id")

        payload = self._service.update_one(filter_, update, upsert=upsert, collection=self._name)
        return Result(payload)

    def delete_one(self, filter_: Mapping[str, Any]):
        deleted = self._service.delete_one(filter_, collection=self._name)

        class Result:
            def __init__(self, count: int):
                self.deleted_count = count

        return Result(deleted)

    def delete_many(self, filter_: Mapping[str, Any]):
        deleted = self._service.delete_many(filter_, collection=self._name)

        class Result:
            def __init__(self, count: int):
                self.deleted_count = count

        return Result(deleted)

    def count_documents(self, filter_: Mapping[str, Any]):
        return self._service.count(filter_, collection=self._name)

    # Index stubs (no-op but keep API parity)
    def create_index(self, *args, **kwargs):
        return None

    def bulk_write(self, operations, ordered: bool = True):
        payload = self._service.bulk_write(operations, ordered=ordered, collection=self._name)

        class Result:
            def __init__(self, data: dict[str, Any]):
                self.modified_count = data.get("modified_count", 0)
                self.upserted_count = data.get("upserted_count", 0)

        return Result(payload)


class MongoConnector(ContextManager["MongoConnector"]):
    """Context manager returning ProxyCollections backed by Postgres."""

    def __init__(self, *args, database: str | None = None, **kwargs) -> None:
        self._service = MongoService()
        self._database = self  # back-compat placeholder

    @property
    def database(self):
        return self

    def get_collection(self, name: str) -> ProxyCollection:
        return ProxyCollection(self._service, name.strip())

    def ping(self) -> bool:
        return self._service.ping()

    def __enter__(self) -> "MongoConnector":
        return self

    def __exit__(self, exc_type: Any, exc: Any, exc_tb: Any) -> None:
        return None
