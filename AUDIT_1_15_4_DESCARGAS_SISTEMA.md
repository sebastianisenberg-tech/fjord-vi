# Auditoría 1.15.5

Corrección puntual:
- `/admin/operational_status.txt` ahora es robusto y no debe caer a pantalla de error.
- `/admin/phase9.txt` ahora es robusto y no debe caer a pantalla de error.
- `/admin/architecture.txt` también queda robustecido por consistencia.
- Si algún subcontrol falla, el TXT se descarga igual e informa el error adentro.
- Los `log_activity` de estas descargas quedan protegidos con try/except.
- Botones renombrados a TXT para dejar claro qué descargan.

No toca:
- Capitán
- reservas
- cargos
- cierres
- QR
- lógica de embarque
