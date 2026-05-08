# Auditoría y corrección 1.7.5

Base: Fjord VI · v1.7.5

## Cambios aplicados

- `APP_VERSION = "1.7.5"` en `main.py`.
- Normalización de versiones visibles y metadata.
- Revisión de actions POST de formularios contra rutas declaradas.
- Corrección o limpieza de posible reset-password huérfano si estaba presente.
- Sin cambios de lógica operativa.

## Validaciones

- Python syntax: True
- Jinja templates: OK
- Versiones detectadas: ['1.7.5', 'v1.7.5']

## Formularios POST pendientes de revisión manual

Antes:
[
  "/admin",
  "/admin/update_user/",
  "/admin_qr",
  "/captain/preflight"
]

Después:
[
  "/admin",
  "/admin/update_user/",
  "/admin_qr",
  "/captain/preflight"
]

Nota: algunos pueden ser falsos positivos si usan rutas dinámicas no detectadas o JavaScript.
