# Fjord VI v3.7.6 · Hardening real

Esta release integra confiabilidad en el sistema visible y en backend, no solamente documentación.

## Cambios reales

- Versión activa 3.3 conectada a templates.
- Modo prueba SMTP visible y editable en Comunicaciones.
- Email receptor de pruebas editable desde Administración.
- Redirección forzada en modo prueba antes de enviar.
- Asunto de prueba con prefijo `[TEST Fjord VI]`.
- Cuerpo del email con destinatario original y destinatario efectivo.
- Guardia para no activar eventos si el modo prueba está incompleto.
- Deduplicación conservadora de emails recientes idénticos.
- Script `scripts/release_check.py`.
- Módulo de invariantes `app/reliability/state_machine.py`.

## Invariantes

- Ocupación nunca debe superar capacidad.
- Una sola ficha/liquidación vigente por salida.
- Reapertura debe versionar/anular con trazabilidad.
- SMTP Test Mode nunca debe enviar a socios reales.
- Eventos de email no deben duplicarse por doble click inmediato.
