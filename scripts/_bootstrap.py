from __future__ import annotations

import sys
from pathlib import Path


def bootstrap(additional_paths: list[Path] | None = None) -> None:
    """Add `apps/` to sys.path and import sitecustomize for env setup.

    - Ensures repository's `apps/` directory is importable so `import alfred` works.
    - Imports `sitecustomize` to load `.env` and respect bytecode settings.
    - Optionally adds extra paths provided by callers.
    """
    repo_root = Path(__file__).resolve().parents[1]
    apps_dir = repo_root / "apps"
    if str(apps_dir) not in sys.path:
        sys.path.insert(0, str(apps_dir))

    if additional_paths:
        for p in additional_paths:
            if str(p) not in sys.path:
                sys.path.insert(0, str(p))

    import sitecustomize  # noqa: F401
