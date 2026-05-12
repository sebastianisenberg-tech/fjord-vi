# 1.18.16 - Versión unificada

- Alinea versión interna, app_build y release_label a 1.18.16.
- Alinea metadata y documentación de la copia app/.

# 1.18.6 - Release unificado

- Alinea versión interna, app_build y release_label a 1.18.6.
- Mantiene lógica operativa existente.

# 1.11.2 - Fase 12B Sistema rápido y seguridad base

- Arranque rápido de Sistema con cache corto.
- Checks pesados diferidos disponibles con `?full=1`.
- Headers básicos de seguridad.
- Mantiene CSRF, sesiones y lógica operativa existentes.
- No toca reservas, invitados, cargos ni cierres.

# 1.11.0 - Fase 12 Profesionalización interna

- Agrega documentación técnica en `docs/`.
- Agrega `.env.example`.
- Agrega `tests/test_smoke_static.py`.
- Agrega `scripts/smoke_check.py`.
- Prepara carpeta `migrations/`.
- Actualiza versión a 1.11.0.
- No modifica reglas operativas de reservas, invitados, cargos ni cierres.


## 1.8.9 · Fase 7 operaciones y alertas
- Semáforo operativo global.
- Alertas operativas y mantenimiento.
- Métricas técnicas y deploy history.
- Preparación multi-barco con boat_id.
- Sin cambios en reglas visibles de reservas/cargos.

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

## 1.8.7
- Fase 5: arquitectura modular controlada.
- Scaffold app/core, app/services, app/routers.
- Mapa de arquitectura en Sistema y endpoints admin/architecture.


## 1.8.8
- Fase 6: estado operativo y preproducción.
- Agrega semáforo ejecutivo en Sistema con score operativo.
- Verifica infraestructura, datos mínimos, roles, integridad, seguridad, locks y comunicaciones.
- Agrega endpoints admin/operational_status.json y admin/operational_status.txt.
- No cambia reglas visibles de reservas.

## 1.18.16
- Fix puntual de reasignación única en Capitán: no devuelve más OK falso en una segunda reasignación.
- Se oculta la opción de reasignar cuando el invitado ya fue reasignado una vez en esa salida.
- Versión unificada en código y metadatos.
