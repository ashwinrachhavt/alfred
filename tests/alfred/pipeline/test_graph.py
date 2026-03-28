"""End-to-end pipeline graph test with mocked services."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from alfred.pipeline.graph import build_pipeline_graph


def _mock_all_services():
    """Return a dict of patch targets to mock objects."""
    doc_svc = MagicMock()
    doc_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test",
        "cleaned_text": "Hello world content",
        "raw_markdown": "# Hello",
        "hash": "testhash123",
    }
    doc_svc.update_document_enrichment.return_value = None

    chunk_svc = MagicMock()
    chunk_svc.chunk.return_value = [
        MagicMock(
            **{
                "model_dump.return_value": {
                    "idx": 0,
                    "text": "Hello world",
                    "tokens": 2,
                    "section": None,
                    "char_start": 0,
                    "char_end": 11,
                }
            }
        )
    ]

    extract_svc = MagicMock()
    extract_svc.extract_all.return_value = {
        "summary": {"short": "test"},
        "topics": {},
        "tags": ["test"],
        "entities": [],
        "embedding": [0.1, 0.2],
        "lang": "en",
    }
    extract_svc.extract_graph.return_value = {
        "entities": [{"name": "Hello", "type": "concept"}],
        "relations": [],
        "topics": [],
    }
    extract_svc.classify_taxonomy.return_value = {
        "domain": "Test",
        "subdomain": "Unit",
        "microtopics": [],
        "topic": {"title": "Test", "confidence": 1.0},
    }

    knowledge_svc = MagicMock()
    knowledge_svc.index_documents.return_value = ["d1:0"]

    cache = MagicMock()
    cache.get.return_value = None
    cache.set.return_value = None

    return {
        "alfred.pipeline.nodes.load_document._get_doc_storage": doc_svc,
        "alfred.pipeline.nodes.chunk._get_chunking_service": chunk_svc,
        "alfred.pipeline.nodes.extract._get_extraction_service": extract_svc,
        "alfred.pipeline.nodes.extract._get_cache": cache,
        "alfred.pipeline.nodes.classify._get_extraction_service": extract_svc,
        "alfred.pipeline.nodes.classify._get_cache": cache,
        "alfred.pipeline.nodes.embed._get_knowledge_service": knowledge_svc,
        "alfred.pipeline.nodes.persist._get_doc_storage": doc_svc,
    }


def test_full_pipeline_runs_all_stages():
    """End-to-end: graph runs load, chunk, extract, classify, embed, persist."""
    checkpointer = MemorySaver()
    graph = build_pipeline_graph(checkpointer=checkpointer)

    mocks = _mock_all_services()
    with contextlib.ExitStack() as stack:
        for target, mock_obj in mocks.items():
            stack.enter_context(patch(target, return_value=mock_obj))

        result = graph.invoke(
            {
                "doc_id": "d1",
                "user_id": "u1",
                "errors": [],
                "cache_hits": [],
                "force_replay": False,
                "replay_from": None,
            },
            config={"configurable": {"thread_id": "d1"}},
        )

    assert result["stage"] == "persist"
    assert result["title"] == "Test"
    assert result["embedding_indexed"] is True
    assert len(result["chunks"]) == 1
    assert "enrichment" in result
    assert "classification" in result


def test_pipeline_checkpoint_saves():
    """Pipeline checkpoints after each node."""
    checkpointer = MemorySaver()
    graph = build_pipeline_graph(checkpointer=checkpointer)

    doc_svc = MagicMock()
    doc_svc.get_document_details.return_value = {
        "id": "d1",
        "title": "Test",
        "cleaned_text": "Hello",
        "raw_markdown": "# Hello",
        "hash": "testhash",
    }

    with patch(
        "alfred.pipeline.nodes.load_document._get_doc_storage",
        return_value=doc_svc,
    ):
        try:
            graph.invoke(
                {
                    "doc_id": "d1",
                    "user_id": "u1",
                    "errors": [],
                    "cache_hits": [],
                    "force_replay": False,
                    "replay_from": None,
                },
                config={"configurable": {"thread_id": "d1"}},
            )
        except Exception:
            pass  # Expected: chunk fails without real service

    checkpoint = checkpointer.get_tuple(
        {"configurable": {"thread_id": "d1", "checkpoint_ns": ""}}
    )
    assert checkpoint is not None
