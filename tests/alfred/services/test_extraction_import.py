from __future__ import annotations


def test_extraction_service_import_and_empty_graph():
    # Import should succeed even if optional deps like langextract are missing
    from alfred.services.extraction_service import ExtractionService

    svc = ExtractionService()
    # Empty text should short-circuit without any network calls
    out = svc.extract_graph(text="")
    assert isinstance(out, dict)
    assert out.get("entities") == []
    assert out.get("relations") == []
    assert out.get("topics") == []
