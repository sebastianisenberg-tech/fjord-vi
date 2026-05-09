# Auditoría 1.8.8 - Fase 6 Estado operativo y preproducción

## Objetivo
Agregar una capa de diagnóstico ejecutivo en Sistema para saber si la beta está lista para piloto controlado sin tocar reglas de negocio.

## Cambios
- Versión unificada 1.8.8.
- Nuevo semáforo Estado operativo / preproducción.
- Score operativo porcentual.
- Controles: DB, PostgreSQL, backup SQL, usuarios, salidas, reservas, roles, integridad, índices, seguridad, locks y comunicaciones.
- Endpoints protegidos por admin: `/admin/operational_status.json` y `/admin/operational_status.txt`.

## Riesgo
Bajo. Cambios de lectura/diagnóstico; no modifican reservas, salidas, usuarios ni cargos.

## Checklist obligatoria
- `/` redirige a login/home.
- `/health` OK.
- Sistema muestra 1.8.8.
- Release check apto o con advertencias conocidas.
- Estado operativo visible.
- PostgreSQL OK.
