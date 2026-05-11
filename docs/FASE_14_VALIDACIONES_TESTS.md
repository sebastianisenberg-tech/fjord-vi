# Fjord VI 1.13.0 · Fase 14 Validaciones backend y tests reales

Objetivo: elevar robustez profesional sin modificar la experiencia visible ni tocar reservas, invitados, cargos o cierres.

## Qué incorpora

- Módulo `app/core/business_rules.py` con reglas puras y testeables.
- Tests automáticos iniciales sobre reglas críticas.
- Validaciones preparadas para conectar gradualmente a endpoints.
- Versión unificada `1.13.0`.

## Reglas cubiertas

- Cupo máximo y prevención de sobreventa.
- Documento duplicado dentro de salida.
- Salida cerrada/cancelada no admite nuevas reservas.
- Transiciones de estado inválidas.
- Permisos por rol.
- Invitado con socio responsable obligatorio.
- Ventana de cierre del capitán.
- Confirmaciones exactas para operaciones peligrosas.

## Criterio de seguridad

Esta fase no cambia la operatoria existente. Primero deja las reglas separadas y verificables. En fases siguientes se conectan a rutas críticas, una por una, para no introducir regresiones.

## Tests

Ejecutar:

```bash
pytest
```

Los tests de Fase 14 son de bajo riesgo porque no requieren PostgreSQL ni servidor corriendo.
