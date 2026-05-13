"""
Fjord VI · Reliability primitives

Este módulo concentra criterios de confiabilidad que deben mantenerse como
referencia única para futuras validaciones de backend, tests y auditorías.

No ejecuta cambios destructivos por sí mismo. Define invariantes, transiciones
y helpers de validación para evitar que reglas operativas queden dispersas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple


APP_VERSION = "3.3"

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

ROLE_ALLOWED_ACTIONS: Dict[str, List[str]] = {
    "socio": [
        "ver_navegaciones",
        "reservar",
        "cancelar_mi_lugar",
        "agregar_invitado",
        "eliminar_invitado_pre_48",
        "ver_reglamento",
    ],
    "capitan": [
        "marcar_presente",
        "marcar_no_embarca",
        "reasignar_invitado",
        "cancelar_salida",
        "cerrar_salida",
        "reabrir_en_ventana",
        "ver_ficha",
    ],
    "admin": [
        "crear_salida",
        "editar_salida",
        "auditar",
        "reabrir_fuera_ventana",
        "corregir_con_auditoria",
        "configurar_smtp",
        "exportar",
        "backup",
    ],
}


@dataclass(frozen=True)
class ReliabilityIssue:
    code: str
    severity: str
    message: str


def can_transition(current_state: str, next_state: str) -> bool:
    return next_state in VALID_TRANSITIONS.get(current_state, [])


def validate_capacity(confirmed: int, capacity: int = 9) -> List[ReliabilityIssue]:
    issues: List[ReliabilityIssue] = []
    if confirmed < 0:
        issues.append(ReliabilityIssue("capacity_negative", "high", "La ocupación no puede ser negativa."))
    if confirmed > capacity:
        issues.append(ReliabilityIssue("capacity_overflow", "critical", "La ocupación supera la capacidad permitida."))
    return issues


def validate_single_active_closing(active_closings: int) -> List[ReliabilityIssue]:
    if active_closings > 1:
        return [ReliabilityIssue("multiple_active_closings", "critical", "Existe más de una ficha/liquidación vigente.")]
    return []


def validate_unique_identity(keys: List[str], label: str) -> List[ReliabilityIssue]:
    normalized = [str(k).strip().lower() for k in keys if str(k).strip()]
    if len(normalized) != len(set(normalized)):
        return [ReliabilityIssue("duplicate_identity", "high", f"Hay duplicación de identidad en {label}.")]
    return []


def validate_smtp_safety(settings: dict) -> List[ReliabilityIssue]:
    issues: List[ReliabilityIssue] = []
    if settings.get("smtp_enabled") and settings.get("smtp_test_mode"):
        if not settings.get("smtp_force_redirect_in_test", True):
            issues.append(ReliabilityIssue("smtp_test_without_redirect", "critical", "SMTP test mode activo sin redirect forzado."))
        if not settings.get("smtp_test_recipient_email") and not settings.get("smtp_test_redirect_email"):
            issues.append(ReliabilityIssue("smtp_test_without_recipient", "critical", "SMTP test mode activo sin email receptor de pruebas."))
    return issues
