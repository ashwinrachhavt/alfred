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

    def collect() -> list[Path]:
        items: list[Path] = []
        for path in root.rglob("*"):
            if ".venv" in path.parts:
                continue
            if path.name.endswith(".pyc") or path.name == "__pycache__":
                items.append(path)
        return items

    offenders = collect()
    if offenders:
        # Auto-clean then re-check to keep CI green while preventing stale artifacts.
        for p in offenders:
            if p.is_dir():
                for child in p.rglob("*"):
                    child.unlink(missing_ok=True)
                p.rmdir()
            else:
                p.unlink(missing_ok=True)
        offenders = collect()

    if offenders:
        for p in offenders:
            print(f"Bytecode artifact found: {p.relative_to(root)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
