from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

import requests
from sqlmodel import Session

from alfred.connectors import ApolloClient, HunterClient
from alfred.core.database import get_session
from alfred.core.settings import settings
from alfred.schemas.outreach import OutreachContact, OutreachRun

logger = logging.getLogger(__name__)


TARGET_TITLES = [
    "vp",
    "head",
    "director",
    "cto",
    "cpo",
    "engineering",
    "product",
    "ai",
]


@dataclass
class Contact:
    name: str
    title: str
    email: str
    confidence: float
    source: str

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "title": self.title,
            "email": self.email,
            "confidence": self.confidence,
            "source": self.source,
        }


def _guess_domain(company: str) -> Optional[str]:
    slug = company.lower().replace(" ", "").replace(",", "").replace(".", "")
    if slug and "." not in slug:
        return f"{slug}.com"
    return slug or None


def _join_name(first: str | None, last: str | None) -> str:
    parts = [part.strip() for part in (first or "", last or "") if part and part.strip()]
    return " ".join(parts)


def _confidence_from_status(status: str | None) -> float:
    if not status:
        return 0.5
    status = status.lower()
    if status in {"verified", "deliverable"}:
        return 0.95
    if status in {"valid", "trusted"}:
        return 0.85
    if status in {"accept_all", "risky"}:
        return 0.65
    if status in {"webmail", "disposable"}:
        return 0.45
    if status in {"unknown"}:
        return 0.5
    if status in {"invalid", "undeliverable", "block", "blocked"}:
        return 0.1
    return 0.5


def _confidence_from_score(raw_score: Any) -> float:
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score = score / 100.0
    return max(0.0, min(1.0, score))


def _merge_confidence(base: float, *, status: str | None = None, score: Any = None) -> float:
    candidates = [base]
    if score is not None:
        candidates.append(_confidence_from_score(score))
    if status:
        candidates.append(_confidence_from_status(status))
    return max(candidates)


class ContactDiscoveryService:
    """Aggregates contacts from Apollo, Hunter, and Snov with simple caching."""

    def __init__(
        self,
        *,
        cache_path: Path | None = None,
        cache_ttl_hours: int | None = None,
        session: Session | None = None,
    ) -> None:
        self.apollo_api_key = settings.apollo_api_key
        self.hunter_api_key = settings.hunter_api_key
        self.hunter_timeout_seconds = settings.hunter_timeout_seconds
        self.hunter_verify_top_n = settings.hunter_verify_top_n
        self.snov_client_id = settings.snov_client_id
        self.snov_client_secret = settings.snov_client_secret
        self.cache_path = cache_path or Path(settings.outreach_cache_path)
        self.cache_ttl = (cache_ttl_hours or settings.outreach_cache_ttl_hours) * 3600
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self.session = session

    # --------------- public ---------------
    def discover(self, company: str, *, limit: int = 20) -> list[dict[str, Any]]:
        key = company.strip().lower()
        cached = self._read_cache(key)
        if cached is not None:
            self._log_run(company, source="cache", contacts=cached)
            return cached

        domain = _guess_domain(company)
        contacts: list[Contact] = []

        contacts.extend(self._hunter_search(company, domain, limit=limit))
        contacts.extend(self._apollo_search(company, domain, limit=limit))
        contacts.extend(self._snov_search(company, domain, limit=limit))

        deduped = self._dedupe_and_rank(contacts, limit=limit)
        payload = [c.model_dump() for c in deduped]
        self._write_cache(key, payload)
        self._log_run(company, source="fresh", contacts=payload)
        return payload

    # --------------- providers ---------------
    def _hunter_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        api_key = self.hunter_api_key
        if not api_key:
            return []

        client = HunterClient(api_key=api_key, timeout_seconds=self.hunter_timeout_seconds)
        try:
            emails = client.domain_search(domain=domain, company=company, limit=limit)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Hunter lookup failed: %s", exc)
            return []

        contacts: list[Contact] = []
        for item in emails:
            email = (item.get("value") or "").strip()
            if not email:
                continue
            verification = item.get("verification") or {}
            contact = Contact(
                name=_join_name(item.get("first_name"), item.get("last_name")),
                title=str(item.get("position") or ""),
                email=email,
                confidence=_merge_confidence(
                    float(item.get("confidence") or 0) / 100.0,
                    status=verification.get("status"),
                    score=verification.get("score"),
                ),
                source="hunter",
            )
            contacts.append(contact)

        if self.hunter_verify_top_n > 0:
            budget = min(self.hunter_verify_top_n, len(contacts))
            for contact in contacts[:budget]:
                try:
                    verification = client.verify_email(contact.email)
                except Exception as exc:  # pragma: no cover - network path
                    logger.debug("Hunter verification failed: %s", exc)
                    continue
                if not verification:
                    continue
                contact.confidence = _merge_confidence(
                    contact.confidence,
                    status=verification.get("status"),
                    score=verification.get("score"),
                )

        return contacts

    def _apollo_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        """Query Apollo using endpoints available on free plans (mixed_people/search, organization_top_people)."""

        api_key = self.apollo_api_key
        if not api_key:
            return []

        payload = {
            "page": 1,
            "per_page": max(1, min(limit, 100)),
            "person_titles": TARGET_TITLES,
            "person_seniorities": ["c-suite", "vp", "head", "director"],
        }
        if domain:
            payload["q_organization_domains"] = [domain]
        else:
            payload["q_organization_names"] = [company]

        client = ApolloClient(api_key=api_key, timeout_seconds=20)

        try:
            status, data = client.mixed_people_search(payload)
            if status == 403:
                logger.info(
                    "Apollo mixed_people/search forbidden, trying organization_top_people via org lookup"
                )
                return self._apollo_top_people(company, domain, client, payload)
            if status >= 400:
                raise Exception(f"status {status}")
            return self._parse_apollo_people(data)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Apollo lookup failed: %s", exc)
            return []

    def _apollo_top_people(
        self,
        company: str,
        domain: str | None,
        client: ApolloClient,
        payload: dict[str, Any],
    ) -> list[Contact]:
        """Fallback that fetches org_id then calls organization_top_people."""

        org_id = self._apollo_org_id(company=company, domain=domain, client=client)
        if not org_id:
            return []

        top_people_payload = {
            "organization_id": org_id,
            "page": payload.get("page", 1),
            "per_page": payload.get("per_page", 20),
            "person_titles": payload.get("person_titles"),
            "person_seniorities": payload.get("person_seniorities"),
        }

        try:
            status, data = client.organization_top_people(top_people_payload)
            if status >= 400:
                raise Exception(f"status {status}")
            return self._parse_apollo_people(data)
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Apollo top_people lookup failed: %s", exc)
            return []

    def _apollo_org_id(self, company: str, domain: str | None, client: ApolloClient) -> str | None:
        """Find the Apollo organization_id using organizations/search."""

        payload: dict[str, Any] = {"page": 1, "per_page": 1}
        if domain:
            payload["q_organization_domains_list"] = [domain]
        else:
            payload["q_organization_name"] = company

        try:
            status, data = client.organizations_search(payload)
            if status >= 400:
                raise Exception(f"status {status}")
            orgs = (data or {}).get("organizations") or []
            if not orgs:
                return None
            # prefer exact domain match when present
            if domain:
                for org in orgs:
                    if str(org.get("domain") or "").lower() == domain.lower():
                        return str(
                            org.get("id") or org.get("_id") or org.get("organization_id") or ""
                        )
            org = orgs[0]
            return str(org.get("id") or org.get("_id") or org.get("organization_id") or "")
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Apollo organization lookup failed: %s", exc)
            return None

    @staticmethod
    def _parse_apollo_people(data: dict[str, Any]) -> list[Contact]:
        people = data.get("people") or data.get("contacts") or []
        out: list[Contact] = []
        for p in people:
            email = (p.get("email") or p.get("email_personal") or "").strip()
            out.append(
                Contact(
                    name=str(p.get("name") or p.get("full_name") or "").strip(),
                    title=str(p.get("title") or ""),
                    email=email,
                    confidence=_confidence_from_status(p.get("email_status")),
                    source="apollo",
                )
            )
        return out

    def _snov_token(self) -> str | None:
        if not (self.snov_client_id and self.snov_client_secret):
            return None
        try:
            resp = requests.post(
                "https://api.snov.io/v1/oauth/access_token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.snov_client_id,
                    "client_secret": self.snov_client_secret,
                },
                timeout=15,
            )
            resp.raise_for_status()
            return (resp.json() or {}).get("access_token")
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Snov token fetch failed: %s", exc)
            return None

    def _snov_search(self, company: str, domain: str | None, *, limit: int = 20) -> list[Contact]:
        token = self._snov_token()
        if not token:
            return []
        # Use lightweight domain emails endpoint; best-effort only.
        d = domain or _guess_domain(company)
        if not d:
            return []
        try:
            start = requests.post(
                "https://api.snov.io/v2/domain-search/domain-emails/start",
                headers={"Authorization": f"Bearer {token}"},
                json={"domain": d, "limit": limit},
                timeout=15,
            )
            start.raise_for_status()
            task = (start.json() or {}).get("links", {}).get("result")
            if not task:
                return []
            result = requests.get(task, headers={"Authorization": f"Bearer {token}"}, timeout=15)
            result.raise_for_status()
            emails = (result.json() or {}).get("data") or []
            out: list[Contact] = []
            for row in emails:
                email = (row.get("email") or "").strip()
                if not email:
                    continue
                out.append(
                    Contact(
                        name=str(row.get("name") or "").strip(),
                        title=str(row.get("position") or ""),
                        email=email,
                        confidence=0.6,
                        source="snov",
                    )
                )
            return out
        except Exception as exc:  # pragma: no cover - network path
            logger.warning("Snov lookup failed: %s", exc)
            return []

    # --------------- helpers ---------------
    def _dedupe_and_rank(self, contacts: Iterable[Contact], *, limit: int = 20) -> List[Contact]:
        seen: set[str] = set()
        cleaned: list[Contact] = []
        for c in contacts:
            email_key = c.email.lower().strip()
            if not email_key:
                # keep non-email records only if we have not exceeded list size
                pass
            if email_key and email_key in seen:
                continue
            if email_key:
                seen.add(email_key)
            cleaned.append(c)

        cleaned.sort(key=lambda x: x.confidence, reverse=True)
        return cleaned[:limit]

    # --------------- logging ---------------
    def _log_run(self, company: str, *, source: str, contacts: list[dict[str, Any]]) -> None:
        try:
            sess_ctx = self.session or next(get_session())
            with sess_ctx as db:
                run = OutreachRun(company=company, source=source, count=len(contacts))
                db.add(run)
                db.flush()
                rows = []
                for c in contacts:
                    rows.append(
                        OutreachContact(
                            run_id=run.id or 0,
                            company=company,
                            name=str(c.get("name", "")),
                            title=str(c.get("title", "")),
                            email=str(c.get("email", "")),
                            confidence=float(c.get("confidence", 0.0)),
                            source=str(c.get("source", "")),
                        )
                    )
                db.add_all(rows)
                db.commit()
        except Exception:
            logger.debug("Failed to log outreach run", exc_info=True)

    def _read_cache(self, key: str) -> Optional[list[dict[str, Any]]]:
        if not self.cache_path.is_file():
            return None
        try:
            data = json.loads(self.cache_path.read_text())
            entry = data.get(key)
            if not entry:
                return None
            if time.time() - entry.get("ts", 0) > self.cache_ttl:
                return None
            return entry.get("contacts")
        except Exception:
            return None

    def _write_cache(self, key: str, contacts: list[dict[str, Any]]) -> None:
        try:
            existing = {}
            if self.cache_path.is_file():
                existing = json.loads(self.cache_path.read_text())
            existing[key] = {"ts": time.time(), "contacts": contacts}
            self.cache_path.write_text(json.dumps(existing, indent=2))
        except Exception:
            logger.debug("Failed to write outreach cache", exc_info=True)


def discover_contacts(company: str, *, limit: int = 20) -> list[dict[str, Any]]:
    return ContactDiscoveryService().discover(company, limit=limit)
