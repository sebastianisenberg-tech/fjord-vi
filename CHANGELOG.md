# v28.5.0 - Premium Minimal UI Skin

- Rediseño premium mobile-first del login con foto hero del Fjord VI.
- Mantiene gallardete/logo existente del sistema.
- Ajuste global de paleta, sombras, bordes y botones para un lenguaje visual más sobrio.
- No modifica lógica de reservas, QR, cierre, cargos ni dependencia socio-invitado.

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
