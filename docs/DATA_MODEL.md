# Modelo de datos operativo

## Entidades principales

- `users`: padrón, socios, administradores y capitanes.
- `outings`: salidas/paseos programados.
- `reservations`: reservas de socios, invitados y estados operativos.
- `closing_sheets`: fichas de cierre y liquidación.
- `audit_logs`: acciones institucionalmente sensibles.
- `activity_log`: navegación técnica y uso del sistema.
- `notification_queue`: cola de comunicaciones.

## Principios

- No borrar usuarios con historial operativo; desactivar en lugar de eliminar.
- No romper trazabilidad de reservas históricas.
- Una salida debe mantener integridad de cupos, presentes, cancelados y cargos.
- Las fichas cerradas deben ser auditables y reemplazables solo con registro.
