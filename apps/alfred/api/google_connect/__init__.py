"""Google OAuth connect UI and API routes."""

from .routes import api_router, legacy_router, ui_router

__all__ = ["api_router", "ui_router", "legacy_router"]
