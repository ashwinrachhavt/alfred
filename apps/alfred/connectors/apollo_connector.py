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
            # Apollo deprecated /mixed_people/search for API callers; /api_search is the supported path.
            "https://api.apollo.io/api/v1/mixed_people/api_search",
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
