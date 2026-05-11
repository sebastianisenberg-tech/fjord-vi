"""Fase 13 · observabilidad liviana.

Este módulo deja una frontera clara para mover métricas, trazas y logs
estructurados fuera de main.py sin cambiar la operación visible.
"""
from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class RequestMetric:
    path: str
    method: str
    status_code: int
    elapsed_ms: int


def elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)


OBSERVABILITY_PHASE = "Fase 13 · request id, tiempos y frontera de métricas"
