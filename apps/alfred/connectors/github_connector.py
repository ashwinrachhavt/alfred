"""GitHub REST API connector for Alfred.

Fetches repository content (READMEs, issues) for knowledge ingestion.
"""

from __future__ import annotations

import logging
import re
from http import HTTPStatus
from typing import Any

import httpx

from alfred.core.settings import settings

_RATE_LIMIT_WARNING_THRESHOLD = 100

logger = logging.getLogger(__name__)

GITHUB_API_URL = "https://api.github.com"
_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


class GitHubClient:
    """Sync client for the GitHub REST API."""

    def __init__(
        self,
        token: str | None = None,
        *,
        timeout_seconds: int = 30,
    ) -> None:
        configured = settings.github_token.get_secret_value() if settings.github_token else None
        self._token = token or configured
        if not self._token:
            raise RuntimeError("GITHUB_TOKEN is not configured")
        self._timeout = timeout_seconds
        self._headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        resp = httpx.get(url, headers=self._headers, params=params, timeout=self._timeout)
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < _RATE_LIMIT_WARNING_THRESHOLD:
            logger.warning("GitHub rate limit low: %s remaining", remaining)
        resp.raise_for_status()
        return resp

    def _paginate(self, url: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Fetch all pages following GitHub's Link header pagination."""
        all_items: list[dict[str, Any]] = []
        next_url: str | None = url

        while next_url:
            resp = self._get(next_url, params=params)
            all_items.extend(resp.json())

            # Only pass params on first request; subsequent URLs are fully qualified
            params = None

            link = resp.headers.get("Link", "")
            match = _LINK_NEXT_RE.search(link)
            next_url = match.group(1) if match else None

        return all_items

    def list_user_repos(
        self,
        *,
        visibility: str = "all",
        sort: str = "updated",
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """List repositories for the authenticated user."""
        return self._paginate(
            f"{GITHUB_API_URL}/user/repos",
            params={"visibility": visibility, "sort": sort, "per_page": min(per_page, 100)},
        )

    def get_repo_metadata(self, owner: str, repo: str) -> dict[str, Any]:
        """Get repository metadata (description, stars, language, etc.)."""
        resp = self._get(f"{GITHUB_API_URL}/repos/{owner}/{repo}")
        return resp.json()

    def get_readme(self, owner: str, repo: str) -> str | None:
        """Fetch the README content as raw text.

        Returns None if the repo has no README.
        """
        try:
            resp = httpx.get(
                f"{GITHUB_API_URL}/repos/{owner}/{repo}/readme",
                headers={**self._headers, "Accept": "application/vnd.github.raw+json"},
                timeout=self._timeout,
            )
            if resp.status_code == HTTPStatus.NOT_FOUND:
                return None
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == HTTPStatus.NOT_FOUND:
                return None
            raise

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "all",
        since: str | None = None,
        labels: str | None = None,
        per_page: int = 100,
    ) -> list[dict[str, Any]]:
        """List issues for a repository.

        Args:
            state: 'open', 'closed', or 'all'.
            since: ISO 8601 datetime — only issues updated after this.
            labels: Comma-separated label names.
            per_page: Results per page (max 100).
        """
        params: dict[str, Any] = {
            "state": state,
            "per_page": min(per_page, 100),
            "sort": "updated",
            "direction": "desc",
        }
        if since:
            params["since"] = since
        if labels:
            params["labels"] = labels

        # Filter out pull requests (GitHub returns PRs in the issues endpoint)
        items = self._paginate(f"{GITHUB_API_URL}/repos/{owner}/{repo}/issues", params=params)
        return [item for item in items if "pull_request" not in item]
