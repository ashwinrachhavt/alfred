from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from alfred.pipeline.state import DocumentPipelineState

# -- load_document --


def test_load_document_populates_state():
    from alfred.pipeline.nodes.load_document import load_document

    mock_svc = MagicMock()
    mock_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test Doc",
        "cleaned_text": "Hello world",
        "raw_markdown": "# Hello world",
    }

    state: DocumentPipelineState = {"doc_id": "d1", "errors": []}

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=mock_svc,
    ):
        result = load_document(state)

    assert result["title"] == "Test Doc"
    assert result["cleaned_text"] == "Hello world"
    import hashlib
    expected_hash = hashlib.sha256(b"Hello world").hexdigest()
    assert result["content_hash"] == expected_hash
    assert result["stage"] == "load_document"


@patch("alfred.pipeline.nodes.load_document.time")
def test_load_document_not_found_retries_then_raises(mock_time):
    from alfred.pipeline.nodes.load_document import load_document

    mock_svc = MagicMock()
    mock_svc.get_document_details.return_value = None

    state: DocumentPipelineState = {"doc_id": "missing", "errors": []}

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=mock_svc,
    ):
        with pytest.raises(ValueError, match="not found after retry"):
            load_document(state)

    mock_time.sleep.assert_called_once_with(2)
    assert mock_svc.get_document_details.call_count == 2


# -- chunk --


def test_chunk_node():
    from alfred.pipeline.nodes.chunk import chunk

    mock_svc = MagicMock()
    mock_svc.chunk.return_value = [
        MagicMock(
            **{"model_dump.return_value": {"idx": 0, "text": "Hello", "tokens": 1}}
        )
    ]

    state: DocumentPipelineState = {"cleaned_text": "Hello world", "errors": []}

    with patch(
        "alfred.pipeline.nodes.chunk._get_chunking_service",
        return_value=mock_svc,
    ):
        result = chunk(state)

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["idx"] == 0
    assert result["stage"] == "chunk"


# -- extract --


def test_extract_node_merges_graph():
    from alfred.pipeline.nodes.extract import extract

    mock_svc = MagicMock()
    mock_svc.extract_all.return_value = {
        "summary": {"short": "test"},
        "topics": {},
        "tags": ["ai"],
        "entities": [],
        "embedding": [0.1],
        "lang": "en",
    }
    mock_svc.extract_graph.return_value = {
        "entities": [{"name": "AI", "type": "concept"}],
        "relations": [{"from": "AI", "to": "ML", "type": "related"}],
        "topics": ["machine learning"],
    }

    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    state: DocumentPipelineState = {
        "cleaned_text": "AI and ML",
        "content_hash": "abc",
        "force_replay": False,
        "cache_hits": [],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.extract._get_extraction_service",
        return_value=mock_svc,
    ), patch(
        "alfred.pipeline.nodes.extract._get_cache",
        return_value=mock_cache,
    ):
        result = extract(state)

    assert "relations" in result["enrichment"]
    assert result["enrichment"]["relations"][0]["from"] == "AI"
    assert result["stage"] == "extract"


# -- classify --


def test_classify_node():
    from alfred.pipeline.nodes.classify import classify

    mock_svc = MagicMock()
    mock_svc.classify_taxonomy.return_value = {
        "domain": "Technology",
        "subdomain": "AI",
        "microtopics": ["NLP"],
        "topic": {"title": "NLP", "confidence": 0.9},
    }

    mock_cache = MagicMock()
    mock_cache.get.return_value = None

    state: DocumentPipelineState = {
        "cleaned_text": "NLP text",
        "content_hash": "abc",
        "force_replay": False,
        "cache_hits": [],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.classify._get_extraction_service",
        return_value=mock_svc,
    ), patch(
        "alfred.pipeline.nodes.classify._get_cache",
        return_value=mock_cache,
    ):
        result = classify(state)

    assert result["classification"]["domain"] == "Technology"
    assert result["stage"] == "classify"


# -- embed --


def test_embed_node():
    from alfred.pipeline.nodes.embed import embed

    mock_svc = MagicMock()
    mock_svc.index_documents.return_value = ["d1:0", "d1:1"]

    state: DocumentPipelineState = {
        "doc_id": "d1",
        "chunks": [
            {"idx": 0, "text": "chunk 0", "section": None, "char_start": 0, "char_end": 7},
            {"idx": 1, "text": "chunk 1", "section": None, "char_start": 8, "char_end": 15},
        ],
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.embed._get_knowledge_service",
        return_value=mock_svc,
    ):
        result = embed(state)

    assert result["embedding_indexed"] is True
    assert result["stage"] == "embed"
    call_args = mock_svc.index_documents.call_args[0][0]
    assert call_args[0]["id"] == "d1:0"
    assert call_args[0]["text"] == "chunk 0"


# -- persist --


def test_persist_node():
    from alfred.pipeline.nodes.persist import persist

    mock_svc = MagicMock()

    state: DocumentPipelineState = {
        "doc_id": "d1",
        "chunks": [{"idx": 0, "text": "test"}],
        "enrichment": {"summary": {"short": "test"}, "topics": {}, "tags": []},
        "classification": {"domain": "Tech"},
        "errors": [],
    }

    with patch(
        "alfred.pipeline.nodes.persist._get_doc_storage",
        return_value=mock_svc,
    ):
        result = persist(state)

    assert result["stage"] == "persist"
    mock_svc.update_document_enrichment.assert_called_once()
