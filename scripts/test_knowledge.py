"""Test script for Knowledge service - unit test without external dependencies."""

import sys
from unittest.mock import Mock


def main():
    print("Testing Knowledge Service (mocked)...")

    try:
        from alfred.services.knowledge import KnowledgeService

        print("✓ Successfully imported KnowledgeService")
    except ImportError as e:
        print(f"✗ Failed to import KnowledgeService: {e}")
        sys.exit(1)

    # Create mock embedder
    print("\nCreating mocked embedder...")
    mock_embedder = Mock()
    mock_embedder.embed_documents.return_value = [
        [0.1] * 1536,  # Mock embedding for doc1
        [0.2] * 1536,  # Mock embedding for doc2
        [0.3] * 1536,  # Mock embedding for doc3
    ]
    mock_embedder.embed_query.return_value = [0.15] * 1536

    # Create knowledge service with mocked embedder
    print("Initializing Knowledge service...")
    knowledge = KnowledgeService(embedder=mock_embedder)
    print(f"✓ Created service with collection: {knowledge.collection_name}")
    print(f"✓ Initial document count: {knowledge.count()}")

    # Index some test documents
    print("\nIndexing test documents...")
    test_docs = [
        {
            "id": "doc1",
            "text": "Python is a high-level programming language known for its simplicity and readability.",
            "meta": {"topic": "programming", "language": "python"},
        },
        {
            "id": "doc2",
            "text": "Machine learning is a subset of artificial intelligence that enables systems to learn from data.",
            "meta": {"topic": "ai", "category": "ml"},
        },
        {
            "id": "doc3",
            "text": "FastAPI is a modern web framework for building APIs with Python based on type hints.",
            "meta": {"topic": "programming", "framework": "fastapi"},
        },
    ]

    indexed_ids = knowledge.index_documents(test_docs)
    print(f"✓ Indexed {len(indexed_ids)} documents: {indexed_ids}")
    print(f"✓ Total documents in store: {knowledge.count()}")

    # Test search
    print("\nTesting search...")
    query = "What is Python?"
    print(f"Query: '{query}'")
    results = knowledge.search(query, limit=2)
    print(f"✓ Found {len(results)} results")
    for i, result in enumerate(results, 1):
        print(f"  {i}. [score: {result['score']:.3f}] {result['doc_id']}")
        print(f"     {result['text'][:60]}...")

    # Test deletion
    print("\nTesting deletion...")
    knowledge.delete_documents(["doc2"])
    print(f"✓ Deleted doc2, remaining count: {knowledge.count()}")

    print("\n✓ All tests passed!")


if __name__ == "__main__":
    main()
