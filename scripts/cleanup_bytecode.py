"""
Remove Python bytecode artifacts from the repo tree.

This script deletes:
- All `__pycache__` directories
- All `*.pyc` and `*.pyo` files

It skips typical virtualenv and VCS directories.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "env", ".ruff_cache", ".mypy_cache"}


def is_skipped_dir(name: str) -> bool:
    return name in SKIP_DIRS


def cleanup(root: Path) -> int:
    removed = 0
    for cur_root, dirs, files in os.walk(root, topdown=True):
        # prune skipped dirs early
        dirs[:] = [d for d in dirs if not is_skipped_dir(d)]

        # remove __pycache__ dirs
        for d in list(dirs):
            if d == "__pycache__":
                p = Path(cur_root) / d
                try:
                    shutil.rmtree(p)
                    removed += 1
                except Exception:
                    pass
                dirs.remove(d)

        # remove .pyc / .pyo files
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                p = Path(cur_root) / f
                try:
                    p.unlink(missing_ok=True)
                    removed += 1
                except Exception:
                    pass
    return removed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("scripts.cleanup_bytecode")
    repo_root = Path(__file__).resolve().parents[1]
    count = cleanup(repo_root)
    logger.info("Removed %d bytecode artifacts", count)

