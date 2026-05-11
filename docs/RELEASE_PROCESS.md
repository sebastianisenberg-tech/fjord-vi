# Proceso de release

## Antes del release

- Compilar `main.py`.
- Revisar versión unificada.
- Ejecutar smoke tests.
- Verificar que no haya `.env`, `.pyc` ni `__pycache__` en el ZIP.
- Revisar que las rutas críticas sigan activas.

## Después del deploy

- Abrir `/health.json`.
- Abrir `/admin/sistema`.
- Revisar PostgreSQL y release check.
- Probar login/logout.
- Probar socio, capitán y administración.
- Confirmar que no aparezca JSON técnico en raíz ni pantallas blancas.
