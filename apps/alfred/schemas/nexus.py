"""Pydantic DTOs for the /api/nexus graph endpoints."""

from __future__ import annotations

from pydantic import BaseModel


class NexusNode(BaseModel):
    card_id: int
    title: str
    topic: str | None = None
    tags: list[str] = []
    bloom_level: int = 1
    cluster_id: int | None = None


class NexusEdge(BaseModel):
    source: int
    target: int
    type: str


class NexusGraph(BaseModel):
    nodes: list[NexusNode]
    edges: list[NexusEdge]


class NexusPath(BaseModel):
    card_ids: list[int]


class NexusBridge(BaseModel):
    card_id: int
    title: str
    score: int


class NexusSyncResult(BaseModel):
    nodes_synced: int
    edges_synced: int
