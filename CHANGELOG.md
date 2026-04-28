# Changelog

## V18 Deploy Ready

Mejoras principales sobre V16:

- Pantallas más pulidas y menos técnicas.
- Navegación inferior con anclas internas reales.
- Timeline visual de reserva, corte 48h, cancelación y embarque.
- Mejor lectura de estados para socio, capitán y administración.
- Barra de progreso de ocupación y presentes.
- Panel admin con herramientas demo y tarjetas de control.
- Reinicio de datos demo desde administración.
- CSV renombrados a V18.
- Base SQLite separada: `fjord_v18_pilot.db`.

Sigue siendo piloto. No reemplaza todavía validación institucional, padrón real, autenticación del Club, backups ni operación productiva.

## V24 operativo auditable
- Centraliza la lectura de reservas en `reservation_view()` dentro de `main.py`.
- Distingue visualmente estado físico y condición reglamentaria en Capitán, Admin y Socio.
- Agrega resumen de cargos por categoría: socios, invitados y menores no socios.
- Corrige la detección visual de salida cerrada usando `Embarque cerrado` como estado real.
- Mantiene la reapertura por capitán, con trazabilidad por auditoría.
- No cambia estructura de base de datos ni requiere migración.

## V25 consolidación operativa
- Agrega acta operativa en Admin con embarcados, no embarcados, pendientes y total de cargos.
- Agrega contadores de acta también en Capitán para lectura rápida durante la salida.
- Mejora el CSV de manifest con estado físico, condición reglamentaria, motivo visible y cargo efectivo.
- Mejora el CSV de cargos con motivo calculado desde la misma lógica central de `reservation_view()`.
- Corrige textos residuales: cancelado por capitán queda como no embarcado y sin cargo visible.
- Agranda y mejora el botón `Salir` en todas las pantallas.
- Agrega estilos visuales para acta, contadores, badges y lectura mobile.
- No cambia base de datos ni requiere migraciones.
