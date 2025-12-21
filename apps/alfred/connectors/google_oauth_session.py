"""
Shared Google OAuth credential handling for Google API connectors.

This module centralizes:
- Validation of required OAuth fields
- Refreshing expired credentials
- Invoking an optional "credentials refreshed" callback (sync or async)

Connectors keep service-specific logic (e.g., Gmail vs Calendar) while relying on this
session object to manage the OAuth lifecycle.
"""

from __future__ import annotations

import inspect
from typing import Awaitable, Callable

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

CredentialsRefreshedCallback = Callable[[Credentials], Awaitable[None] | None]


class GoogleOAuthSession:
    """Manages Google OAuth credentials refresh behavior for connectors."""

    def __init__(
        self,
        credentials: Credentials,
        *,
        on_credentials_refreshed: CredentialsRefreshedCallback | None = None,
    ) -> None:
        self._credentials = credentials
        self._on_refresh = on_credentials_refreshed

    async def get_credentials(self) -> Credentials:
        """Return valid credentials, refreshing if needed."""
        if not all(
            [
                self._credentials.client_id,
                self._credentials.client_secret,
                self._credentials.refresh_token,
            ]
        ):
            raise ValueError(
                "Google OAuth credentials (client_id, client_secret, refresh_token) must be set"
            )

        if not self._credentials.expired:
            return self._credentials

        # Rebuild credentials from refresh token to ensure refresh fields are present.
        self._credentials = Credentials(
            token=self._credentials.token,
            refresh_token=self._credentials.refresh_token,
            token_uri=self._credentials.token_uri,
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            scopes=self._credentials.scopes,
            expiry=self._credentials.expiry,
        )

        if self._credentials.expired or not getattr(self._credentials, "valid", False):
            self._credentials.refresh(Request())
            if self._on_refresh is not None:
                result = self._on_refresh(self._credentials)
                if inspect.isawaitable(result):
                    await result  # type: ignore[func-returns-value]

        return self._credentials
