# Fjord VI v58.0 - Usuarios / Padrón operativo

Cambios enfocados solo en el módulo Usuarios de Administración:

- Rediseño de tabla de usuarios para aprovechar mejor el ancho en escritorio.
- Botones de acciones corregidos: Editar, Reset, Desactivar/Activar ya no se cortan.
- Editar abre panel lateral funcional, no desplegable incompleto.
- Edición completa de usuario: nombre, documento, fecha de nacimiento, Nº socio, email, teléfono, rol y estado.
- Fecha de nacimiento incorporada al padrón para identificar menores.
- Edad calculada automáticamente en la grilla según fecha actual.
- Alta de usuario incluye fecha de nacimiento.
- CSV de usuarios incluye fecha de nacimiento y edad calculada.
- El sistema mantiene la regla de no eliminar personas: se desactivan para preservar historial, fichas y auditoría.
- Migración liviana: agrega users.birth_date si falta, sin borrar datos.

No se modificó la lógica de fichas, cierre, socio ni capitán.
