#!/usr/bin/env python
"""Fail if os.getenv(...) or os.environ.get(...) is used outside approved files.

All config should route through `alfred.core.settings` so Pydantic validates it
and .env.example stays in sync. See CLAUDE.md.

Approved exceptions:
  - apps/alfred/core/settings.py  (the authorized consumer)
  - tests/**                      (may read/mutate env)
  - **/conftest.py                (test setup hooks)
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_DIRS = [ROOT / "apps" / "alfred"]

ALLOWED = {
    ROOT / "apps" / "alfred" / "core" / "settings.py",
}

ALLOWED_GLOBS = (
    "tests/",
    "/conftest.py",
)

PATTERN = re.compile(r"\bos\.(getenv|environ\.get|environ\[)")


def is_allowed(path: Path) -> bool:
    if path in ALLOWED:
        return True
    s = str(path)
    return any(glob in s for glob in ALLOWED_GLOBS)


def main() -> int:
    offenders: list[tuple[Path, int, str]] = []
    for target in TARGET_DIRS:
        for py in target.rglob("*.py"):
            if is_allowed(py):
                continue
            try:
                lines = py.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for n, line in enumerate(lines, start=1):
                # Skip comments and docstrings heuristically (keeps it dumb + fast).
                stripped = line.lstrip()
                if stripped.startswith("#"):
                    continue
                if PATTERN.search(line):
                    offenders.append((py, n, line.rstrip()))

    if not offenders:
        return 0

    print(
        "Direct env-var access is banned outside apps/alfred/core/settings.py.\n"
        "Use `from alfred.core.settings import settings` so Pydantic validates config.\n"
    )
    for path, n, line in offenders:
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        print(f"  {rel}:{n}: {line.strip()}")
    print(f"\n{len(offenders)} violation(s).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
