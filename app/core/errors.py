"""Fase 15 · frontera profesional de errores.

Errores tipados para separar fallas de validación, permisos, reglas de negocio
y fallas técnicas. El objetivo es que rutas, servicios y repositorios no
improvisen mensajes ni expongan tracebacks al usuario final.
"""
from dataclasses import dataclass, field
from html import escape
from typing import Any, Mapping


@dataclass
class AppError(Exception):
    message: str
    code: str = "app_error"
    status_code: int = 400
    context: Mapping[str, Any] = field(default_factory=dict)
    safe_for_user: bool = True

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


class ValidationAppError(AppError):
    def __init__(self, message: str, code: str = "validation_error", context: Mapping[str, Any] | None = None):
        super().__init__(message=message, code=code, status_code=400, context=context or {})


class PermissionAppError(AppError):
    def __init__(self, message: str = "No tenés permiso para realizar esta acción.", code: str = "permission_denied", context: Mapping[str, Any] | None = None):
        super().__init__(message=message, code=code, status_code=403, context=context or {})


class BusinessRuleAppError(AppError):
    def __init__(self, message: str, code: str = "business_rule", context: Mapping[str, Any] | None = None):
        super().__init__(message=message, code=code, status_code=409, context=context or {})


class OperationAppError(AppError):
    def __init__(self, message: str, code: str = "operation_error", context: Mapping[str, Any] | None = None):
        super().__init__(message=message, code=code, status_code=422, context=context or {})


class SystemAppError(AppError):
    def __init__(self, message: str = "Error técnico controlado.", code: str = "system_error", context: Mapping[str, Any] | None = None):
        super().__init__(message=message, code=code, status_code=500, context=context or {}, safe_for_user=False)


def render_app_error_html(exc: AppError, request_id: str = "") -> str:
    title = "No se pudo completar la operación"
    msg = exc.message if exc.safe_for_user else "La aplicación registró un error técnico controlado. Reintentá la operación o avisá a soporte."
    return f"""<!doctype html>
<html lang='es'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width,initial-scale=1'>
  <title>Fjord VI · Operación controlada</title>
  <style>
    body{{font-family:Arial,sans-serif;background:#eef5f9;color:#102033;padding:24px}}
    .box{{max-width:560px;margin:auto;background:#fff;border-radius:20px;padding:24px;box-shadow:0 12px 30px rgba(0,0,0,.12)}}
    .code{{display:inline-block;margin-top:10px;background:#eef6fb;color:#355;padding:8px 12px;border-radius:999px;font-weight:700}}
    a{{display:inline-block;margin-top:14px;background:#0b5f8f;color:#fff;padding:10px 16px;border-radius:999px;text-decoration:none;font-weight:700}}
  </style>
</head>
<body>
  <div class='box'>
    <h1>{escape(title)}</h1>
    <p>{escape(msg)}</p>
    <div class='code'>Código: {escape(exc.code)} · Ref: {escape(request_id or '-')}</div>
    <p><a href='/'>Volver al inicio</a></p>
  </div>
</body>
</html>"""


ERROR_BOUNDARY_PHASE = "Fase 15 · errores tipados y centralizados"
