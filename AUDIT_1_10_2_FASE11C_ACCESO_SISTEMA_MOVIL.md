# Fjord VI 1.10.2 - Fase 11C Acceso Sistema móvil

Corrección específica sobre 1.10.1.

## Objetivo
Evitar que en Android/Samsung horizontal el tab Sistema quede visualmente activo pero no cargue la consola Sistema.

## Cambios
- Versión 1.10.2.
- Links de Sistema cambiados a ruta canónica `/admin?page=sistema`.
- Botón directo Sistema agregado en barra superior de administración.
- Script de guardia `data-force-system` para forzar navegación por `window.location.assign`.
- Botones internos "Abrir Sistema", "Ver estado operativo" y "Volver a Sistema" usan la ruta canónica.
- Corrección menor de enlace `Ver reservas` en Inicio.

## No modifica
- Reglas de reservas.
- Invitados.
- Cargos.
- Cierres.
- Base PostgreSQL.
