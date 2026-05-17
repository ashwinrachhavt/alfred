#!/usr/bin/env python
"""
Remove Python bytecode artifacts (.pyc files and __pycache__ directories).
"""

from __future__ import annotations

from pathlib import Path

from bytecode_artifacts import remove_bytecode_artifacts


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    remove_bytecode_artifacts(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
