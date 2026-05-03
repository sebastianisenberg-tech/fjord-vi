FJORD VI v53.4 - ADMIN DETALLE DE SALIDA REAL

Base: v53.3.1 BASE TESTEO DURO.

Cambios implementados:
- Nueva página Admin -> Detalle salida, accesible desde Salidas con botón Ver detalle.
- Detalle por viaje con bloques: embarcaron, lista de espera ordenada, confirmados pendientes, ausentes, no embarca/no embarcados, cancelados, cargos firmes y auditoría vinculada.
- KPIs de la salida: estado, cupo activo, embarcaron, espera y cargos.
- Acciones de salida en detalle: cerrar, reabrir, cancelar, exportar detalle CSV y exportar cargos.
- Usuarios: edición ampliada de todos los campos visibles: nombre, documento, número de socio, email, teléfono, rol de acceso y condición institucional.
- Nueva condición institucional de usuario: socio / no socio / baja lógica.
- Baja lógica deja usuario inactivo sin borrar historial.
- CSV de usuarios incluye condición institucional.
- Se mantiene backup seguro no bloqueante de v53.2 y densidad ERP de v53.3.

No se tocó:
- Socio.
- Capitán.
- Reglamento.
- Motor central de reservas/cupos/lista de espera, salvo lectura/agrupación administrativa.

Validación realizada:
- main.py compila.
- Templates principales cargan.
- /admin, /admin?page=navegaciones, /admin?page=socios, /admin?page=detalle abren con TestClient.
- /admin/users.csv, /admin/outings.csv y /admin/backup responden.
