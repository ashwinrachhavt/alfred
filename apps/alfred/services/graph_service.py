from __future__ import annotations

import importlib.util
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_NEO4J_AVAILABLE = importlib.util.find_spec("neo4j") is not None

if _NEO4J_AVAILABLE:
    from neo4j import GraphDatabase  # type: ignore

    @dataclass
    class GraphService:
        """Thin wrapper around the Neo4j Python driver."""

        uri: str
        user: str
        password: str

        def __post_init__(self) -> None:
            self._driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
            logger.debug("GraphService connected to Neo4j at %s", self.uri)

        # --- internals ---
        def _run(self, query: str, params: Dict[str, Any] | None = None) -> list[dict[str, Any]]:
            with self._driver.session() as session:
                result = session.run(query, params or {})
                try:
                    return [dict(r) for r in result]
                except Exception:
                    return []

        def close(self) -> None:
            try:
                self._driver.close()
            except Exception:
                pass

        # --- public helpers ---
        def upsert_document_node(
            self, *, doc_id: str, title: Optional[str], source_url: Optional[str]
        ) -> None:
            query = """
            MERGE (d:Document {doc_id: $doc_id})
            SET d.title = coalesce($title, d.title),
                d.source_url = coalesce($source_url, d.source_url),
                d.updated_at = timestamp()
            """
            self._run(query, {"doc_id": doc_id, "title": title, "source_url": source_url})

        def upsert_entity(self, *, name: str, type_: Optional[str] = None) -> None:
            query = """
            MERGE (e:Entity {name: $name})
            SET e.type = coalesce($type, e.type),
                e.updated_at = timestamp()
            """
            self._run(query, {"name": name, "type": type_})

        def link_doc_to_entity(self, *, doc_id: str, name: str, rel_type: str = "MENTIONS") -> None:
            query = f"""
            MATCH (d:Document {{doc_id: $doc_id}})
            MATCH (e:Entity {{name: $name}})
            MERGE (d)-[r:{rel_type}]->(e)
            ON CREATE SET r.created_at = timestamp()
            """
            self._run(query, {"doc_id": doc_id, "name": name})

        def link_entities(self, *, from_name: str, to_name: str, rel_type: str = "RELATED_TO") -> None:
            query = f"""
            MATCH (a:Entity {{name: $from}}), (b:Entity {{name: $to}})
            MERGE (a)-[r:{rel_type}]->(b)
            ON CREATE SET r.created_at = timestamp()
            """
            self._run(query, {"from": from_name, "to": to_name})
else:
    @dataclass
    class GraphService:
        """No-op GraphService when `neo4j` is not installed.

        Keeps import-time behavior safe and allows tests/runs without Neo4j.
        """

        uri: str
        user: str
        password: str

        def __post_init__(self) -> None:  # pragma: no cover - environment dependent
            logger.info("Neo4j not installed; GraphService will no-op.")

        def _run(self, query: str, params: Dict[str, Any] | None = None) -> list[dict[str, Any]]:
            return []

        def close(self) -> None:
            return

        def upsert_document_node(
            self, *, doc_id: str, title: Optional[str], source_url: Optional[str]
        ) -> None:
            return

        def upsert_entity(self, *, name: str, type_: Optional[str] = None) -> None:
            return

        def link_doc_to_entity(self, *, doc_id: str, name: str, rel_type: str = "MENTIONS") -> None:
            return

        def link_entities(self, *, from_name: str, to_name: str, rel_type: str = "RELATED_TO") -> None:
            return
