# 1.14.0 · Fase 15 · Arquitectura, errores y services

- Se agregan errores tipados centralizados.
- Se agrega logging base estructurable.
- Se agrega settings centralizado.
- Se agregan repositorios scaffold.
- Se agrega middleware scaffold.
- Se agrega servicio de operaciones.
- Se mantiene Sistema rápido.
- No se toca operación de reservas/cargos/cierres.

# Changelog

## 1.14.0 · Fase 14 Validaciones backend y tests reales

- Agrega validaciones de negocio puras en `app/core/business_rules.py`.
- Agrega tests automáticos iniciales para cupos, duplicados, roles, estados e invitado responsable.
- Mantiene UX y operatoria sin cambios.
- Prepara conexión gradual de reglas al backend crítico.


## 1.14.0 · Fase 13 Seguridad, tests y observabilidad

- Observabilidad liviana por request-id y tiempo de respuesta.
- Endpoints admin de seguridad y observabilidad.
- Cache no-store en áreas autenticadas.
- Fronteras nuevas para validadores y métricas.
- Documentación y plan de tests ampliados.
- No cambia reglas de reservas, invitados, cargos ni cierres.

# 1.11.3 - Fase 12C Sistema rápido real y versión unificada

- Unifica numeración visible/runtime en 1.11.3.
- Hace que Sistema cargue liviano por defecto.
- Oculta/renderiza diferido los checks pesados hasta `?full=1`.
- Reduce consultas iniciales de actividad/comunicaciones/arquitectura.
- No toca reservas, invitados, cargos ni cierres.

# 1.11.3 - Fase 12C Sistema rápido real y versión unificada

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
