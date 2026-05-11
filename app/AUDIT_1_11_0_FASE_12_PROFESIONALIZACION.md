# Fjord VI 1.11.0 - Fase 12 Profesionalización interna

## Objetivo
Iniciar el pasaje de beta funcional a proyecto profesional mantenible, sin modificar reglas de reservas, invitados, cargos, cierres ni pantallas operativas críticas.

## Cambios incorporados

- Documentación técnica inicial en `docs/`.
- Checklist de seguridad.
- Guía de deploy desde PC/GitHub/Render.
- Modelo de datos operativo documentado.
- Proceso de release documentado.
- `.env.example` para separar secretos del código.
- Carpeta `migrations/` preparada.
- Smoke tests estáticos en `tests/`.
- Script local `scripts/smoke_check.py`.
- Versión unificada 1.11.0.
- Health JSON declara `phase12_profesionalizacion_interna`.

## No cambia

- Reservas.
- Invitados.
- Cargos.
- Cierre de capitán.
- Fichas.
- Login funcional.
- PostgreSQL.
- Templates operativos.

## Riesgo
Bajo. Es una fase documental y de estructura profesional. No introduce dependencias nuevas ni cambios de base de datos.
