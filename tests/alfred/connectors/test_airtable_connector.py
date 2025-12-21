import pytest
from alfred.connectors.airtable_connector import AirtableConnector
from alfred.schemas.airtable_auth_credentials import AirtableAuthCredentialsBase


def test_get_records_by_date_range_builds_filter_formula(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = AirtableConnector(credentials=AirtableAuthCredentialsBase(access_token="t"))

    captured: dict[str, object] = {}

    def fake_get_all_records(*, filter_by_formula: str | None = None, **kwargs):
        captured["filter_by_formula"] = filter_by_formula
        captured["kwargs"] = kwargs
        return [{"id": "rec1"}], None

    monkeypatch.setattr(conn, "get_all_records", fake_get_all_records)

    records, error = conn.get_records_by_date_range(
        base_id="base",
        table_id="table",
        date_field="Due Date",
        start_date="2024-01-01",
        end_date="2024-02-01",
        max_records=10,
    )

    assert error is None
    assert records == [{"id": "rec1"}]
    assert captured["filter_by_formula"] == (
        'AND(NOT(IS_BEFORE({Due Date}, DATETIME_PARSE("2024-01-01", "YYYY-MM-DD"))), '
        'IS_BEFORE({Due Date}, DATETIME_PARSE("2024-02-01", "YYYY-MM-DD")))'
    )
    assert captured["kwargs"] == {"base_id": "base", "table_id": "table", "max_records": 10}


@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        ("2024-01-01T00:00:00", "2024-02-01"),
        ("2024-01-01", "2024-02-01T00:00:00"),
        ("20240101", "2024-02-01"),
    ],
)
def test_get_records_by_date_range_rejects_non_date_inputs(start_date: str, end_date: str) -> None:
    conn = AirtableConnector(credentials=AirtableAuthCredentialsBase(access_token="t"))

    records, error = conn.get_records_by_date_range(
        base_id="base",
        table_id="table",
        date_field="Due Date",
        start_date=start_date,
        end_date=end_date,
    )

    assert records == []
    assert error == "start_date and end_date must be in YYYY-MM-DD format"


def test_get_records_by_date_range_rejects_non_increasing_range() -> None:
    conn = AirtableConnector(credentials=AirtableAuthCredentialsBase(access_token="t"))

    records, error = conn.get_records_by_date_range(
        base_id="base",
        table_id="table",
        date_field="Due Date",
        start_date="2024-02-01",
        end_date="2024-02-01",
    )

    assert records == []
    assert error == "start_date (2024-02-01) must be before end_date (2024-02-01)"
