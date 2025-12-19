"""MongoDB connector built on top of PyMongo."""

from __future__ import annotations

from typing import Any, ContextManager

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from pymongo.errors import PyMongoError

from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings


class MongoConnector(ContextManager["MongoConnector"]):
    """Thin wrapper around :class:`pymongo.MongoClient`."""

    def __init__(
        self,
        uri: str | None = None,
        database: str | None = None,
        *,
        app_name: str | None = None,
        client: MongoClient | None = None,
        tz_aware: bool = True,
    ) -> None:
        self._uri = (uri or settings.mongo_uri).strip()
        if not self._uri:
            raise ConfigurationError("Mongo URI is required. Set MONGO_URI in the environment.")

        self._database_name = (database or settings.mongo_database).strip()
        if not self._database_name:
            raise ConfigurationError(
                "Mongo database name is required. Set MONGO_DATABASE in the environment."
            )

        self._app_name = (app_name or settings.mongo_app_name).strip() or "alfred"
        self._client = client or MongoClient(
            self._uri,
            appname=self._app_name,
            tz_aware=tz_aware,
            uuidRepresentation="standard",
        )
        self._database = self._client[self._database_name]

    @property
    def client(self) -> MongoClient:
        return self._client

    @property
    def database(self) -> Database:
        return self._database

    def get_collection(self, name: str) -> Collection:
        name = name.strip()
        if not name:
            raise ConfigurationError("Collection name cannot be empty.")
        return self._database[name]

    def ping(self) -> bool:
        try:
            self._client.admin.command("ping")
        except PyMongoError as exc:  # pragma: no cover - network call
            raise RuntimeError("Unable to reach MongoDB instance") from exc
        return True

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "MongoConnector":
        return self

    def __exit__(self, exc_type: Any, exc: Any, exc_tb: Any) -> None:
        self.close()
