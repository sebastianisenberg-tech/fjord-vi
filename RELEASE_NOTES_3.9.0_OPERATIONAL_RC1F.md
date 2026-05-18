# Fjord VI 3.9.0 OPERATIONAL RC1F

## Cambio aplicado

Mejora menor de UX en alta de invitado tipo hijo menor de socio no socio.

- Se reemplaza la leyenda técnica `Validación contra fecha de salida.` por un texto más claro para el socio.
- Se agrega la etiqueta visible `Fecha de nacimiento del menor`.
- Se mantiene intacta la lógica reglamentaria y la validación de edad contra la fecha de navegación.

## Alcance

Cambio aislado en `templates/socio.html`.

No se modifica:

- motor de reservas;
- Capitán;
- cierres;
- liquidaciones;
- PDFs;
- SMTP;
- cola automática de emails;
- lógica reglamentaria.

## Rollback

Restaurar `templates/socio.html` desde RC1E o volver a desplegar `FjordVI_3.9.0_OPERATIONAL_RC1E_EMAIL_AUTOSCHEDULER.zip`.
