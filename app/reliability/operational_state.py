from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

APP_VERSION = "3.8.6-production-ready-rc1"

# Estados reales usados por el monolito. Este módulo NO introduce una segunda
# nomenclatura: formaliza la semántica existente para que las rutas no escriban
# estados arbitrarios.
OUTING_OPEN_STATES = {"Programada", "En reservas", "Reprogramada", "Demorada"}
OUTING_CLOSED_STATES = {"Embarque cerrado", "Realizada"}
OUTING_CANCELLED_STATES = {"Cancelada por capitán", "Cancelado", "Cancelada"}
OUTING_STATES = OUTING_OPEN_STATES | OUTING_CLOSED_STATES | OUTING_CANCELLED_STATES

RESERVATION_ACTIVE_STATUSES = {"Confirmado", "Condicional hasta 48h", "Hijo menor de socio no socio"}
RESERVATION_WAITLIST_STATUS = "Lista de espera"
RESERVATION_CANCELLED_STATUS = "Cancelado"
RESERVATION_STATUSES = RESERVATION_ACTIVE_STATUSES | {RESERVATION_WAITLIST_STATUS, RESERVATION_CANCELLED_STATUS}

ATTENDANCE_ACTIVE = {"Por confirmar", "Presente"}
ATTENDANCE_INACTIVE = {"Ausente", "No embarca", "No embarcable", "Lista de espera"}
ATTENDANCE_VALUES = ATTENDANCE_ACTIVE | ATTENDANCE_INACTIVE

ALLOWED_OUTING_TRANSITIONS = {
    "Programada": {"Programada", "En reservas", "Reprogramada", "Demorada", "Cancelada por capitán", "Embarque cerrado"},
    "En reservas": {"En reservas", "Reprogramada", "Demorada", "Cancelada por capitán", "Embarque cerrado"},
    "Reprogramada": {"Reprogramada", "En reservas", "Demorada", "Cancelada por capitán", "Embarque cerrado"},
    "Demorada": {"Demorada", "En reservas", "Reprogramada", "Cancelada por capitán", "Embarque cerrado"},
    "Embarque cerrado": {"Embarque cerrado", "En reservas"},
    "Realizada": {"Realizada", "En reservas"},
    "Cancelada por capitán": {"Cancelada por capitán", "En reservas"},
}

ALLOWED_RESERVATION_TRANSITIONS = {
    "Confirmado": {"Confirmado", "Condicional hasta 48h", "Lista de espera", "Cancelado", "Hijo menor de socio no socio"},
    "Condicional hasta 48h": {"Condicional hasta 48h", "Confirmado", "Lista de espera", "Cancelado"},
    "Hijo menor de socio no socio": {"Hijo menor de socio no socio", "Lista de espera", "Cancelado"},
    "Lista de espera": {"Lista de espera", "Confirmado", "Condicional hasta 48h", "Hijo menor de socio no socio", "Cancelado"},
    "Cancelado": {"Cancelado"},
}

@dataclass(frozen=True)
class StateIssue:
    code: str
    severity: str
    message: str


def can_outing_transition(current: str, target: str) -> bool:
    current = (current or "Programada").strip()
    target = (target or "").strip()
    return target in ALLOWED_OUTING_TRANSITIONS.get(current, set())


def can_reservation_transition(current: str, target: str) -> bool:
    current = (current or "Confirmado").strip()
    target = (target or "").strip()
    return target in ALLOWED_RESERVATION_TRANSITIONS.get(current, set())


def is_outing_mutable(status: str) -> bool:
    return (status or "").strip() in OUTING_OPEN_STATES


def is_reservation_waitlisted(status: str, attendance: str = "") -> bool:
    return (status or "").strip() == RESERVATION_WAITLIST_STATUS or (attendance or "").strip() == RESERVATION_WAITLIST_STATUS


def validate_reservation_record(r) -> list[StateIssue]:
    issues: list[StateIssue] = []
    status = (getattr(r, "status", "") or "").strip()
    attendance = (getattr(r, "attendance", "") or "").strip()
    charge = float(getattr(r, "charge_amount", 0) or 0)
    protocolar = bool(getattr(r, "protocolar", False))

    if status and status not in RESERVATION_STATUSES:
        issues.append(StateIssue("unknown_reservation_status", "high", f"Estado de reserva no formalizado: {status}"))
    if attendance and attendance not in ATTENDANCE_VALUES:
        issues.append(StateIssue("unknown_attendance", "high", f"Estado de asistencia no formalizado: {attendance}"))
    if is_reservation_waitlisted(status, attendance):
        if attendance == "Presente":
            issues.append(StateIssue("waitlist_present", "critical", "Una reserva en espera no puede figurar Presente."))
        if charge > 0:
            issues.append(StateIssue("waitlist_charged", "critical", "Una reserva en espera no puede tener cargo."))
    if status == RESERVATION_CANCELLED_STATUS and attendance == "Presente":
        issues.append(StateIssue("cancelled_present", "critical", "Una reserva cancelada no puede figurar Presente."))
    if protocolar and charge > 0:
        issues.append(StateIssue("protocolar_charged", "critical", "Una participación protocolar nunca debe tener cargo."))
    return issues


def validate_capacity(active_count: int, max_crew: int) -> list[StateIssue]:
    if active_count > max_crew:
        return [StateIssue("capacity_overflow", "critical", f"Cupo operativo excedido: {active_count}/{max_crew}")]
    if active_count < 0:
        return [StateIssue("capacity_negative", "critical", "El cupo operativo no puede ser negativo.")]
    return []


def validate_unique_active_identities(rows: Iterable, active_predicate) -> list[StateIssue]:
    issues: list[StateIssue] = []
    seen = {}
    for r in rows:
        if not active_predicate(r):
            continue
        key = (getattr(r, "dni", "") or "").strip().lower() or f"row:{getattr(r, 'id', '')}"
        if key in seen:
            issues.append(StateIssue("duplicate_active_identity", "critical", f"Identidad activa duplicada: {seen[key]} / {getattr(r, 'person_name', '')}"))
        else:
            seen[key] = getattr(r, "person_name", "")
    return issues


def issues_to_messages(issues: Iterable[StateIssue]) -> list[str]:
    return [i.message for i in issues]
