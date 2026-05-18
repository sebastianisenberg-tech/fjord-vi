# Fjord VI 3.9.0-OPERATIONAL-RC1

Primera candidata operativa para pruebas controladas con socios.

## Criterio de esta versión

- Base funcional estabilizada a partir del flujo Socio + Capitán + cierre + ficha.
- Socio y Capitán deben responder rápido y no esperar SMTP.
- Emails quedan desacoplados en cola diferida.
- Acciones críticas del Capitán usan POST nativo directo.
- Se preserva cierre/liquidación/ficha como flujo consolidado.
- Versionado unificado en constante global, VERSION.txt y metadata.

## Qué probar manualmente

1. Login de socio.
2. Alta de titular.
3. Alta de varios invitados.
4. Baja individual de invitado.
5. Cancelación de titular y reincorporación.
6. Login de Capitán.
7. Marcar presente, no se presentó/con cargo y no embarca/sin cargo.
8. Reasignar invitado a socio presente.
9. Cerrar salida y generar ficha.
10. Ver PDF, CSV e historial.
11. Reabrir, corregir y recerrar.
12. Revisar cola de comunicaciones sin bloquear operación.

## Restricción

No es producción masiva. Es RC operativa para piloto controlado.
