# v66.3.1 SYSTEM CONSOLE AUDIT FIX

- Auditoría de compatibilidad del módulo Sistema.
- Dockerfile corregido para instalar `postgresql-client` y disponer de `pg_dump`.
- El backup PostgreSQL ya puede generar `.sql` real en Render cuando `DATABASE_URL` está activo.
- Mantiene fallback JSON si `pg_dump` fallara.
- Sin cambios en socio, capitán, liquidación ni fichas.

# v66.3 · SYSTEM CONSOLE + ACTIVITY

- Mejora de pestaña Sistema como consola técnica.
- Estado de aplicación, versión, hora servidor y URL pública.
- Estado de base de datos: PostgreSQL/SQLite, host y conexión.
- Conteos principales: usuarios, salidas, reservas, fichas y auditoría.
- Schema guard: revisión de tablas/columnas críticas y reparación segura.
- Backups: JSON y backup lógico PostgreSQL con fallback JSON si pg_dump no está disponible.
- Integridad: DNI duplicado por salida, cupos excedidos, invitados presentes con socio ausente, salidas cerradas sin ficha y socios sin Nº de socio.
- Actividad: activos últimos 5/30 minutos, activos del día, módulos usados y últimos movimientos.
- Diagnóstico técnico descargable.
- Comunicaciones queda previsto para v67, sin activar emails.

# FJORD VI v66.1 - ADMIN ERP CONTROLES AUDITADOS

- Se auditó el módulo Administración completo.
- Se corrigió la interacción de filas clickeables en Salidas / navegaciones.
- Botones Ver, Reservas, Cargos, Fichas, CSV, Exportaciones, Usuarios y Sistema verificados.
- Comunicaciones permanece previsto para v67, sin lógica activa de envío.

# FJORD VI v66 - ADMIN ERP LAYOUT

Cambios principales:

- Administración orientada a escritorio con criterio ERP.
- Inicio operativo con dos cargas principales: Salidas y Usuarios.
- Tarjeta prevista para Comunicaciones, sin activar emails todavía.
- Salidas / navegaciones con tabla activa: click en fila o botón Ver selecciona la salida.
- Panel lateral/contextual en Salidas con KPIs de la salida seleccionada.
- Accesos rápidos desde el panel: Reservas, Cargos, Fichas, CSV salida y ficha vigente.
- Fila seleccionada resaltada.
- Versión centralizada actualizada a v66.

Sin cambios en:

- lógica de capitán;
- reservas de socio;
- liquidación;
- fichas;
- preflight;
- reglas de cobro;
- motor de comunicaciones/emails, que queda previsto para v67.
