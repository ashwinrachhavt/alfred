import sys
from pathlib import Path

"""Ensure `alfred` is importable in tests.

Add the `apps/` directory to `sys.path` so `import alfred` resolves to
`apps/alfred`. Then import `sitecustomize` to load `.env` early.
"""

ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))

# Trigger environment bootstrap (idempotent)
try:  # pragma: no cover - simple import side effect
    import sitecustomize  # noqa: F401
except Exception:
    pass
