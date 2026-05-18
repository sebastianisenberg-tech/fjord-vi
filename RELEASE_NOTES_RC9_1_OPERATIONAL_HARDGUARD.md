# Fjord VI RC9.1 Operational Hardguard

Objetivo: estabilidad operativa sin bloquear Socio ni Capitán por emails o doble toque.

Cambios:
- SMTP/outbox: commits agrupados en acciones de Capitán y cierre.
- Si falla el encolado de email, se audita y no bloquea la operación principal.
- Formularios nativos: bloqueo visual extendido para evitar doble toque/reintento prematuro en red lenta.
- Capitán/cierre: no se modificó la lógica reglamentaria de liquidación.
