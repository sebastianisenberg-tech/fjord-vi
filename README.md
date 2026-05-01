# YCA · Fjord VI · Embarque · v39.3.0

Sistema piloto para gestionar paseos de fin de semana del Fjord VI.

## Estructura de deploy

Esta versión es plana y sin duplicados:

- HTML en la raíz del proyecto.
- Recursos visuales únicamente en `/static`.
- Sin carpeta `/templates`.
- `main.py` usa renderizado seguro desde raíz y sirve `/static/style.css`.

## Fixes incluidos

- Corrige el error Jinja: `builtin_function_or_method object is not iterable` cambiando `g.items` por `g["items"]`.
- Corrige carga de CSS con `app.mount('/static', StaticFiles(...))`.
- Mantiene estructura simple para copiar todo en un solo nivel desde celular.
- Mantiene QR fijo, QR dinámico, ventana operativa, histórico y cierre operativo.

## Validación rápida post deploy

Probar estas rutas:

- `/`
- `/static/style.css`
- `/admin`
- `/captain`
- `/socio`
- `/qr_fijo`
- `/embarque`

Versión interna: v39.3.0
