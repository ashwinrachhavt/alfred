"""
Fail if Python bytecode artifacts exist in the repo tree.

Checks for:
- Any `__pycache__` directories
- Any `*.pyc` or `*.pyo` files

Skips common virtualenv and VCS directories.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "env", ".ruff_cache"}


def is_skipped_dir(name: str) -> bool:
    return name in SKIP_DIRS


def find_bytecode(root: Path) -> list[Path]:
    offenders: list[Path] = []
    for cur_root, dirs, files in os.walk(root, topdown=True):
        dirs[:] = [d for d in dirs if not is_skipped_dir(d)]
        for d in dirs:
            if d == "__pycache__":
                offenders.append(Path(cur_root) / d)
        for f in files:
            if f.endswith((".pyc", ".pyo")):
                offenders.append(Path(cur_root) / f)
    return offenders


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("scripts.check_no_bytecode")
    repo_root = Path(__file__).resolve().parents[1]
    offenders = find_bytecode(repo_root)
    if offenders:
        logger.error("Bytecode artifacts found (fail):")
        for p in offenders:
            logger.error(" - %s", p)
        sys.exit(1)
    logger.info("No bytecode artifacts found.")
