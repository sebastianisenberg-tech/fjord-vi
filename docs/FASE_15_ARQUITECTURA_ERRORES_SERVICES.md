# Fase 15 · Arquitectura backend, errores y servicios

Versión: 1.16.3

Objetivo: profesionalizar la estructura interna sin modificar la operación visible de reservas, invitados, cargos ni cierres.

## Cambios incluidos

- Frontera central de errores en `app/core/errors.py`.
- Logging base centralizado en `app/core/logging_config.py`.
- Settings centralizados en `app/core/settings.py`.
- Scaffold de repositorios en `app/repositories/`.
- Scaffold de middleware separado en `app/middleware/`.
- Servicio de operaciones en `app/services/operations.py`.
- Handler global para `AppError` integrado en `main.py`.
- Versión unificada a `1.16.3`.
- Tests de estructura para verificar que la arquitectura profesional esté presente.

## Qué mejora

- Permite que nuevas reglas levanten errores tipados y no mensajes improvisados.
- Separa futuras consultas SQL de rutas y templates.
- Facilita que otro programador entienda dónde colocar lógica nueva.
- Prepara el camino para sacar lógica del monolito sin romper la beta.

## Qué NO cambia

- No cambia UX.
- No cambia reglas de reservas.
- No cambia invitados.
- No cambia cargos.
- No cambia cierres.
- No cambia login ni sesiones visibles.

## Próximo paso recomendado

Fase 16: conectar gradualmente servicios y repositorios reales en endpoints críticos, empezando por operaciones de bajo riesgo:

1. consultas de actividad;
2. lectura de usuarios;
3. lectura de salidas;
4. validación previa de reservas;
5. acciones críticas con `BusinessRuleAppError`.
