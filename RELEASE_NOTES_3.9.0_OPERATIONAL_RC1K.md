# Fjord VI 3.9.0-OPERATIONAL-RC1K

## Objetivo
Fortalecer comunicaciones operativas sin enlentecer Socio ni Capitán.

## Cambio único
- Consolidado garantizado de emails operativos por socio + salida.
- Los cambios sucesivos actualizan una única fila `pending` vigente en `notification_queue`.
- No se cancela un email operativo pendiente sin dejar reemplazo vivo.
- Ventana normal: hasta 10 minutos desde el último cambio.
- Límite absoluto: máximo 15 minutos desde el primer cambio del bloque operativo.

## No se tocó
- Motor de reservas.
- Capitán.
- Socio UI.
- Cierres.
- Liquidaciones.
- PDFs.
- Lógica reglamentaria.
- SMTP dentro de endpoints operativos.

## Validación local
- `python3 -m py_compile main.py`: OK.
- `pytest -q`: 40/40 OK.
