"""logging_config.py — Centralised logging setup.

Call ``setup_logging()`` once in ``main.py`` before the app starts.
Every module should obtain its logger with::

    import logging
    logger = logging.getLogger(__name__)
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Configure the root logger for the FastAPI application.

    Format:
        2026-09-20 06:00:12 INFO  backend.routers.discussions  discussion_created id=abc123
    """
    fmt = "%(asctime)s %(levelname)-5s %(name)s  %(message)s"
    date_fmt = "%Y-%m-%d %H:%M:%S"

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=date_fmt))

    root = logging.getLogger()
    # Remove any handlers already attached (e.g., by uvicorn)
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # We want to see uvicorn's startup messages (which are logged to "uvicorn.error"),
    # but we can quieten the access logs so our custom middleware logs stand out.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
