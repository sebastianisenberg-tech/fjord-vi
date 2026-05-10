# Auditoría 1.15.3

Cambios:
- `Cargar checks completos` ahora da feedback visual:
  - cambia a "Cargando checks..."
  - al abrir la vista completa muestra cartel "Checks completos cargados".
- Se agrega explicación visible de qué hace el botón.
- `Descargar diagnóstico ZIP` ahora apunta a `/admin/diagnostic.zip`.
- Nuevo endpoint `/admin/diagnostic.zip` con paquete técnico real:
  - README
  - diagnóstico TXT
  - release check JSON
  - estado operativo JSON
  - arquitectura JSON
  - contexto de sistema JSON
  - actividad reciente CSV
  - auditoría reciente CSV
  - metadata JSON
- Se mantiene `/admin/diagnostic.txt` como diagnóstico simple heredado.
- No modifica reservas, invitados, cargos, cierres ni Capitán.
