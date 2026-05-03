import logging

from alfred.core.logging import setup_logging


def test_setup_logging_string_levels(monkeypatch):
    setup_logging("ERROR")
    root = logging.getLogger()
    assert root.getEffectiveLevel() == logging.ERROR
    assert len(root.handlers) >= 1

    setup_logging("debug")
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_setup_logging_numeric():
    setup_logging(10)  # DEBUG
    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_setup_logging_from_settings(monkeypatch):
    from alfred.core.settings import settings

    monkeypatch.setattr(settings, "log_level", "WARNING")
    monkeypatch.setattr(settings, "log_level_fallback", None)
    setup_logging(None)  # resolve from settings
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
