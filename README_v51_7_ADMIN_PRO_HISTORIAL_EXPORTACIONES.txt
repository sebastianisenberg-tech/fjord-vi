FJORD VI v51.7 ADMIN PRO - HISTORIAL Y EXPORTACIONES

Base: v51.6.2

Objetivo:
- Transformar Administración en consola operativa de escritorio.
- Permitir ver planillas completas, operar tablas anchas, consultar historial y descargar datos.

Cambios funcionales en Administración:
- Nueva sección Historial en el menú lateral.
- Historial completo de reservas de todas las salidas visible desde Admin.
- Tabla maestra con scroll horizontal, encabezados fijos y columnas completas.
- Exportaciones CSV nuevas:
  - /admin/reservations_all.csv: historial completo de reservas.
  - /admin/outings.csv: salidas completas.
  - /admin/users.csv: usuarios/socios/capitanes/admins.
  - /admin/audit.csv: auditoría completa.
- Página Exportar ampliada con accesos a:
  - CSV salida seleccionada.
  - CSV historial completo.
  - CSV cargos por salida o todos.
  - CSV salidas.
  - CSV usuarios.
  - CSV auditoría.
  - Backup JSON.
- Auditoría visible ampliada a 1000 registros.
- Navegaciones ahora exporta CSV y muestra más columnas operativas.
- Reservas de salida seleccionada muestran responsable, fecha de reserva y cancelación.
- Filtros básicos en Reservas e Historial.

Cambios de layout Admin:
- Tablas con min-width y overflow horizontal real.
- Columnas largas con wrap controlado.
- Botonera de exportación operativa.
- Ajuste desktop para que las planillas no queden comprimidas.

No tocado:
- Socio.
- Capitán.
- Lógica de reservas.
- Lógica de cargos.
- Reglamento.
- Login.

Validación estática:
- main.py compila.
- Templates Jinja parsean.
- Rutas nuevas agregadas sin modificar las existentes.
