from __future__ import annotations


def test_graph_service_instantiation_without_neo4j():
    # GraphService should be importable and instantiable without neo4j installed
    from alfred.services.graph_service import GraphService

    svc = GraphService(uri="bolt://localhost:7687", user="neo4j", password="pass")
    # Close should no-op safely
    svc.close()
