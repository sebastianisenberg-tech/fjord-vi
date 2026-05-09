# Fjord VI 1.8.7 · Fase 5 · Arquitectura modular controlada

## Objetivo
Preparar la separación progresiva de `main.py` sin modificar reglas visibles ni romper el beta operativo.

## Incluye
- Scaffold `app/core`, `app/services`, `app/routers`.
- Mapa de arquitectura en consola Sistema.
- Endpoints `/admin/architecture.json` y `/admin/architecture.txt`.
- Checklist de release ampliado con control de modularización.
- Versión unificada 1.8.7.

## Criterio técnico
Esta etapa no mueve todavía la lógica crítica de reservas. Primero crea fronteras claras y verificables para que la futura división del backend se haga con menos riesgo.

## Próximo paso
Mover por tandas pequeñas:
1. config y helpers puros;
2. seguridad;
3. usuarios;
4. reservas;
5. salidas/cierres;
6. backups/sistema;
7. routers.
