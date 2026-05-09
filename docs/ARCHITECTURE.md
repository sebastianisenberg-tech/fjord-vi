# Fjord VI - arquitectura técnica

## Objetivo
Sistema web operativo para reservas, embarque, administración, capitán, auditoría y soporte técnico del Fjord VI.

## Estructura principal

```text
app/              fronteras modulares futuras de backend
static/           CSS, JavaScript, imágenes y recursos públicos
templates/        plantillas Jinja2/HTML
main.py           aplicación FastAPI actual y punto de entrada
migrations/       migraciones SQL versionadas futuras
tests/            pruebas automáticas y smoke tests
scripts/          utilidades de diagnóstico local
```

## Estado actual
El sistema todavía conserva gran parte de la lógica en `main.py`, pero ya tiene una frontera modular inicial en `app/`. La prioridad de la fase 12 es preparar una transición ordenada sin cambiar reglas operativas.

## Regla de ingeniería
Las reglas de negocio no deben depender de HTML ni JavaScript visual. Deben terminar alojadas en servicios Python:

```text
app/services/reservations.py
app/services/outings.py
app/services/users.py
app/services/backups.py
```

## Rutas críticas
Deben permanecer protegidas contra regresiones:

```text
/
/login
/logout
/admin
/admin/sistema
/admin/system
/admin/actividad
/health.json
```

## Fuente de verdad
PostgreSQL es la fuente de verdad. JSON queda para exportación o backup auxiliar, no como base operativa principal.
