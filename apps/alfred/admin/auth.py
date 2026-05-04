"""Authentication backend for the SQLAdmin UI.

SQLAdmin mounts as a Starlette sub-app, so the app-level Clerk dependency
registered in :func:`alfred.api.register_routes` does NOT apply. The admin
surface must enforce its own policy.

This backend runs on every admin page load and handles three flows:

* ``login``     — called when the user submits the login form.
* ``logout``    — clears the admin session.
* ``authenticate`` — called on every subsequent request to verify access.

The ``authenticate`` policy is the single most important security decision
for this feature, so it is intentionally left for the project owner to
define (see TODO below).
"""

from __future__ import annotations

import logging

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request
from starlette.responses import RedirectResponse

from alfred.core.settings import get_settings

logger = logging.getLogger(__name__)


class AdminAuthBackend(AuthenticationBackend):
    """Gate the SQLAdmin UI behind a project-defined policy.

    The ``authenticate`` method is the hot path — it runs on every request
    to ``/admin/*``. It must be fast and must NEVER silently fall open.
    """

    async def login(self, request: Request) -> bool:
        """Validate the submitted login form and stash a session marker.

        The default implementation reads ``ALFRED_ADMIN_PASSWORD`` from
        settings-derived env and compares it against the submitted value.
        Swap this for Clerk JWT validation or IP allowlisting once the
        policy in :meth:`authenticate` is decided.
        """

        form = await request.form()
        submitted = str(form.get("password") or "")

        import os

        expected = os.getenv("ALFRED_ADMIN_PASSWORD", "")
        if not expected:
            logger.warning("ALFRED_ADMIN_PASSWORD is not set — admin login refused.")
            return False

        if submitted != expected:
            return False

        request.session.update({"admin_authenticated": True})
        return True

    async def logout(self, request: Request) -> bool:
        """Drop the admin session marker."""

        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool | RedirectResponse:
        """Gate every admin request.

        TODO(ashwin): decide the policy.

        Options to consider:
          (a) Simple password gate (matches ``login`` above) — easiest,
              fine for a solo-dev knowledge factory, but no audit trail
              and no per-user permissions.
          (b) Clerk JWT + ``User.is_superuser`` check — reuses your
              existing identity, gives per-user admin flags, but adds
              coupling to Clerk availability. See ``alfred.core.auth``.
          (c) IP allowlist + password — belt-and-suspenders for when the
              admin is exposed beyond localhost (e.g. via Cloud Run).

        Return ``True`` to allow, ``False`` to reject, or a
        :class:`RedirectResponse` to send the user somewhere specific.

        See :func:`alfred.core.auth.get_current_user` for how the rest of
        the app verifies Clerk JWTs — reuse that machinery if you pick (b).
        """

        raise NotImplementedError(
            "Admin authenticate() policy is unset — see TODO in alfred/admin/auth.py"
        )


def build_auth_backend() -> AdminAuthBackend:
    """Factory used by :mod:`alfred.admin.setup` at mount time."""

    settings = get_settings()
    secret = (
        settings.secret_key.get_secret_value()
        if settings.secret_key is not None
        else "dev-admin-session-secret-change-me"
    )
    return AdminAuthBackend(secret_key=secret)
