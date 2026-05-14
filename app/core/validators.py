"""Fase 13 · validadores centrales.

La lógica sensible debe validarse en backend, no solo en formularios.
Este módulo es deliberadamente pequeño y seguro: sirve como frontera
para ir moviendo validaciones sin alterar reservas/cargos.
"""
import re

_DNI_RE = re.compile(r"[^0-9A-Za-z]")


def clean_document(value: str) -> str:
    return _DNI_RE.sub("", (value or "").strip())[:32]


def clean_member_no(value: str) -> str:
    return re.sub(r"[^0-9]", "", (value or "").strip())[:16]


def is_safe_human_name(value: str) -> bool:
    v = (value or "").strip()
    return 2 <= len(v) <= 120 and "<" not in v and ">" not in v


def is_reasonable_email(value: str) -> bool:
    v = (value or "").strip()
    return (not v) or ("@" in v and "." in v and len(v) <= 160)
