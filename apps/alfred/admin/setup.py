"""Mount the SQLAdmin UI onto the FastAPI app.

Call :func:`mount_admin` from :mod:`alfred.main` after
:func:`register_routes`. The admin lives at ``/admin`` and uses the same
sync engine as the rest of the app (see :mod:`alfred.core.database`).
"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from sqladmin import Admin

from alfred.admin.auth import build_auth_backend
from alfred.admin.views import ALL_VIEWS
from alfred.core.database import engine

logger = logging.getLogger(__name__)


def mount_admin(app: FastAPI) -> Admin:
    """Attach SQLAdmin at ``/admin`` and register every known view.

    Returns the ``Admin`` instance so callers can register additional views
    at runtime if needed (e.g. tests).
    """

    admin = Admin(
        app=app,
        engine=engine,
        title="Alfred Admin",
        base_url="/admin",
        authentication_backend=build_auth_backend(),
    )
    for view in ALL_VIEWS:
        admin.add_view(view)

    logger.info("SQLAdmin mounted at /admin with %d views", len(ALL_VIEWS))
    return admin
