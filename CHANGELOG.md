## 3.8.6 · Production Ready RC1

- Cola SMTP blindada con claim transaccional previo al envío (`processing_token`).
- Recovery post restart para emails interrumpidos en estado `processing`.
- Migración segura de columnas SMTP nuevas sin borrar datos.
- Release check actualizado a 3.8.6 y paquete sin basura técnica.
- Tests críticos agregados para idempotencia SMTP, recovery y guardas de ficha vigente/anulada.

## 3.8.5 · Release hardening

- Versión unificada 3.8.5.
- Política operativa de envíos formalizada: inmediatos, diferidos, reemplazables y definitivos.
- Cola SMTP con expiración de pendientes y retry máximo configurable.
- Recovery post restart cancela pendientes obsoletos y retries agotados.
- Release check actualizado para tests críticos 3.8.5.
- Pytest mínimo agregado para versión, waitlist, SMTP policy y release hardening.

## 3.8.4 · Release hardening

- Cierre de rutas técnicas públicas: /docs, /redoc y /openapi.json.
- Idempotencia SMTP con columna propia indexada `notification_queue.idempotency_key`.
- Migración liviana compatible para bases existentes.
- Acción excepcional “No embarca sin cargo” simplificada a una sola confirmación con motivo obligatorio.
- Limpieza de release: sin `__pycache__` ni artefactos compilados.

## 1.19

- Paquete limpio de producción basado en 1.18.18.
- Se conservaron la lógica operativa, reasignación persistente y documentación esencial.
- Se eliminaron archivos históricos sueltos, auditorías viejas, tests, scripts auxiliares y duplicados que no participan de la ejecución en Render.
- Se consolidó la historia técnica en `HISTORIAL_TECNICO.txt`.
- Versión unificada a `1.19` en metadata principal.

## 3.8.3 · Integridad transaccional
- Recompute centralizado de waitlist.
- Validación de estados imposibles.
- Idempotencia SMTP por clave operacional.
- Recuperación de cola económica obsoleta al iniciar.
- No embarca sin cargo protegido con motivo obligatorio.
