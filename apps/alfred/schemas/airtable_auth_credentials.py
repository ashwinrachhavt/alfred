"""Schemas for Airtable authentication credentials."""

from __future__ import annotations

from pydantic import BaseModel


class AirtableAuthCredentialsBase(BaseModel):
    """Minimal OAuth credential shape for Airtable.

    Only the access token is required for current connector usage.
    Extend as needed (e.g., refresh_token, expires_in, token_type).
    """

    access_token: str


__all__ = ["AirtableAuthCredentialsBase"]
