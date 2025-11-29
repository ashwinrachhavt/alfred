"""Early bootstrapping for Alfred when `apps/` is on `sys.path`.

This module is imported automatically by Python at startup if found on
`sys.path` (see the `site` module). We leverage it to:

- Load environment variables from `.env` files (package-local first, then repo root).
- Respect `PYTHONDONTWRITEBYTECODE` to avoid `__pycache__` churn in dev.

It is safe and idempotent: guarded by `ALFRED_ENV_LOADED` so repeated imports
do not reload the `.env` file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _load_env_once() -> None:
    if os.environ.get("ALFRED_ENV_LOADED") == "1":
        return

    try:
        from dotenv import load_dotenv  # type: ignore

        apps_dir = Path(__file__).resolve().parent
        pkg_env = apps_dir / "alfred" / ".env"
        root_env = apps_dir.parent / ".env"

        if pkg_env.exists():
            load_dotenv(pkg_env)
        elif root_env.exists():
            load_dotenv(root_env)
    except Exception:
        # Dotenv is optional; ignore if unavailable.
        pass
    finally:
        os.environ["ALFRED_ENV_LOADED"] = "1"


def _set_no_pyc() -> None:
    if os.environ.get("PYTHONDONTWRITEBYTECODE") == "1":
        try:
            sys.dont_write_bytecode = True
        except Exception:
            pass


_load_env_once()
_set_no_pyc()
