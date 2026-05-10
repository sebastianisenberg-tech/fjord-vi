# Performance operativa 1.16.1

## Principio
Socio y Capitán deben ser los módulos más rápidos del sistema. Administración y Sistema pueden tener herramientas pesadas, pero siempre diferidas o bajo demanda.

## Implementado
- Anti doble toque global para formularios POST.
- Feedback inmediato en botones críticos.
- Descargas técnicas no bloqueadas.
- Cabeceras de cache prudentes por tipo de ruta.
- Endpoint `/admin/performance_policy.json`.
- Panel informativo de política de performance en Sistema.

## No modificado
- Capitán.
- QR.
- Reservas.
- Cargos.
- Cierres.
- Fichas.

## Criterio futuro
Toda funcionalidad nueva debe declarar si es:
- operativa crítica y liviana;
- administrativa;
- técnica/diferida.
