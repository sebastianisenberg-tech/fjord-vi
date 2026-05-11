# Fjord VI 1.10.3 - Fase 11D Sistema directo

Corrección específica de navegación móvil hacia Sistema.

Cambios:
- Todos los accesos a Sistema usan /admin/sistema como ruta directa.
- Se elimina el intercept JS data-force-system para evitar que touchend/click se anulen en Android.
- La tarjeta Sistema usa formulario GET directo además de link.
- Se agrega acceso Sistema en el bloque superior de Inicio.
- No modifica reservas, invitados, cargos ni cierres.
