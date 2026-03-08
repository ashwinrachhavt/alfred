from __future__ import annotations

from alfred.schemas.intelligence import MemoryCreateRequest
from alfred.services.doc_storage_pg import DocStorageService
from alfred.services.memory_service import MemoryService
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_memory_service_create_and_list() -> None:
    session = _session()
    doc_storage = DocStorageService(session=session)
    svc = MemoryService(doc_storage=doc_storage)

    created = svc.create_memory(
        MemoryCreateRequest(
            text="Prefer concise, practical answers for engineering discussions.",
            user_id=123,
            source="manual",
            tags=["writing", "style"],
        )
    )
    assert created.id
    assert created.metadata.get("kind") == "memory"
    assert created.metadata.get("user_id") == 123

    listed = svc.list_memories(q="concise", user_id=123, skip=0, limit=20)
    assert listed.total == 1
    assert listed.items[0].id == created.id


def test_memory_service_context_scoring() -> None:
    session = _session()
    doc_storage = DocStorageService(session=session)
    svc = MemoryService(doc_storage=doc_storage)

    svc.create_memory(
        MemoryCreateRequest(text="Use TypeScript for frontend features.", source="task")
    )
    svc.create_memory(
        MemoryCreateRequest(text="Prefer minimal UI with strong defaults.", source="manual")
    )

    ctx = svc.get_context_memories(query="frontend TypeScript autocomplete", limit=5)
    assert ctx
    assert any("typescript" in item.text.lower() for item in ctx)
    assert all("score" in (item.metadata or {}) for item in ctx)
