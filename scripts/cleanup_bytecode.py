#!/usr/bin/env python
"""
Remove Python bytecode artifacts (.pyc files and __pycache__ directories).
"""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    for path in root.rglob("*"):
        if path.name.endswith(".pyc"):
            path.unlink(missing_ok=True)
        elif path.name == "__pycache__":
            shutil.rmtree(path, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
