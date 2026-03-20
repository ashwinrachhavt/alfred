from __future__ import annotations

from alfred.pipeline.router import resolve_next_stage
from alfred.pipeline.state import DocumentPipelineState


def test_no_replay_starts_at_chunk():
    """Normal flow: after load_document, go to chunk."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "replay_from": None,
    }
    assert resolve_next_stage(state) == "chunk"


def test_replay_from_extract_with_prerequisites():
    """replay_from=extract works when chunks exist."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "chunks": [{"idx": 0, "text": "hello"}],
        "replay_from": "extract",
    }
    assert resolve_next_stage(state) == "extract"


def test_replay_from_invalid_falls_back():
    """replay_from=embed without chunks falls back to chunk."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "chunks": [],
        "replay_from": "embed",
    }
    assert resolve_next_stage(state) == "chunk"


def test_replay_from_classify():
    """replay_from=classify works when cleaned_text exists."""
    state: DocumentPipelineState = {
        "doc_id": "d1",
        "cleaned_text": "hello",
        "content_hash": "abc",
        "replay_from": "classify",
    }
    assert resolve_next_stage(state) == "classify"
