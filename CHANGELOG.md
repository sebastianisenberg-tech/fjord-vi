# v26.9.3 Puerta institucional YCA/Fjord VI

- Login institucional con Yacht Club Argentino, FJORD VI y Sistema de Reservas.
- Eliminados accesos demo visibles y credenciales de prueba de la pantalla pública.
- Logo YCA incorporado al mismo nivel del ZIP como logo_yca.jpg.
- Contacto Oficina de Vela: +54 11 4314-0505.

# v26.9.3 Lista de espera con prioridad de socios

- Socios desplazan invitados/menores activos antes del corte de 48h si el cupo está completo.
- Después del corte de 48h, la tripulación activa queda congelada; ante una vacante real se promueve la lista de espera por orden cronológico.
- Las personas en lista de espera no generan cargos mientras no entren al cupo.
- Si una persona promovida desde lista de espera luego cancela tarde o no embarca, aplica el cargo reglamentario según categoría.
- Se permite salir de lista de espera sin cargo.
- Refuerza mensajes y reglas visibles para socios.

## v26.8.2 release candidate revisada
- Versión visible: v26.8.2.
- Procfile y start.sh corregidos para apuntar a `main:app`.
- La salida seleccionada por defecto prioriza salidas operables y no canceladas.
- Mensajes de cancelación homogeneizados: sin cargos ni preliquidaciones vigentes.

# Changelog

## v26.8.2 socio premium + admin desktop
- Rediseña la pantalla de socios con jerarquía premium, menor ruido visual y acciones más claras.
- Reestructura Administración para uso desktop con panel lateral, KPIs, tabla de tripulación y bloques de operación/sistema.
- Mantiene intacta la lógica contable validada: preliquidación, cancelación por capitán, reapertura y cierre firme.
- Unifica branding: YCA · Fjord VI · Operativo de Embarque.
- Versión visible: v26.8.0 · build puerta-institucional-yca.

## v26.8.0 revisión fina de producción
- Actualiza versión visible a v26.8.0.
- Corrige README que todavía mostraba v26.6.
- Actualiza nombre del servicio Render a v26.8.0.
- Mantiene lógica contable y estructura de base sin cambios.

## v26.8.0 UX premium YCA revisada
- Corrige configuración de tarifa invitado en render.yaml, docker-compose y README a 45000.
- Actualiza nombre del servicio Render a v26.8.0.
- Unifica versión visible y título interno.
- Mantiene la base de datos existente sin cambiar el nombre del archivo SQLite para no perder datos.

# v26.6 legacy previo

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

## Legacy deploy ready

Mejoras principales sobre V16:

- Pantallas más pulidas y menos técnicas.
- Navegación inferior con anclas internas reales.
- Timeline visual de reserva, corte 48h, cancelación y embarque.
- Mejor lectura de estados para socio, capitán y administración.
- Barra de progreso de ocupación y presentes.
- Panel admin con herramientas demo y tarjetas de control.
- Reinicio de datos demo desde administración.
- CSV de versiones previas.
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

## v26.8.2 release candidate con lista de espera y cierre seguro
- Botón Reactivar visible solo cuando corresponde.
- Confirmación antes de cerrar embarque/liquidar y antes de cancelar por capitán.
- Protección anti doble click en formularios de capitán.
- Padding inferior reforzado para que la barra inferior no tape contenido.
- Lista de espera automática: cuando no hay cupo, socios/invitados quedan en espera; al liberarse una vacante se promueve automáticamente según prioridad auditable.


## v26.9.8
- Feedback visible cuando se bloquea un DNI duplicado o un socio cargado como invitado.
- Refuerzo de cupo: el backend baja excedentes no presentes a lista de espera para impedir activos > 9.
- Administración más clara: salida seleccionada, activos embarcables, pendientes activos, registros totales y lista de espera.
- Cierre de capitán devuelve mensajes de pantalla, no errores técnicos, si falta mínimo o se supera máximo.

## v27.0.0 - Administración de oficina
- Rediseño del panel de administración como pantalla de oficina: selector de salida, resumen operativo, liquidación, tabla administrativa y agenda.
- Separación visual entre planificación mensual, revisión posterior a la navegación, liquidación y herramientas del sistema.
- Métricas más explícitas: reservas totales, activos embarcables, embarcados, no embarcados, lista de espera y cargos firmes.

## v27.1.0 - Estable fin de semana
- Alcance cerrado a paseos de sábado y domingo.
- Refinamiento visual de Administración para uso de oficina en PC.
- Refinamiento de lectura móvil para Socio y Capitán.
- Se conserva la lógica existente: máximo 9 tripulantes, mínimo 2, invitados condicionales hasta 48h, invitado dependiente del socio, cargos 70%/100% y cierre del capitán como liquidación firme.
- No incorpora regatas, cruceros ni automatizaciones nuevas.

## v27.2.0 ADMIN PC PULIDO
- Ajuste visual exclusivo para Administración en PC.
- Más densidad de información: menos padding, filas y tarjetas más compactas.
- Tablas con encabezados más firmes, mejor contraste y alineación de importes.
- Formularios de Programar y Usuarios optimizados en una línea cuando hay ancho de escritorio.
- Sin cambios de lógica, reservas, penalizaciones, backup, socio ni capitán.

## v27.3.0 HEADER CORREGIDO
- Aumenta la jerarquía visual de la salida seleccionada en ADMIN.
- Cambia el bloque superior a fondo oscuro con texto blanco de alto contraste.
- Convierte el estado de navegación en badge fuerte y legible.
- No modifica lógica, reglas, datos, usuarios, reservas ni liquidación.

## v27.4.0 ADMIN HEADER MOBILE FIX
- Corrige el cartel de estado en Administración móvil.
- Evita desborde horizontal del badge de estado.
- Usa estado verde con texto blanco, consistente con Socio y Capitán.
- No modifica lógica, reservas, cargos ni navegación.

## v27.6.0 - Admin status force fix
- Fuerza el cartel de Estado navegación en Administración con estilos inline para evitar que la vista de escritorio lo deje azul/chico.
- Mantiene cartel verde con texto blanco en PC y celular.
- No modifica lógica, reservas ni cargos.

## v27.7.0 - Admin Salir visible fix
- Corrección visual puntual en Administración: botón “Salir” del header en blanco, más grande y visible.
- No modifica lógica, reservas, cargos ni reglas.
