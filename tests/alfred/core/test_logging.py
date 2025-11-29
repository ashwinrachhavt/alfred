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


def test_setup_logging_from_env(monkeypatch):
    monkeypatch.setenv("ALFRED_LOG_LEVEL", "WARNING")
    setup_logging(None)  # resolve from env
    assert logging.getLogger().getEffectiveLevel() == logging.WARNING
