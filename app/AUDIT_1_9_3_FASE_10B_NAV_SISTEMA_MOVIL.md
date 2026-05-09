# Fjord VI 1.9.3 - Fase 10B Navegación Sistema móvil

Correcciones:
- Sistema y Comunicaciones ahora tienen rutas directas HTML: /admin/sistema, /admin/system, /admin/comunicaciones, /admin/communications.
- La barra superior usa rutas directas en vez de depender sólo de query params.
- Inicio agrega tarjeta directa a Sistema para móvil/tablet.
- Se conserva /admin?page=sistema como compatibilidad.
- No cambia reservas, cargos, invitados ni cierres.

Checklist:
- Root/login sin página técnica.
- Sistema accesible desde tab, desde /admin/sistema y desde tarjeta de Inicio.
- Comunicaciones accesible desde tab y /admin/comunicaciones.
