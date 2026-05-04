# Fjord VI v66.4 HARDENING

## Cambios técnicos
- Consola Sistema endurecida para soporte/preproducción.
- Versión actualizada a v66.4 y build `v66-hardening-system-console`.
- PostgreSQL sigue seleccionado por `DATABASE_URL`; SQLite queda solo como fallback local.
- Host de DB oculto en consola para no exponer infraestructura.
- Health incluye `hardening` y disponibilidad de `pg_dump`.

## Backups
- Dockerfile mantiene `postgresql-client` para disponer de `pg_dump` en Render.
- Backup PostgreSQL descarga `.sql` real cuando `pg_dump` está disponible.
- JSON se conserva como backup auxiliar, no como fuente principal.

## Integridad
- Nuevos controles:
  - fichas vigentes duplicadas;
  - payload inválido en fichas;
  - salidas cerradas sin ficha vigente.
- Botón seguro para reparar salidas cerradas sin ficha vigente.
- La reparación valida cupo y socio responsable presente antes de generar ficha.

## No tocado
- Socio.
- Capitán.
- Liquidación.
- Fichas existentes.
- Reglas de cargos.
