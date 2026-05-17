#!/usr/bin/env python
"""
Fail if any Python bytecode artifacts (.pyc files or __pycache__ dirs) are present.
"""

from __future__ import annotations

import sys
from pathlib import Path

from bytecode_artifacts import iter_bytecode_artifacts


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    offenders = list(iter_bytecode_artifacts(root))

    if offenders:
        for path in offenders:
            print(f"Bytecode artifact found: {path.relative_to(root)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
