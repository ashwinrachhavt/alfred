from __future__ import annotations

from typing import Any, Tuple

import requests


class ApolloClient:
    """Minimal Apollo API wrapper for contact discovery."""

    def __init__(self, api_key: str, *, timeout_seconds: int = 20) -> None:
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.headers = {"Content-Type": "application/json", "X-Api-Key": api_key}

    def mixed_people_search(self, payload: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        resp = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/search",
            headers=self.headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def organizations_search(self, payload: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        resp = requests.post(
            "https://api.apollo.io/api/v1/organizations/search",
            headers=self.headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        return resp.status_code, self._safe_json(resp)

    def organization_top_people(self, payload: dict[str, Any]) -> Tuple[int, dict[str, Any]]:
        # Primary path
        resp = requests.post(
            "https://api.apollo.io/api/v1/mixed_people/organization_top_people",
            headers=self.headers,
            json=payload,
            timeout=self.timeout_seconds,
        )
        if resp.status_code == 404:
            # Fallback path without /api prefix used in some tenants
            resp = requests.post(
                "https://api.apollo.io/v1/mixed_people/organization_top_people",
                headers=self.headers,
                json=payload,
                timeout=self.timeout_seconds,
            )
        return resp.status_code, self._safe_json(resp)

    @staticmethod
    def _safe_json(resp: requests.Response) -> dict[str, Any]:
        try:
            return resp.json() or {}
        except Exception:
            return {}
