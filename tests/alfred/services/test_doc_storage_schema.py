from __future__ import annotations

import os

import pytest
from alfred.schemas.documents import (
    DocChunkRecord,
    DocumentIngest,
    DocumentIngestChunk,
    DocumentRecord,
    NoteCreate,
    NoteRecord,
)
from alfred.services.doc_storage import DocStorageService
from bson import ObjectId
from pymongo import MongoClient


def _connect_client() -> MongoClient | None:
    uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    try:
        client = MongoClient(uri, uuidRepresentation="standard")
        # simple ping; skip test if not reachable
        client.admin.command("ping")
        return client
    except Exception:
        return None


@pytest.mark.integration
def test_ingest_and_validate_shapes():
    client = _connect_client()
    if client is None:
        pytest.skip("MongoDB not available for integration test")

    dbname = "notes_db_test_schema"
    db = client[dbname]
    try:
        svc = DocStorageService(database=db)
        svc.ensure_indexes()

        ingest = DocumentIngest(
            source_url="https://example.com/page",
            title="Example Page",
            cleaned_text="Hello world. This is a test document.",
            content_type="web",
            chunks=[
                DocumentIngestChunk(idx=0, text="Chunk 0"),
            ],
        )
        res = svc.ingest_document(ingest)
        oid = ObjectId(res["id"]) if ObjectId.is_valid(res["id"]) else None
        assert oid is not None

        d = db.get_collection("documents").find_one({"_id": oid})
        assert d is not None
        # Validate with canonical model (allows extra like _id)
        DocumentRecord.model_validate(d)

        c = db.get_collection("doc_chunks").find_one({"doc_id": oid})
        assert c is not None
        DocChunkRecord.model_validate(c)

        note_id = svc.create_note(NoteCreate(text="Hello note"))
        note_oid = ObjectId(note_id)
        note_doc = db.get_collection("notes").find_one({"_id": note_oid})
        assert note_doc is not None
        NoteRecord.model_validate(note_doc)
    finally:
        client.drop_database(dbname)
