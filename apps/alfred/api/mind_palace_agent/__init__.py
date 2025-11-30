from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()

from .routes import router as _routes  # noqa: E402  (lazy import wiring)
router.include_router(_routes)

