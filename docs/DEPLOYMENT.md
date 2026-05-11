# Deploy Fjord VI

## Flujo correcto desde PC

1. Descargar ZIP completo.
2. Descomprimirlo.
3. Subir todo el contenido del ZIP al repositorio, respetando carpetas:

```text
app/
templates/
static/
main.py
requirements.txt
Dockerfile
VERSION.txt
software_metadata.json
```

4. No subir `__pycache__` ni archivos `.pyc`.
5. Commit en la branch de trabajo.
6. Esperar deploy automático de Render.
7. Verificar `/health.json` y `/admin/sistema`.

## Checklist post deploy

- `/` redirige a pantalla humana.
- `/login` abre login.
- `/admin/sistema` abre Sistema.
- `/admin/actividad` abre Actividad.
- Login admin correcto.
- Login socio correcto.
- Login capitán correcto.
- Reset de clave obliga a cambiarla.
- PostgreSQL conectado.
- Release check sin errores críticos.
