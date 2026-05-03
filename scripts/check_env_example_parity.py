#!/usr/bin/env python
"""Fail if a field in Settings has no entry in apps/alfred/.env.example.

This keeps developer onboarding honest: every config flag the app reads must be
documented in the example file (even if commented-out). Extra example vars are
fine — we only flag missing ones.

Env-var name resolution:
  - Pydantic `Field(..., alias="FOO")` → FOO
  - Otherwise the bare attribute name, uppercased.

Lines in .env.example that count as "documented":
  - KEY=...
  - # KEY=...
  - KEY (bare)
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "apps" / "alfred" / "core" / "settings.py"
ENV_EXAMPLE = ROOT / "apps" / "alfred" / ".env.example"

KEY_RE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]*)\s*=")
BARE_KEY_RE = re.compile(r"^\s*#?\s*([A-Z][A-Z0-9_]+)\s*$")


def extract_env_keys_from_example(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        m = KEY_RE.match(line) or BARE_KEY_RE.match(line)
        if m:
            keys.add(m.group(1))
    return keys


def extract_settings_fields(path: Path) -> list[tuple[str, str | None, int]]:
    """Return (attr_name, alias_or_None, lineno) for each field in Settings."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    results: list[tuple[str, str | None, int]] = []

    settings_cls = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            settings_cls = node
            break
    if settings_cls is None:
        return results

    for stmt in settings_cls.body:
        if not isinstance(stmt, ast.AnnAssign):
            continue
        if not isinstance(stmt.target, ast.Name):
            continue
        name = stmt.target.id
        if name.startswith("_"):
            continue
        alias = _extract_alias(stmt.value)
        results.append((name, alias, stmt.lineno))
    return results


def _extract_alias(value: ast.expr | None) -> str | None:
    """Pull `alias="..."` out of Field(...) or similar calls."""
    if value is None or not isinstance(value, ast.Call):
        return None
    for kw in value.keywords:
        if kw.arg in {"alias", "env"} and isinstance(kw.value, ast.Constant):
            v = kw.value.value
            if isinstance(v, str):
                return v
    return None


def env_name_for(attr: str, alias: str | None) -> str:
    return alias if alias else attr.upper()


def main() -> int:
    documented = extract_env_keys_from_example(ENV_EXAMPLE)
    fields = extract_settings_fields(SETTINGS)

    missing: list[tuple[str, str, int]] = []
    for attr, alias, lineno in fields:
        env = env_name_for(attr, alias)
        if env not in documented:
            missing.append((attr, env, lineno))

    if not missing:
        return 0

    print(
        f"{ENV_EXAMPLE.relative_to(ROOT)} is missing {len(missing)} variable(s) "
        f"declared in apps/alfred/core/settings.py.\n"
        "Add each as a commented example line (e.g., `# KEY=default`) so developers know it exists.\n"
    )
    for attr, env, lineno in missing:
        print(f"  missing: {env}  (Settings.{attr} at settings.py:{lineno})")
    return 1


if __name__ == "__main__":
    sys.exit(main())
