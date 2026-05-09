# Fjord VI 1.8.2 - Blindaje base etapa 1

Intervención de bajo riesgo, sin alterar reglas de negocio ni flujos visibles principales.

## Cambios aplicados

1. Versionado
- APP_VERSION, APP_BUILD y RELEASE_LABEL unificados en 1.8.2.
- VERSION.txt actualizado a 1.8.2.
- software_metadata.json actualizado a 1.8.2.
- CHANGELOG.md actualizado.

2. Índices SQL
- Corregidos índices mal apuntados a `email_queue`.
- Ahora apuntan a `notification_queue`.
- Agregados índices para `notification_log` y `login_attempts`.

3. Seguridad de sesión
- Cookie de sesión centralizada en `set_session_cookie()`.
- En producción (`APP_ENV=production` o `prod`) la cookie se emite con `secure=True`.
- Limpieza de cookie centralizada en `clear_session_cookie()`.

4. CSRF
- Agregada protección CSRF por token firmado para formularios POST estándar.
- El token se inyecta automáticamente en formularios HTML renderizados.
- Se excluyen uploads multipart/importaciones en esta etapa para no romper el flujo de padrón.

5. Intentos fallidos de login
- Nueva tabla `login_attempts`.
- Registro durable de intentos exitosos y fallidos.
- Bloqueo progresivo configurable luego de 20 intentos fallidos dentro de 30 minutos.
- Variables configurables:
  - LOGIN_LOCK_ATTEMPTS
  - LOGIN_LOCK_WINDOW_MINUTES
  - LOGIN_LOCK_MINUTES

6. Login
- Mensaje específico para bloqueo por intentos fallidos.
- Se mantiene la lógica existente de prioridad por Nº de socio frente a DNI.

## Pruebas realizadas

- Compilación Python: `python3 -m py_compile main.py`.
- Importación de la app con SQLite temporal.
- GET `/` devuelve login con token CSRF inyectado.
- POST `/login` con token válido responde 303.
- POST `/login` sin token responde 403.
- GET `/health` devuelve versión 1.8.2.
- Verificación de índices requeridos sin referencias a `email_queue`.

## Alcance no incluido

- No se implementó Alembic.
- No se reestructuró `main.py` en módulos.
- No se modificó la lógica de reservas/cupos/cierres.
- No se implementó locking transaccional de concurrencia.
- No se alteró el diseño visual general.
