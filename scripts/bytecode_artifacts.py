#!/usr/bin/env python
"""Shared helpers for Python bytecode artifact checks and cleanup."""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from pathlib import Path

EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".next",
        ".pytest_cache",
        ".ruff_cache",
        ".uv-cache",
        ".venv",
        "node_modules",
    }
)


def iter_bytecode_artifacts(root: Path) -> Iterator[Path]:
    """Yield bytecode artifacts below root, skipping heavyweight local caches."""

    root = root.resolve()
    for current_dir, dir_names, file_names in os.walk(root):
        dir_names[:] = [name for name in dir_names if name not in EXCLUDED_DIR_NAMES]

        if "__pycache__" in dir_names:
            path = Path(current_dir) / "__pycache__"
            yield path
            dir_names.remove("__pycache__")

        for file_name in file_names:
            if file_name.endswith((".pyc", ".pyo")):
                yield Path(current_dir) / file_name


def remove_bytecode_artifacts(root: Path) -> list[Path]:
    """Remove bytecode artifacts below root and return the removed paths."""

    removed: list[Path] = []
    for path in iter_bytecode_artifacts(root):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        removed.append(path)
    return removed
