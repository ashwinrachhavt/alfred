import logging
import sys


def setup_logging():
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        fmt = logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"
        )
        handler.setFormatter(fmt)
        root.addHandler(handler)
        root.setLevel(logging.INFO)
