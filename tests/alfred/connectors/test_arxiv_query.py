from datetime import date, datetime

import pytest
from alfred.connectors.arxiv_connector import (
    ArxivConnector,
    _compose_query,
    _normalize_date,
)


def test_normalize_date_inputs():
    assert _normalize_date(date(2024, 10, 1)) == "20241001"
    assert _normalize_date(datetime(2024, 10, 1, 12, 30)) == "20241001"
    assert _normalize_date("2024-10-05") == "20241005"
    assert _normalize_date("2024/10/06") == "20241006"
    assert _normalize_date("abc") == ""


def test_compose_query_parts():
    q = _compose_query(
        "transformers",
        categories=["cs.LG", "stat.ML"],
        date_from="2024-10-01",
        date_to="2024-10-05",
    )
    assert "(transformers)" in q
    assert "(cat:cs.LG OR cat:stat.ML)" in q
    assert "submittedDate:[20241001 TO 20241005]" in q


def test_validate_sort_values():
    # Valid passes
    ArxivConnector._validate_sort("relevance", "descending")

    # Invalid raises
    with pytest.raises(ValueError):
        ArxivConnector._validate_sort("bad", "descending")
    with pytest.raises(ValueError):
        ArxivConnector._validate_sort("relevance", "up")
