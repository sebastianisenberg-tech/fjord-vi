# v66.6.1 - Production Ready Audit Fix

- Revisión completa de cierre técnico.
- Desactivadas rutas heredadas `/admin/restore`, `/admin/import_data` y `/admin/demo_reset`.
- PostgreSQL queda como única fuente de verdad operativa.
- JSON queda solo como exportación manual/backup previo a reset.
- Se mantiene Backup PostgreSQL, Reset Producción protegido y consola Sistema.
