"""Shared handler for knowledge import endpoints.

Eliminates the duplicated try/except/ImportResponse pattern across 12+ import routes.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from alfred.schemas.imports import ImportResponse

logger = logging.getLogger(__name__)


def handle_import_request(
    import_fn: Callable[..., dict[str, Any] | Awaitable[dict[str, Any]]],
    source_name: str,
    **kwargs: Any,
) -> ImportResponse:
    """Call an import function and wrap the result in a standard ImportResponse.

    Usage in a route::

        @router.post("/import", response_model=ImportResponse)
        def start_import(payload: ImportRequest, svc=Depends(get_doc_storage_service)):
            return handle_import_request(
                import_readwise, "readwise",
                doc_store=svc, token=payload.token, since=payload.since,
            )
    """
    try:
        result = import_fn(**kwargs)
    except Exception as exc:
        logger.exception("%s import failed", source_name)
        return ImportResponse(status="error", result={"ok": False, "error": str(exc)})
    return ImportResponse(status="completed", result=result)
