"""Fase 14 · validaciones de negocio puras.

Estas funciones no dependen de FastAPI ni de la base de datos. Sirven como
frontera profesional para que las reglas críticas puedan testearse antes de
aplicarse en rutas y servicios.

La intención de esta fase es blindar sin alterar la operatoria existente:
primero se consolidan las reglas y sus tests; luego se conectan gradualmente
contra los endpoints críticos.
"""
from dataclasses import dataclass
from typing import Iterable, Optional


VALID_RESERVATION_STATES = {
    "activa",
    "pendiente",
    "presente",
    "no_embarco",
    "cancelada",
    "cerrada",
}

VALID_OUTING_STATES = {
    "abierta",
    "en_reservas",
    "cerrada",
    "cancelada",
}

WRITE_ROLES = {"admin", "captain"}
ADMIN_ONLY_ROLES = {"admin"}
CAPTAIN_ROLES = {"admin", "captain"}
SOCIO_ROLES = {"admin", "captain", "socio"}


@dataclass(frozen=True)
class RuleResult:
    ok: bool
    code: str
    message: str


def ok(code: str = "ok", message: str = "OK") -> RuleResult:
    return RuleResult(True, code, message)


def fail(code: str, message: str) -> RuleResult:
    return RuleResult(False, code, message)


def normalize_state(value: Optional[str]) -> str:
    return (value or "").strip().lower().replace(" ", "_").replace("-", "_")


def validate_capacity(current_active: int, max_capacity: int, requested: int = 1) -> RuleResult:
    """Evita cupos excedidos desde backend."""
    if max_capacity <= 0:
        return fail("capacity_invalid", "El cupo máximo configurado no es válido.")
    if current_active < 0 or requested < 1:
        return fail("capacity_request_invalid", "La cantidad solicitada no es válida.")
    if current_active + requested > max_capacity:
        return fail("capacity_exceeded", "No hay plazas disponibles para esta operación.")
    return ok("capacity_ok", "Hay cupo disponible.")


def validate_no_duplicate_document(document: str, existing_documents: Iterable[str]) -> RuleResult:
    """Bloquea DNI/documento duplicado dentro de una misma salida."""
    doc = (document or "").strip().lower()
    if not doc:
        return fail("document_required", "El documento es obligatorio para validar duplicados.")
    normalized = {(d or "").strip().lower() for d in existing_documents}
    if doc in normalized:
        return fail("duplicate_document", "Ya existe una reserva con ese documento en la salida.")
    return ok("document_unique", "Documento sin duplicados en la salida.")


def validate_outing_open_for_reservation(outing_state: str) -> RuleResult:
    state = normalize_state(outing_state)
    if state not in VALID_OUTING_STATES:
        return fail("outing_state_invalid", "El estado de la salida no es reconocido.")
    if state in {"cerrada", "cancelada"}:
        return fail("outing_not_open", "La salida no admite nuevas reservas en este estado.")
    return ok("outing_open", "La salida admite reservas.")


def validate_reservation_state_transition(current_state: str, target_state: str) -> RuleResult:
    current = normalize_state(current_state)
    target = normalize_state(target_state)
    if current not in VALID_RESERVATION_STATES:
        return fail("reservation_state_invalid", "El estado actual de la reserva no es reconocido.")
    if target not in VALID_RESERVATION_STATES:
        return fail("reservation_target_invalid", "El estado destino de la reserva no es reconocido.")
    if current == "cancelada" and target == "presente":
        return fail("cancelled_to_present_blocked", "Una reserva cancelada no puede pasar directo a presente.")
    if current == "cerrada" and target not in {"cerrada"}:
        return fail("closed_reservation_locked", "Una reserva cerrada no puede modificarse sin reapertura formal.")
    return ok("transition_ok", "Transición permitida.")


def validate_role_access(user_role: str, allowed_roles: Iterable[str]) -> RuleResult:
    role = normalize_state(user_role)
    allowed = {normalize_state(r) for r in allowed_roles}
    if role not in allowed:
        return fail("role_forbidden", "El usuario no tiene permisos para esta operación.")
    return ok("role_allowed", "Permiso concedido.")


def validate_guest_has_responsible_member(responsible_member_no: Optional[str]) -> RuleResult:
    member = (responsible_member_no or "").strip()
    if not member:
        return fail("guest_without_responsible", "El invitado debe estar asociado a un socio responsable.")
    return ok("guest_responsible_ok", "Invitado asociado a socio responsable.")


def validate_captain_close_window(now_ts: float, departure_ts: float, close_after_seconds: int = 48 * 3600) -> RuleResult:
    """Valida ventana de cierre de capitán sin depender de timezone ni DB."""
    if now_ts < departure_ts:
        return fail("close_before_departure", "El capitán no puede cerrar antes del horario programado.")
    if now_ts > departure_ts + close_after_seconds:
        return fail("close_window_expired", "La ventana de cierre del capitán venció; requiere Administración.")
    return ok("close_window_ok", "El capitán puede cerrar dentro de la ventana permitida.")


def validate_admin_reset_confirmation(typed: str, expected: str) -> RuleResult:
    if (typed or "").strip() != (expected or "").strip():
        return fail("confirmation_mismatch", "La frase de confirmación no coincide.")
    return ok("confirmation_ok", "Confirmación válida.")
