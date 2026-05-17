from __future__ import annotations

from pathlib import Path

from alfred.schemas.imports import ImportStats


def test_import_stats_add_error_records_consistent_context() -> None:
    stats = ImportStats()

    stats.add_error(
        source="rss",
        operation="map",
        error=ValueError("missing link"),
        item_id="entry-1",
        feed_url="https://example.com/feed.xml",
    )

    assert stats.errors == [
        {
            "source": "rss",
            "operation": "map",
            "id": "entry-1",
            "error": "missing link",
            "error_type": "ValueError",
            "feed_url": "https://example.com/feed.xml",
        }
    ]


def test_import_stats_add_error_accepts_string_errors() -> None:
    stats = ImportStats()

    stats.add_error(
        source="google_drive",
        operation="export_doc",
        error="export failed",
        item_id="file-1",
    )

    assert stats.errors == [
        {
            "source": "google_drive",
            "operation": "export_doc",
            "id": "file-1",
            "error": "export failed",
            "error_type": "Error",
        }
    ]


def test_import_services_use_normalized_error_helper() -> None:
    repo_root = Path(__file__).parents[3]
    import_services = (repo_root / "apps" / "alfred" / "services").glob("*_import.py")

    bypasses = [
        str(path.relative_to(repo_root))
        for path in import_services
        if "stats.errors.append" in path.read_text()
    ]

    assert bypasses == []
