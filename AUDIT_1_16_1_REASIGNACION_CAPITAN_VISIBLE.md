# Auditoría 1.16.5

Corrección puntual:
- Se restaura la reasignación visible de invitados en la pantalla de Capitán.
- La función ya existía en backend (`/captain/reassign/{rid}`), pero quedaba demasiado escondida dentro del menú de tres puntos.
- Ahora cada invitado/menor con socio responsable muestra un bloque desplegable visible: `Reasignar invitado`.
- El Capitán puede elegir un socio presente sin volver a cargar el invitado ni duplicarlo.
- Se mantiene la opción dentro del menú de tres puntos.

No toca:
- QR
- cierre
- cancelación
- cargos
- ficha
- reglas de backend
