"""Fase 15 · servicios de operación.

Punto de entrada gradual para mover reglas desde rutas hacia servicios. Por
ahora ofrece helpers puros y seguros, sin modificar datos.
"""
from dataclasses import dataclass
from typing import Any
from app.core.business_rules import validate_capacity, validate_role
from app.core.errors import BusinessRuleAppError, PermissionAppError


@dataclass(frozen=True)
class OperationDecision:
    ok: bool
    code: str
    message: str


def require_operation_role(role: str, allowed: set[str], action: str = "operar") -> OperationDecision:
    result = validate_role(role, allowed)
    if not result.ok:
        raise PermissionAppError(f"El rol {role or '-'} no puede {action}.", code=result.code)
    return OperationDecision(True, result.code, result.message)


def require_capacity(current_count: int, max_crew: int) -> OperationDecision:
    result = validate_capacity(current_count=current_count, max_crew=max_crew)
    if not result.ok:
        raise BusinessRuleAppError(result.message, code=result.code, context={"current_count": current_count, "max_crew": max_crew})
    return OperationDecision(True, result.code, result.message)


SERVICE_PHASE = "Fase 15 · servicios de operación preparados"
