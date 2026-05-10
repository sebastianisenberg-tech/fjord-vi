# 1.16.8

- Capitán: se elimina visualmente "Clave" del header azul.
- Capitán: queda solo "🔑 Cambio de clave" en tarjeta compacta.
- Protocolar: se limpia doble rotulación.
- Badges vacíos: se ocultan o caen a "Pendiente".
- Versión unificada en el paquete.

# 1.16.8

- Reformas operativas visibles.
- Capitán: métricas más claras: A bordo, Ocupación y Reservas procesadas.
- Protocolar: badge único, sin duplicación como invitado.
- Ficha: resumen superior y grupos por socio más legibles.
- Reasignación: se explicita socio original no embarcado.
- Sin cambios en lógica de cargos, QR, cierre ni reasignación.

# 1.16.8

- Socio: cupos claros, sin ambigüedad entre ocupados y libres.
- Socio: cambio de clave compacto con pastilla "🔑 Clave".
- Capitán: cada invitado común muestra a qué socio pertenece.
- Protocolar: textos visuales más limpios, sin repetir "sin cargo".
- Sin cambios en QR, cierre, cargos normales ni reasignación.

# 1.16.8

- Capitán ahora ve claramente a qué socio pertenece cada invitado común.
- Muestra socio responsable, Nº de socio y estado de presencia.
- Protocolares quedan separados como independientes.
- Sin cambios en cargos, cierre, QR ni ficha.

# 1.16.8

- Regla protocolar corregida:
  - Protocolar puede embarcar aunque no esté quien lo cargó.
  - Protocolar no requiere reasignación.
  - Protocolar siempre sin cargo, antes/después de 48 h, presente/ausente/no confirmado.
  - Cierre y preflight ya no bloquean protocolares por socio responsable ausente.
- Capitán muestra al protocolar como independiente y sin cargo.
- Sin cambios en QR, cierre general, invitados normales ni cargos normales.

# 1.16.8

- Restauración visible de reasignación de invitados en Capitán.
- Mantiene el backend existente `/captain/reassign/{rid}`.
- Agrega bloque desplegable visible `Reasignar invitado` en cada invitado/menor con responsable.
- Sin cambios en QR, cierre, cancelación, cargos ni fichas.

# 1.16.8

- Performance operativa.
- Anti doble toque global.
- Feedback inmediato en acciones críticas.
- Descargas técnicas no bloqueadas.
- Política explícita Socio/Capitán livianos.
- Checks y diagnósticos bajo demanda.
- Sin cambios en Capitán, reservas, cargos ni cierres.

# 1.16.8

- Feedback visual para Cargar checks completos.
- Aclaración funcional del botón en Sistema.
- Diagnóstico ZIP real con TXT, JSON, CSV y metadata.
- Se mantiene diagnóstico TXT heredado.
- No modifica lógica de reservas, Capitán, cargos ni cierres.

# 1.16.8

- Rotulado claro de botones técnicos de Sistema.
- Health JSON identificado como salida técnica cruda.
- Release check identificado como TXT.
- Diagnóstico identificado como ZIP.
- Versión interna unificada.
- Sin cambios en reglas operativas.

# 1.16.8

- Versión visible unificada.
- Corrección de chips intermedios en Sistema.
- En modo rápido, los chips cargan la vista completa y abren la sección correcta.
- Mejor feedback para Contraer/Expandir cuando los controles están diferidos.
- No toca reglas operativas.


# 1.16.8

- observabilidad inicial profesional
- endpoints /health/live y /health/ready
- estructura inicial migraciones
- nuevos tests fase 16
- documentación observabilidad
- estrategia formal de testing
- preparación CI/CD futura


# 1.16.8 · Fase 15 · Arquitectura, errores y services

- Se agregan errores tipados centralizados.
- Se agrega logging base estructurable.
- Se agrega settings centralizado.
- Se agregan repositorios scaffold.
- Se agrega middleware scaffold.
- Se agrega servicio de operaciones.
- Se mantiene Sistema rápido.
- No se toca operación de reservas/cargos/cierres.

# Changelog

## 1.16.8 · Fase 14 Validaciones backend y tests reales

- Agrega validaciones de negocio puras en `app/core/business_rules.py`.
- Agrega tests automáticos iniciales para cupos, duplicados, roles, estados e invitado responsable.
- Mantiene UX y operatoria sin cambios.
- Prepara conexión gradual de reglas al backend crítico.


## 1.16.8 · Fase 13 Seguridad, tests y observabilidad

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
