# Fjord VI 3.9.0-OPERATIONAL-RC1B

Corrección focalizada de comunicaciones sobre la base operativa RC1A.

## Alcance

- No modifica Socio.
- No modifica Capitán.
- No modifica cierre.
- No modifica fichas ni liquidaciones.
- No modifica autenticación SMTP ni cola.

## Cambios

- Limpieza de asuntos y cuerpos de emails en texto plano.
- Eliminación del texto técnico visible en modo prueba: evento interno, QA, destinatario original y redirección detallada.
- Saludos y textos diferenciados para socio y administración.
- Modo prueba mantiene una línea breve y clara indicando que el correo fue redirigido al receptor de pruebas.
- Plantillas base sincronizadas para corregir textos viejos al iniciar.
