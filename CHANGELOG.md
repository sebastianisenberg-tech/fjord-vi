# FJORD VI v28.4.0

## Fix crítico de negocio: dependencia socio -> invitado

- Si el capitán marca a un socio titular como **No embarca**, todos sus invitados/menores vinculados pasan automáticamente a **No embarca**.
- Un invitado/menor no socio ya no puede quedar como **Presente/Embarcado** si su socio responsable no está presente.
- La cascada se aplica antes del cierre y antes de recalcular cargos.
- Los invitados bloqueados por ausencia/no embarque del socio responsable quedan sin cargo por embarque.
- Se mantiene la regla: el QR registra presencia, pero la autorización final corresponde al capitán.

## Conservado de v28.3

- Clasificación por padrón: si el DNI corresponde a usuario activo con rol socio, liquida como socio.
- QR de check-in desde Capitán.
- Reincorporación del socio titular.

## v29.7.0 - Cierre inteligente operativo
- El cierre ahora valida el mínimo contra tripulantes activos, no solo contra presentes marcados manualmente.
- Al cerrar, los activos pendientes se confirman automáticamente como presentes.
- Mantiene ventana de capitán de 48h, QR público, QR admin, liquidación y dependencia socio-invitado.
