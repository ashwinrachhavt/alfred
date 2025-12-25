from __future__ import annotations

import uuid

from alfred.schemas.outreach import OutreachContact, OutreachMessage
from alfred.services.company_outreach_service import OutreachService
from sqlmodel import Session, SQLModel, create_engine


def _session() -> Session:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def test_list_contacts_uses_cache(monkeypatch) -> None:
    session = _session()
    contact = OutreachContact(
        run_id=1,
        company="Stripe",
        name="Jane Doe",
        title="VP Product",
        email="jane@stripe.com",
        confidence=0.9,
        source="hunter",
    )
    with session:
        session.add(contact)
        session.commit()
    svc = OutreachService(session=session)

    # Should return cached row without hitting providers
    monkeypatch.setattr(
        "alfred.services.company_outreach_service.ContactDiscoveryService.discover",
        lambda *args, **kwargs: [],
    )
    results = svc.list_contacts("Stripe", limit=5, role_filter=None, refresh=False)
    assert results[0]["email"] == "jane@stripe.com"


def test_list_contacts_refresh_calls_discovery(monkeypatch) -> None:
    session = _session()
    svc = OutreachService(session=session)

    called = {}

    def _fake(self, company: str, limit: int = 20, **_kwargs):
        called["hit"] = True
        return [
            {"email": "a@example.com", "title": "Head of Eng", "confidence": 0.8, "source": "x"}
        ]

    monkeypatch.setattr(
        "alfred.services.company_outreach_service.ContactDiscoveryService.discover", _fake
    )
    results = svc.list_contacts("Acme", refresh=True)
    assert called.get("hit") is True
    assert results[0]["email"] == "a@example.com"


def test_send_email_dry_run() -> None:
    session = _session()
    svc = OutreachService(session=session)
    msg = svc.send_email(
        company="Stripe",
        contact_email="jane@stripe.com",
        subject="Hello",
        body="Hi Jane",
        dry_run=True,
    )
    assert isinstance(msg.id, uuid.UUID)
    assert msg.status == "skipped"
    with session:
        persisted = session.get(OutreachMessage, msg.id)
        assert persisted is not None
        assert persisted.status == "skipped"
