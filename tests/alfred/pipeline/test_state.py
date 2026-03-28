from __future__ import annotations

from alfred.pipeline.state import STAGE_ORDER, DocumentPipelineState


def test_state_has_required_keys():
    """State TypedDict has all expected keys."""
    keys = DocumentPipelineState.__annotations__
    assert "doc_id" in keys
    assert "cleaned_text" in keys
    assert "chunks" in keys
    assert "enrichment" in keys
    assert "errors" in keys
    assert "stage" in keys


def test_stage_order_is_complete():
    """STAGE_ORDER lists all backbone stages."""
    assert STAGE_ORDER == [
        "load_document",
        "chunk",
        "extract",
        "classify",
        "embed",
        "persist",
    ]


def test_stage_prerequisites():
    """Each stage's prerequisite output fields are defined."""
    from alfred.pipeline.state import STAGE_PREREQUISITES

    assert "chunks" not in STAGE_PREREQUISITES["chunk"]
    assert "cleaned_text" in STAGE_PREREQUISITES["extract"]
    assert "chunks" in STAGE_PREREQUISITES["embed"]
