# Fjord VI 1.11.3 - Fase 12C Sistema rápido real y versión unificada

Objetivo: elevar performance percibida y seguridad base sin tocar reglas operativas.

Incluye:
- Vista Sistema liviana por defecto.
- Cache corto configurable por `SYSTEM_FAST_CACHE_SECONDS` (default 45s).
- Botón `Cargar checks completos` para diagnóstico profundo.
- Headers HTTP básicos: X-Content-Type-Options, X-Frame-Options, Referrer-Policy, Permissions-Policy y HSTS en producción.
- Health expone banderas `phase12b_system_fast` y `security_headers_base`.

No modifica:
- Reservas.
- Invitados.
- Cargos.
- Cierres.
- Fichas de navegación.
