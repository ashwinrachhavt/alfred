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

        def link_entities(
            self, *, from_name: str, to_name: str, rel_type: str = "RELATED_TO"
        ) -> None:
            query = f"""
            MATCH (a:Entity {{name: $from}}), (b:Entity {{name: $to}})
            MERGE (a)-[r:{rel_type}]->(b)
            ON CREATE SET r.created_at = timestamp()
            """
            self._run(query, {"from": from_name, "to": to_name})

        def upsert_topic_node(self, *, topic_id: str, name: Optional[str] = None) -> None:
            query = """
            MERGE (t:Topic {topic_id: $topic_id})
            SET t.name = coalesce($name, t.name),
                t.updated_at = timestamp()
            """
            self._run(query, {"topic_id": topic_id, "name": name})

        def link_topic_to_document(
            self, *, topic_id: str, doc_id: str, rel_type: str = "HAS_RESOURCE"
        ) -> None:
            query = f"""
            MATCH (t:Topic {{topic_id: $topic_id}})
            MATCH (d:Document {{doc_id: $doc_id}})
            MERGE (t)-[r:{rel_type}]->(d)
            ON CREATE SET r.created_at = timestamp()
            """
            self._run(query, {"topic_id": topic_id, "doc_id": doc_id})

        def link_topic_to_entity(
            self, *, topic_id: str, name: str, rel_type: str = "COVERS"
        ) -> None:
            query = f"""
            MATCH (t:Topic {{topic_id: $topic_id}})
            MATCH (e:Entity {{name: $name}})
            MERGE (t)-[r:{rel_type}]->(e)
            ON CREATE SET r.created_at = timestamp()
            """
            self._run(query, {"topic_id": topic_id, "name": name})

        def fetch_topic_subgraph(self, *, topic_id: str, limit: int = 200) -> dict[str, Any]:
            query = """
            MATCH (t:Topic {topic_id: $topic_id})
            OPTIONAL MATCH (t)-[:HAS_RESOURCE]->(d:Document)
            OPTIONAL MATCH (d)-[:MENTIONS]->(e:Entity)
            RETURN d.doc_id AS doc_id, d.title AS doc_title, d.source_url AS source_url, e.name AS entity_name
            LIMIT $limit
            """
            rows = self._run(query, {"topic_id": topic_id, "limit": int(limit)})
            nodes: list[dict[str, Any]] = [
                {"id": f"topic:{topic_id}", "label": f"Topic {topic_id}", "type": "topic"}
            ]
            edges: list[dict[str, Any]] = []
            node_ids = {nodes[0]["id"]}
            for r in rows:
                doc_id = r.get("doc_id")
                if doc_id:
                    did = f"doc:{doc_id}"
                    if did not in node_ids:
                        nodes.append(
                            {
                                "id": did,
                                "label": r.get("doc_title") or doc_id,
                                "type": "document",
                                "meta": {"source_url": r.get("source_url")},
                            }
                        )
                        node_ids.add(did)
                    edges.append(
                        {"source": f"topic:{topic_id}", "target": did, "type": "HAS_RESOURCE"}
                    )
                entity_name = r.get("entity_name")
                if entity_name:
                    eid = f"entity:{entity_name}"
                    if eid not in node_ids:
                        nodes.append({"id": eid, "label": entity_name, "type": "entity"})
                        node_ids.add(eid)
                    if doc_id:
                        edges.append({"source": f"doc:{doc_id}", "target": eid, "type": "MENTIONS"})
            return {"nodes": nodes, "edges": edges}
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

        def link_entities(
            self, *, from_name: str, to_name: str, rel_type: str = "RELATED_TO"
        ) -> None:
            return

        def upsert_topic_node(self, *, topic_id: str, name: Optional[str] = None) -> None:
            return

        def link_topic_to_document(
            self, *, topic_id: str, doc_id: str, rel_type: str = "HAS_RESOURCE"
        ) -> None:
            return

        def link_topic_to_entity(
            self, *, topic_id: str, name: str, rel_type: str = "COVERS"
        ) -> None:
            return

        def fetch_topic_subgraph(self, *, topic_id: str, limit: int = 200) -> dict[str, Any]:
            return {"nodes": [], "edges": []}
