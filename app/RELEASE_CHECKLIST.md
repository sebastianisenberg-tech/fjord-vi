# Fjord VI · Checklist fija de release/deploy

Antes de pasar una versión beta a producción debe verificarse:

1. `/` redirige a una pantalla humana (`/login` o home según sesión), sin JSON ni Method Not Allowed visible.
2. `/login` abre correctamente.
3. Login, logout, reset de clave y cambio obligatorio de clave funcionan.
4. Sesiones viejas se invalidan cuando cambia o se resetea la clave.
5. UX móvil vertical y horizontal no muestra pantallas blancas ni elementos críticos ocultos.
6. Toasts y alertas son visibles y legibles.
7. PostgreSQL conecta y es la fuente única de verdad.
8. `/health` devuelve `ok=true` y versión correcta.
9. Esquema, integridad e índices están en OK desde Sistema.
10. Links internos principales funcionan y no exponen rutas técnicas al usuario final.
11. Backup PostgreSQL disponible antes de importaciones o cambios masivos.

La versión 1.8.5 agrega este control dentro de Sistema como “Checklist de release”.
