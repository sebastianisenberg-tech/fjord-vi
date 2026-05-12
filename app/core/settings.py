"""Fase 15 · settings centralizados.

Frontera de configuración para ir sacando constantes de main.py sin alterar
la operación actual. No expone secretos y permite documentar defaults.
"""
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AppSettings:
    app_version: str
    app_env: str
    log_level: str
    session_max_age_seconds: int
    login_lock_attempts: int
    login_lock_window_minutes: int
    operation_lock_ttl_seconds: int
    system_fast_cache_seconds: int


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def load_settings(app_version: str) -> AppSettings:
    return AppSettings(
        app_version=app_version,
        app_env=os.getenv("APP_ENV", "development").strip().lower(),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper(),
        session_max_age_seconds=_int_env("SESSION_MAX_AGE_SECONDS", 43200),
        login_lock_attempts=_int_env("LOGIN_LOCK_ATTEMPTS", 20),
        login_lock_window_minutes=_int_env("LOGIN_LOCK_WINDOW_MINUTES", 30),
        operation_lock_ttl_seconds=_int_env("OPERATION_LOCK_TTL_SECONDS", 30),
        system_fast_cache_seconds=_int_env("SYSTEM_FAST_CACHE_SECONDS", 45),
    )


SETTINGS_PHASE = "Fase 15 · settings centralizados"
