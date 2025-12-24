#!/usr/bin/env python
"""
Fail if any Python bytecode artifacts (.pyc files or __pycache__ dirs) are present.
"""

from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    offenders: list[Path] = []
    for path in root.rglob("*"):
        if path.name.endswith(".pyc") or path.name == "__pycache__":
            offenders.append(path)
    if offenders:
        for p in offenders:
            print(f"Bytecode artifact found: {p.relative_to(root)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
