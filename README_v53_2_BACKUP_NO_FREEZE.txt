FJORD VI v53.2 - Backup seguro sin congelar Admin

Cambios:
- /admin/backup ahora genera el JSON en memoria y lo descarga como adjunto.
- Evita escritura previa en disco durante la descarga.
- Agrega Cache-Control: no-store.
- En Admin, los enlaces de backup abren descarga en pestaña nueva / modo descarga para no bloquear la consola.
- Versión y cache actualizadas a v53.2.

No toca:
- Socio
- Capitán
- lógica de reservas
- lógica de cargos
- estructura de Admin ERP
