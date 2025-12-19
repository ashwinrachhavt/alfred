import logging
import os
import sys


def setup_logging(level: str | int | None = None) -> None:
    """Initialize root logger once with stream handler and level.

    Level is resolved by precedence:
      1) explicit `level` arg
      2) env `ALFRED_LOG_LEVEL` or `LOG_LEVEL`
      3) default INFO
    """
    raw = level if level is not None else (os.getenv("ALFRED_LOG_LEVEL") or os.getenv("LOG_LEVEL"))
    if isinstance(raw, int):
        desired_level = raw
    elif isinstance(raw, str):
        name = raw.strip().upper()
        if name.isdigit():
            desired_level = int(name)
        else:
            name_map = {
                "CRITICAL": logging.CRITICAL,
                "ERROR": logging.ERROR,
                "WARNING": logging.WARNING,
                "WARN": logging.WARNING,
                "INFO": logging.INFO,
                "DEBUG": logging.DEBUG,
                "NOTSET": logging.NOTSET,
            }
            desired_level = name_map.get(name, logging.INFO)
    else:
        desired_level = logging.INFO

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        handler.setFormatter(fmt)
        root.addHandler(handler)
        logging.captureWarnings(True)
    root.setLevel(desired_level)
