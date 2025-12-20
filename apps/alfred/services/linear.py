from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from alfred.connectors.linear_connector import LinearConnector
from alfred.core.exceptions import ConfigurationError, ServiceUnavailableError
from alfred.core.settings import settings

logger = logging.getLogger(__name__)


class LinearService:
    """Service wrapper around Linear's GraphQL API.

    Reads `LINEAR_API_KEY` from settings by default.
    """

    def __init__(self, token: str | None = None) -> None:
        configured = settings.linear_api_key.get_secret_value() if settings.linear_api_key else None
        self._token = token or configured
        if not self._token:
            raise ConfigurationError("LINEAR_API_KEY is not configured")

        self._connector = LinearConnector(token=self._token)

    def viewer(self) -> dict[str, Any]:
        """Return the current Linear user (viewer) object."""
        query = """
        query {
            viewer {
                id
                name
                email
            }
        }
        """
        try:
            result = self._connector.execute_graphql_query(query)
            viewer = (result.get("data") or {}).get("viewer")
            return viewer or {}
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning("Linear viewer query failed: %s", exc)
            raise ServiceUnavailableError("Linear API request failed") from exc

    def list_issues(
        self, *, include_comments: bool = False, limit: int = 100
    ) -> list[dict[str, Any]]:
        try:
            return self._connector.get_all_issues(
                include_comments=include_comments,
                limit=limit,
            )
        except Exception as exc:  # pragma: no cover - external dependency
            logger.warning("Linear list issues failed: %s", exc)
            raise ServiceUnavailableError("Linear API request failed") from exc

    def list_issues_by_date_range(
        self,
        *,
        start_date: str,
        end_date: str,
        include_comments: bool = False,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        issues, error = self._connector.get_issues_by_date_range(
            start_date=start_date,
            end_date=end_date,
            include_comments=include_comments,
            limit=limit,
        )
        if error:
            raise ServiceUnavailableError(error)
        return issues

    def format_issue(self, issue: dict[str, Any]) -> dict[str, Any]:
        return self._connector.format_issue(issue)

    def issue_to_markdown(self, issue: dict[str, Any]) -> str:
        return self._connector.format_issue_to_markdown(issue)


@lru_cache
def get_linear_service() -> LinearService:
    """Lazily build a singleton LinearService."""

    return LinearService()
