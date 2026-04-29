# Changelog

## v26.6.1 UX premium YCA revisada
- Corrige configuración de tarifa invitado en render.yaml, docker-compose y README a 45000.
- Actualiza nombre del servicio Render a v26.6.1.
- Unifica versión visible y título interno.
- Mantiene la base de datos existente sin cambiar el nombre del archivo SQLite para no perder datos.

# v26.6-ux-premium-yca

- Bloquea acciones de socio e invitados cuando la salida está cancelada por capitán.
- Oculta formularios operativos en salida cancelada hasta reapertura.
- Limpia textos repetidos en tripulación durante cancelación por capitán.
- Cambia tarjetas canceladas a tratamiento visual neutro/premium.
- Mantiene lógica contable validada: cancelación capitán $0, reapertura recalculada, cierre con cargos firmes.

## v26.6 UX profesional YCA

- Unificación de versión visible en app: YCA · Fjord VI · Operativo de Embarque · v26.6.
- Título interno FastAPI actualizado.
- Bloqueo de edición por socio en salidas canceladas por capitán hasta reapertura operativa.
- Mensajes de cancelación homogeneizados: sin cargos ni preliquidaciones vigentes.
- Revisión de compatibilidad de templates y rutas.

## v26.4.2 UX semántica
- Cambia la etiqueta visible de “Cancelado por capitán” a “No embarcado por capitán” para evitar confundirlo con baja del socio.
- Distingue visualmente “No embarca por capitán” en gris/neutral y “Ausente” en rojo con cargo.
- Refuerza “Salida cerrada y liquidada” en los mensajes de estado.
- Cargo firme se muestra en verde; preliquidación estimada conserva color naranja.

# V26.1 - Contabilidad cerrada revisada

- Separa cargo firme de preliquidación/proyección.
- Antes del cierre del capitán no hay deuda firme.
- Si la salida es cancelada por capitán, todos los cargos y proyecciones quedan en $0.
- Cancelado por capitán individual queda sin cargo y no ocupa cupo.
- Manifest CSV agrega cargo estimado además de cargo firme.
- Pantallas muestran “Preliquidación” cuando corresponde y aclaran que no es firme hasta cierre.

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


## v26.5 - UX profesional + branding YCA
- Unifica versionado con `VERSION`, `CLUB_NAME`, `APP_NAME` y `APP_MODEL`.
- Agrega footer discreto con YCA, Fjord VI, modelo operativo y versión.
- Limpia pantallas de capitán y socio para reducir repetición y mejorar lectura operativa.
- Reemplaza banners rojos invasivos por estados globales profesionales.
- Mantiene lógica contable validada: preliquidación, cargo firme, cancelación capitán y reapertura.
