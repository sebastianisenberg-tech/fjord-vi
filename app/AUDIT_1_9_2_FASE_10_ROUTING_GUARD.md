# Fjord VI 1.9.2 - Fase 10 Routing Guard

## Objetivo
Corregir la regresión detectada en 1.9.1 donde el acceso directo o el tab de Sistema podía terminar en una ruta inexistente y mostrar JSON técnico `Not Found`.

## Cambios
- Se agregan alias humanos para Sistema: `/admin/sistema`, `/admin/system`, `/sistema`, `/system`.
- Se agregan alias humanos para Comunicaciones: `/admin/comunicaciones`, `/admin/communications`, `/comunicaciones`, `/communications`.
- El admin acepta `page=system`, `tab=system`, `page=sistema` y sus equivalentes.
- Handler 404 humano: evita JSON crudo en navegación normal y redirige rutas conocidas.
- Versión unificada 1.9.2.

## Alcance
No modifica reglas de reservas, invitados, cargos, cierres, salidas ni liquidaciones.

## Checklist
- Root `/` mantiene redirección humana.
- `/admin?page=sistema` abre Sistema.
- `/admin/system` redirige a Sistema.
- `/admin/sistema` redirige a Sistema.
- `/admin?tab=system` abre Sistema.
- Rutas inexistentes ya no deben exponer JSON técnico al usuario final.
