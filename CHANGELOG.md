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
