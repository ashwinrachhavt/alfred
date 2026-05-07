from __future__ import annotations

import os

import pytest

from alfred.core.settings import Settings


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("/Users/example", ["/Users/example"]),
        ('["/tmp/a", "/tmp/b"]', ["/tmp/a", "/tmp/b"]),
        (f"/tmp/a{os.pathsep}/tmp/b", ["/tmp/a", "/tmp/b"]),
        ("/tmp/a,/tmp/b", ["/tmp/a", "/tmp/b"]),
    ],
)
def test_notes_filesystem_roots_accepts_docker_env_strings(
    monkeypatch: pytest.MonkeyPatch,
    raw_value: str,
    expected: list[str],
) -> None:
    monkeypatch.setenv("ALFRED_NOTES_FILESYSTEM_ROOTS", raw_value)

    settings = Settings(_env_file=None)

    assert settings.notes_filesystem_roots == expected
