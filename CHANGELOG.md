# Changelog

## 1.7.6

- Safe User Delete.
- Agrega botón Borrar en Admin / Usuarios.
- Solo elimina físicamente usuarios sin historial operativo.
- Bloquea borrado si tiene reservas, responsable de invitados, autorizaciones protocolares o actividad.
- Si no se puede borrar, lo deja inactivo y registra el intento.
- Protege al usuario actual y al admin principal.
- Doble confirmación: escribir BORRAR + confirmación final.
- No cambia reglas de reservas, cupos, cargos, QR ni cierres.
