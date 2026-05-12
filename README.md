# Fjord VI 1.18.18

Versión operativa actual del sistema web de reservas y embarque del Fjord VI con blindaje monolítico reforzado.

- Release unificado en versión 1.18.18.
- Reasignación persistente con responsable final único e historial auditable.
- Base de datos PostgreSQL como fuente de verdad en Render.
- Diagnóstico operativo, release check y estado humano disponibles desde Sistema.
- Mantiene la lógica operativa vigente de socio, capitán, administración, cierres, reaperturas, cargos e institucionales.

## Resumen

Sistema web interno para gestionar salidas de fin de semana del Fjord VI, con foco en uso real desde celular para socios y capitán, y administración más completa desde escritorio.

## Control mínimo antes de ZIP/deploy

- Ejecutar `python scripts/release_check.py`.
- El script valida versión unificada, compileall, caches Python, archivos críticos y corre los tests mínimos de negocio/release.
- El ZIP no debería considerarse oficial si ese script falla.

- Exportación PDF ejecutiva del módulo Estadísticas para reuniones de Comisión Directiva.
