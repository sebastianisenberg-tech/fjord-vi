# Fjord VI 3.9.0 OPERATIONAL RC1E

Actualización acotada al módulo Comunicaciones.

## Objetivo

Evitar que el envío de emails dependa de Administración durante la operación de fin de semana, sin volver a acoplar SMTP al flujo de Socio o Capitán.

## Cambios

- Procesador automático de cola SMTP en segundo plano.
- El worker corre después de responder al navegador, para no bloquear acciones de Socio/Capitán.
- Throttle configurable por `communications_auto_interval_seconds`, default 60 segundos.
- Límite chico por corrida, default 5 emails, respetando `smtp_send_limit_per_run`.
- Emails de cierre/liquidación diferidos por `smtp_closing_delay_minutes`, default 15 minutos.
- Si una salida se reabre o se genera nueva ficha, los emails económicos pendientes anteriores quedan obsoletos antes de enviarse.
- Recordatorios 24h siguen encolándose de forma conservadora.
- Se registran última corrida automática, disparador y resultado.

## No tocado

- Socio.
- Capitán.
- Cierre de salida.
- Fichas.
- Liquidaciones.
- PDF.
- Motor SMTP y credenciales.
- Templates de email.

## Validación

- `python -m py_compile main.py`: OK.
- `pytest -q`: 40/40 OK.
