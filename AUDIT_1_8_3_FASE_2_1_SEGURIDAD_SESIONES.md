# Fjord VI · v1.8.3 · Fase 2.1 Seguridad y sesiones

## Objetivo
Primer bloque de robustecimiento institucional sin modificar reglas de negocio ni pantallas principales.

## Cambios incluidos

1. Versionado de sesión
   - La cookie de sesión ahora incluye `user_id:session_version` firmados.
   - Si la versión de sesión en base cambia, la cookie anterior queda inválida.

2. Invalidación de sesiones al cambiar clave
   - Cambio inicial obligatorio de clave invalida sesiones anteriores.
   - Cambio voluntario desde perfil invalida sesiones anteriores.
   - Reset individual por administración invalida sesiones anteriores del usuario reseteado.
   - Reset masivo de claves invalida sesiones anteriores de todos los usuarios activos.

3. Nuevas columnas de seguridad en `users`
   - `session_version INTEGER DEFAULT 1`
   - `last_login_at TIMESTAMP`
   - `last_password_change_at TIMESTAMP`

4. Login hardening prudente
   - Se mantiene umbral alto por identidad para no castigar usuarios reales.
   - Se agrega umbral por IP para detectar automatismos distribuidos contra varios usuarios.
   - Variables configurables:
     - `LOGIN_LOCK_ATTEMPTS` default 20
     - `LOGIN_LOCK_WINDOW_MINUTES` default 30
     - `LOGIN_LOCK_IP_ATTEMPTS` default 80
     - `SESSION_MAX_AGE_SECONDS` default 43200

5. Auditoría operacional
   - Los cambios de clave dejan constancia de invalidación de sesiones anteriores.
   - `last_login_at` se actualiza en login correcto.

6. Health check ampliado
   - `/health` informa `session_versioning`, `login_ip_lock_threshold` y `session_max_age_seconds`.

## Alcance
No cambia la lógica de reservas, cupos, invitados, protocolares, cierres ni liquidaciones.

## Pruebas sugeridas
1. Entrar con admin.
2. Resetear clave de un usuario.
3. Verificar que ese usuario debe cambiar clave al ingresar.
4. Cambiar clave y verificar que entra correctamente.
5. Abrir sesión del mismo usuario en dos navegadores, cambiar clave en uno y verificar que la sesión anterior queda inválida.
6. Revisar `/health` y confirmar versión 1.8.3.
