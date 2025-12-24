"""SQLAdmin setup for Alfred.

Creates the admin instance, registers ModelViews/BaseViews, and mounts it
under ``/admin``. Keeping setup in one place avoids import-time side effects
in FastAPI startup.
"""

from __future__ import annotations

from fastapi import FastAPI
from sqladmin import Admin

from alfred.admin.views import (
    CompanyInterviewAdmin,
    LearningTopicAdmin,
    UserAdmin,
    ZettelCardAdmin,
    ZettelCardImportView,
)
from alfred.core.database import engine


def mount_admin(app: FastAPI) -> Admin:
    """Attach SQLAdmin to the FastAPI app and register all views."""

    admin = Admin(app, engine, base_url="/admin", title="Alfred Admin")
    admin.add_view(UserAdmin)
    admin.add_view(ZettelCardAdmin)
    admin.add_view(LearningTopicAdmin)
    admin.add_view(CompanyInterviewAdmin)
    admin.add_base_view(ZettelCardImportView)

    # expose for later reuse/tests if needed
    app.state.admin = admin
    return admin


__all__ = ["mount_admin"]
