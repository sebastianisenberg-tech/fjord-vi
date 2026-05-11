"""Fase 15 · logging estructurado mínimo.

No agrega dependencias externas. Deja una base consistente para que Render,
soporte o una futura herramienta de monitoreo puedan correlacionar errores.
"""
import logging
import sys
from typing import Final

LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    numeric = getattr(logging, (level or "INFO").upper(), logging.INFO)
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(numeric)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


LOGGING_PHASE = "Fase 15 · logging base centralizado"
