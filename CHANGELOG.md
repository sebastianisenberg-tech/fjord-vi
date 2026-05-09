# Changelog

## 1.8.2 - Blindaje base etapa 1
- Unificación de versión visible, metadata y health check.
- Corrección de índices de notification_queue.
- Protección CSRF automática en formularios POST estándar.
- Cookie de sesión con secure=True en producción.
- Bloqueo progresivo de login luego de intentos fallidos repetidos.
- Registro durable de intentos de login en base SQL.

## 1.7.6

- Safe User Delete.
- Agrega botón Borrar en Admin / Usuarios.
- Solo elimina físicamente usuarios sin historial operativo.
- Bloquea borrado si tiene reservas, responsable de invitados, autorizaciones protocolares o actividad.
- Si no se puede borrar, lo deja inactivo y registra el intento.
- Protege al usuario actual y al admin principal.
- Doble confirmación: escribir BORRAR + confirmación final.
- No cambia reglas de reservas, cupos, cargos, QR ni cierres.


## 1.8.0 - Reset de claves visible en Usuarios
- Botón individual visible: “Resetear clave”.
- La clave vuelve a `demo1234` y queda activado el cambio obligatorio al primer ingreso.
- Bloque superior de claves en Usuarios / Padrón Pro.
- Reset masivo excepcional para usuarios activos, protegido con frase exacta.
- Columna Acciones ampliada para evitar que el botón quede escondido.
