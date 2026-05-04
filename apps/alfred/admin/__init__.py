"""SQLAdmin integration for Alfred.

Mounts a Django-style admin UI at ``/admin`` for browsing and editing
SQLModel tables. Auth is delegated to :mod:`alfred.admin.auth`.

Do NOT confuse this with :mod:`alfred.api.admin`, which exposes operational
JSON endpoints under ``/api/admin/*`` (concept extraction backlogs, etc.).
"""

from __future__ import annotations

from .setup import mount_admin

__all__ = ["mount_admin"]
