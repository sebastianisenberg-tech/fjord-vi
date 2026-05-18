# Fjord VI RC9_OPERATIONAL_CORE_FAST

Objetivo de esta versión: estabilizar el flujo completo Socio -> Capitán sin volver a mezclar arreglos parciales.

Cambios relevantes:

1. Capitán no bloquea una acción de embarque por pantalla vieja. Usa el estado real actual de base y audita la diferencia.
2. Las acciones de Capitán `/captain/attendance/...` salen del lock global por salida. El doble toque queda controlado por idempotencia y estado real, no por un lock que podía dejar la pantalla trabada.
3. El procesamiento SMTP queda diferido en asistencia/reasignación. El POST operativo no espera envío de mails.
4. Se mantiene el cierre de Capitán intacto respecto de la versión base: `/captain/close` sigue protegido.
5. Socio mantiene altas/bajas rápidas con submit normal y sin envío SMTP sincrónico.
6. La UI de Capitán re-habilita botones después de 8 segundos si el navegador queda esperando, para evitar bloqueo visual permanente.

Validación automática:

- `python -m py_compile main.py`: OK
- `pytest -q`: 40/40 OK

Prueba manual obligatoria antes de producción:

1. Socio: agregar titular.
2. Socio: agregar 3 invitados.
3. Socio: eliminar 1 invitado.
4. Socio: cancelar titular.
5. Socio: reincorporar titular.
6. Capitán: marcar titular presente.
7. Capitán: marcar invitados presentes.
8. Capitán: marcar un invitado ausente.
9. Capitán: cerrar y generar ficha.
10. Ver ficha y volver a Capitán/Admin.


## RC9_OPERATIONAL_CORE_FAST_LOCKFREE
- Socio y Capitán quedan fuera del procesamiento SMTP automático.
- El middleware ya no procesa cola de emails en rutas operativas.
- Los formularios operativos usan submit nativo; AJAX/fetch queda sólo opt-in.
- Cierre, asistencia y cancelación de salida encolan comunicaciones sin enviarlas dentro del POST.
