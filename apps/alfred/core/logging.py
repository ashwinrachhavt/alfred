import logging
import sys


def setup_logging(level: str | int | None = None) -> None:
    """Initialize root logger once with stream handler and level.

    Level is resolved by precedence:
      1) explicit `level` arg
      2) settings: ALFRED_LOG_LEVEL then LOG_LEVEL
      3) default INFO
    """
    # Import lazily: logging is initialized very early in main.py/celery_app.py and
    # we don't want to force settings resolution if the caller passes an explicit level.
    if level is None:
        from alfred.core.settings import settings
        raw = settings.log_level or settings.log_level_fallback
    else:
        raw = level
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
