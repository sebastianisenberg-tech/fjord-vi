"""Helpers de contexto de request para futura separación de middleware."""
import secrets
from time import perf_counter


def new_request_id() -> str:
    return secrets.token_hex(8)


def start_timer() -> float:
    return perf_counter()


def elapsed_ms(started: float) -> int:
    return int((perf_counter() - started) * 1000)
