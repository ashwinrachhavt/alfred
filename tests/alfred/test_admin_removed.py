from __future__ import annotations

import importlib.util

from alfred.main import app


def test_sqladmin_package_is_not_available() -> None:
    assert importlib.util.find_spec("alfred.admin") is None


def test_sqladmin_ui_is_not_mounted() -> None:
    admin_routes = [
        route
        for route in app.routes
        if (path := getattr(route, "path", "")) == "/admin" or path.startswith("/admin/")
    ]

    assert admin_routes == []
