from __future__ import annotations

import pytest
from alfred.schemas.mind_palace import (
    DocumentIngest,
    DocumentIngestChunk,
    NoteCreate,
)


def test_note_create_validation():
    with pytest.raises(ValueError):
        NoteCreate(text="   ")
    ok = NoteCreate(text="hello", source_url=None, metadata={})
    assert ok.text == "hello"


def test_chunk_and_ingest_validators():
    with pytest.raises(ValueError):
        DocumentIngestChunk(idx=-1, text="x")
    with pytest.raises(ValueError):
        DocumentIngestChunk(idx=0, text="  ")

    # Valid chunk and ingest require cleaned_text and source_url
    chunk = DocumentIngestChunk(idx=0, text="content")
    ing = DocumentIngest(source_url="https://x", cleaned_text=" body ", chunks=[chunk])
    assert ing.cleaned_text == "body"
    assert ing.source_url == "https://x"
    assert ing.chunks[0].idx == 0

