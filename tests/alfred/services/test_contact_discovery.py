import sys
from pathlib import Path

import pytest

# ensure "apps" package is importable when running tests directly
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps"))

from alfred.core.settings import settings  # noqa: E402
from alfred.services.company_outreach_service import ContactDiscoveryService  # noqa: E402


class _FakeResponse:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if 400 <= self.status_code:
            raise Exception(f"status {self.status_code}")


@pytest.fixture
def service(monkeypatch) -> ContactDiscoveryService:
    monkeypatch.setattr(settings, "apollo_api_key", "test-key")
    monkeypatch.setattr(settings, "hunter_api_key", "hunter-key")
    monkeypatch.setattr(settings, "hunter_timeout_seconds", 5)
    monkeypatch.setattr(settings, "hunter_verify_top_n", 0)
    return ContactDiscoveryService(cache_path=None, cache_ttl_hours=1, session=None)


def test_hunter_search_parses_confidence_and_name(monkeypatch, service):
    called: dict[str, list] = {"urls": []}

    def fake_get(url, params=None, timeout=None):
        called["urls"].append(url)
        assert params["api_key"] == "hunter-key"
        if url.endswith("email-count"):
            return _FakeResponse(200, {"data": {"total": 1}})
        return _FakeResponse(
            200,
            {
                "data": {
                    "emails": [
                        {
                            "value": "alex@acme.com",
                            "first_name": "Alex",
                            "last_name": "Doe",
                            "position": "CTO",
                            "confidence": 92,
                            "verification": {"status": "valid", "score": 99},
                        }
                    ]
                }
            },
        )

    monkeypatch.setattr("requests.get", fake_get)

    people = service._hunter_search(company="Acme", domain="acme.com", limit=1)

    assert called["urls"] == [
        "https://api.hunter.io/v2/email-count",
        "https://api.hunter.io/v2/domain-search",
    ]
    assert len(people) == 1
    contact = people[0]
    assert contact.name == "Alex Doe"
    assert contact.title == "CTO"
    assert contact.email == "alex@acme.com"
    assert contact.confidence > 0.9
    assert contact.source == "hunter"


def test_hunter_search_runs_verifier_for_top_n(monkeypatch):
    svc = ContactDiscoveryService(cache_path=None, cache_ttl_hours=1, session=None)
    svc.hunter_verify_top_n = 1
    monkeypatch.setattr(svc, "hunter_api_key", "hunter-key")
    monkeypatch.setattr(svc, "hunter_timeout_seconds", 5)

    calls: list[str] = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        if url.endswith("email-count"):
            return _FakeResponse(200, {"data": {"total": 1}})
        if url.endswith("domain-search"):
            return _FakeResponse(
                200,
                {
                    "data": {
                        "emails": [
                            {
                                "value": "jane@beta.com",
                                "confidence": 70,
                                "verification": {"status": "risky"},
                            }
                        ]
                    }
                },
            )
        if url.endswith("email-verifier"):
            return _FakeResponse(200, {"data": {"status": "valid", "score": 96}})
        raise AssertionError("unexpected url")

    monkeypatch.setattr("requests.get", fake_get)

    people = svc._hunter_search(company="Beta", domain="beta.com", limit=1)

    assert calls == [
        "https://api.hunter.io/v2/email-count",
        "https://api.hunter.io/v2/domain-search",
        "https://api.hunter.io/v2/email-verifier",
    ]
    assert len(people) == 1
    assert people[0].confidence > 0.9  # boosted after verifier


def test_apollo_search_uses_api_search(monkeypatch: pytest.MonkeyPatch, service):
    calls: list[str] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append(url)
        return _FakeResponse(
            200,
            {
                "people": [
                    {
                        "name": "Ada Lovelace",
                        "title": "CTO",
                        "email": "ada@titan.ai",
                        "email_status": "verified",
                    }
                ]
            },
        )

    monkeypatch.setattr("requests.post", fake_post)

    people = service._apollo_search(company="Titan AI", domain="titan.ai", limit=2)

    assert calls == ["https://api.apollo.io/api/v1/mixed_people/api_search"]
    assert len(people) == 1
    assert people[0].source == "apollo"
    assert people[0].confidence > 0.9


def test_apollo_search_returns_empty_on_forbidden(monkeypatch: pytest.MonkeyPatch, service):
    calls: list[str] = []

    def fake_post(url, *, headers, json, timeout):
        calls.append(url)
        return _FakeResponse(403, {})

    monkeypatch.setattr("requests.post", fake_post)

    people = service._apollo_search(company="Shepherd", domain=None, limit=1)

    assert calls == ["https://api.apollo.io/api/v1/mixed_people/api_search"]
    assert people == []
