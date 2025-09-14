import sys
from pathlib import Path

"""Ensure `alfred` package is importable during tests.

Place the parent of the package (`apps/`) on sys.path so imports like
`from alfred.core.config import Settings` resolve to `apps/alfred`.
"""
ROOT = Path(__file__).resolve().parents[1]
APPS_DIR = ROOT / "apps"
if str(APPS_DIR) not in sys.path:
    sys.path.insert(0, str(APPS_DIR))
