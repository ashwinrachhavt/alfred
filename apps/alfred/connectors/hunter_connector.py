from __future__ import annotations

from typing import Any

import requests

HUNTER_BASE_URL = "https://api.hunter.io/v2"


class HunterClient:
    """Lightweight wrapper around Hunter endpoints used for contact discovery."""

    def __init__(self, api_key: str, *, timeout_seconds: int = 15) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def domain_search(
        self, *, domain: str | None, company: str | None, limit: int = 20
    ) -> list[dict[str, Any]]:
        if not (domain or company):
            raise ValueError("Hunter domain search requires a domain or company")

        params: dict[str, Any] = {"api_key": self.api_key, "limit": limit, "type": "personal"}
        if domain:
            params["domain"] = domain
        else:
            params["company"] = company

        resp = requests.get(
            f"{HUNTER_BASE_URL}/domain-search", params=params, timeout=self.timeout_seconds
        )
        resp.raise_for_status()
        return (resp.json() or {}).get("data", {}).get("emails") or []

    def verify_email(self, email: str) -> dict[str, Any] | None:
        if not email:
            return None

        params = {"api_key": self.api_key, "email": email}
        resp = requests.get(
            f"{HUNTER_BASE_URL}/email-verifier", params=params, timeout=self.timeout_seconds
        )
        if resp.status_code == 202:
            return None  # verification still running; skip
        resp.raise_for_status()
        return (resp.json() or {}).get("data") or {}
