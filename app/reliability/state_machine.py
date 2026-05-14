from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List

APP_VERSION = "3.7.3"

VALID_TRANSITIONS: Dict[str, List[str]] = {
    "borrador": ["reserva", "cancelada"],
    "reserva": ["confirmacion", "cancelada"],
    "confirmacion": ["embarque", "cancelada"],
    "embarque": ["cierre", "cancelada"],
    "cierre": ["reapertura", "historial"],
    "reapertura": ["embarque", "cierre"],
    "historial": [],
    "cancelada": [],
}

@dataclass(frozen=True)
class ReliabilityIssue:
    code: str
    severity: str
    message: str

def can_transition(current_state: str, next_state: str) -> bool:
    return next_state in VALID_TRANSITIONS.get(current_state, [])

def validate_capacity(confirmed: int, capacity: int = 9) -> list[ReliabilityIssue]:
    issues = []
    if confirmed < 0:
        issues.append(ReliabilityIssue("capacity_negative", "high", "La ocupación no puede ser negativa."))
    if confirmed > capacity:
        issues.append(ReliabilityIssue("capacity_overflow", "critical", "La ocupación supera la capacidad permitida."))
    return issues

def validate_single_active_closing(active_closings: int) -> list[ReliabilityIssue]:
    if active_closings > 1:
        return [ReliabilityIssue("multiple_active_closings", "critical", "Existe más de una ficha/liquidación vigente.")]
    return []

def validate_unique_identity(keys: list[str], label: str) -> list[ReliabilityIssue]:
    normalized = [str(k).strip().lower() for k in keys if str(k).strip()]
    if len(normalized) != len(set(normalized)):
        return [ReliabilityIssue("duplicate_identity", "high", f"Hay duplicación de identidad en {label}.")]
    return []

def validate_smtp_safety(settings: dict) -> list[ReliabilityIssue]:
    issues = []
    if settings.get("smtp_test_mode"):
        if not settings.get("smtp_force_redirect_in_test", True):
            issues.append(ReliabilityIssue("smtp_test_without_redirect", "critical", "Modo prueba SMTP activo sin redirección forzada."))
        if not settings.get("smtp_test_recipient_email") and not settings.get("smtp_test_redirect_email"):
            issues.append(ReliabilityIssue("smtp_test_without_recipient", "critical", "Modo prueba SMTP activo sin email receptor de pruebas."))
    return issues
