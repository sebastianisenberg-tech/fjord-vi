# Auditoría 1.16.8

Corrección puntual:
- `/admin/diagnostic.zip` ahora genera un ZIP robusto.
- Si falla un subcontrol interno, el ZIP igual descarga y deja el error en `09_ERRORES.txt`.
- Se evita explícitamente la descarga de 0 bytes.
- `log_activity` queda protegido para que nunca rompa la descarga.
- El nombre del archivo queda simple y estable: `fjord_vi_diagnostico_1.16.8.zip`.

No toca:
- Capitán
- reservas
- cargos
- cierres
- QR
- lógica de embarque
