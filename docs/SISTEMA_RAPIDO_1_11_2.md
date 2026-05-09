# Sistema rápido 1.11.2

La pantalla `/admin/sistema` carga primero una vista liviana para evitar esperas largas en móvil y PC.

## Modo normal
`/admin/sistema`

Muestra versión, base de datos, semáforo liviano, estado operativo básico, actividad y alertas principales.

## Modo completo
`/admin/sistema?full=1`

Ejecuta los checks pesados: integridad, índices, backups, release completo y diagnósticos profundos.

## Cache
`SYSTEM_FAST_CACHE_SECONDS=45` por defecto.
