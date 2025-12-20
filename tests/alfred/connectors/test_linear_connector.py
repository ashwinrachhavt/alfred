import pytest
from alfred.connectors.linear_connector import LinearConnector


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def test_execute_graphql_query_raises_on_graphql_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(*_args, **_kwargs):
        return _FakeResponse(status_code=200, payload={"errors": [{"message": "nope"}]})

    monkeypatch.setattr("requests.post", fake_post)

    conn = LinearConnector(token="t")
    with pytest.raises(RuntimeError, match="GraphQL errors"):
        conn.execute_graphql_query("query { viewer { id } }")


def test_get_all_issues_paginates_and_respects_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        _FakeResponse(
            status_code=200,
            payload={
                "data": {
                    "issues": {
                        "nodes": [{"id": "1"}, {"id": "2"}],
                        "pageInfo": {"hasNextPage": True, "endCursor": "c1"},
                    }
                }
            },
        ),
        _FakeResponse(
            status_code=200,
            payload={
                "data": {
                    "issues": {
                        "nodes": [{"id": "3"}],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            },
        ),
    ]
    calls: list[dict] = []

    def fake_post(_url, *, headers, json, timeout):
        assert headers["Authorization"] == "t"
        assert timeout == 30
        calls.append(json)
        return responses.pop(0)

    monkeypatch.setattr("requests.post", fake_post)

    conn = LinearConnector(token="t")
    issues = conn.get_all_issues(include_comments=False, limit=3)
    assert [i["id"] for i in issues] == ["1", "2", "3"]

    # First page should not include variables; second should.
    assert "variables" not in calls[0]
    assert calls[1]["variables"] == {"after": "c1"}
