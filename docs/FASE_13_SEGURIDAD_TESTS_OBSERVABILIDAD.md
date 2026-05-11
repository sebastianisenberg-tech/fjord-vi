# Fjord VI 1.12.0 · Fase 13 Seguridad, tests y observabilidad

Objetivo: fortalecer el sistema sin tocar reglas de reservas, invitados, cargos ni cierres.

## Incluye

- Versión unificada 1.12.0.
- Middleware de observabilidad liviana: `X-Fjord-Request-ID`, `X-Fjord-Version`, `X-Fjord-Response-Time-Ms`.
- Cache-Control `no-store` en zonas autenticadas sensibles.
- Endpoints técnicos seguros para administración:
  - `/admin/security_status.json`
  - `/admin/observability.json`
- Nuevas fronteras de código:
  - `app/core/observability.py`
  - `app/core/validators.py`
- Tests de documentación/estructura para evitar deploy incompleto.
- Checklist profesional ampliada.

## No modifica

- Reservas.
- Invitados.
- Cargos.
- Cierre capitán.
- Liquidaciones.

## Próximo paso recomendado

Fase 14: tests automáticos reales de flujo: login, socio, invitado, capitán, cierre y admin.
