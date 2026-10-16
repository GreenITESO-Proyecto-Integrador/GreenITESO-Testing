"""Logger compartido del framework. Escribe a consola (vía pytest) y a reporting/logs."""

import logging
import os
from datetime import datetime

from src.configs.environment import LOGS_DIR

_LOGGER_NAME = "greeniteso"


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child of the framework logger (e.g. get_logger(__name__))."""
    return logging.getLogger(f"{_LOGGER_NAME}.{name}" if name else _LOGGER_NAME)


def setup_file_logging() -> None:
    """Attach a timestamped file handler to the framework logger (idempotent)."""
    root = logging.getLogger(_LOGGER_NAME)
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    # Con pytest-xdist cada worker es un proceso aparte (gw0, gw1, ...) y escribe su propio archivo.
    worker = os.getenv("PYTEST_XDIST_WORKER", "main")
    handler = logging.FileHandler(LOGS_DIR / f"run_{datetime.now():%Y%m%d_%H%M%S}_{worker}.log", encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
    root.addHandler(handler)
    root.setLevel(logging.DEBUG)
