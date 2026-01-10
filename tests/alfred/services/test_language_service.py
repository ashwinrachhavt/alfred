from __future__ import annotations

from alfred.services.language_service import LanguageService


def test_language_detect_empty() -> None:
    svc = LanguageService()
    res = svc.detect(text="")
    assert res.language is None
    assert res.provider == "empty"


def test_language_detect_smoke() -> None:
    svc = LanguageService()
    res = svc.detect(text="Hello world, this is a short English sentence.")
    assert res.provider in {"langid", "unavailable", "langid_error"}
