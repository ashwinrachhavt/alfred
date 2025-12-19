"""Shared API dependencies."""

from collections.abc import Generator
from ipaddress import ip_address
from typing import Optional

from fastapi import Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from alfred.core.config import settings
from alfred.core.database import get_session


def get_db_session() -> Generator[Session, None, None]:
    """Provide a database session for request handlers."""
    yield from get_session()


def _extract_client_ip(request: Request) -> Optional[str]:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def require_internal_agent(
    request: Request,
    x_internal_token: Optional[str] = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected = settings.internal_agent_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal agent token not configured",
        )
    if x_internal_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")

    client_ip = _extract_client_ip(request)
    if not client_ip:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing client IP")
    try:
        ip_obj = ip_address(client_ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid client IP") from exc
    if not (ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden network")


__all__ = ["get_db_session", "require_internal_agent"]
