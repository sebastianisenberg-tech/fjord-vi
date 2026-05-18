# Fjord VI 3.9.0-OPERATIONAL-RC1BB

Release de corrección focalizada sobre 3.9.0-OPERATIONAL-RC1B.

## Objetivo

Corregir dos flancos detectados durante el test operativo:

1. Versionado visible inconsistente entre Administración, Comunicaciones, Sistema, diagnóstico y documentos.
2. SMTP con error de red `OSError: [Errno 101] Network is unreachable` en entorno Render/hosting.

## Cambios

- `APP_VERSION`, `APP_BUILD` y `RELEASE_LABEL` quedan unificados exactamente como `3.9.0-OPERATIONAL-RC1B`.
- Release check ahora valida igualdad exacta entre las tres fuentes de versión.
- Comunicaciones deja de mostrar `SMTP · RC8` y muestra `SMTP · 3.9.0-OPERATIONAL-RC1B`.
- Corrección de textos visibles de release check que todavía mencionaban RC8.
- SMTP fuerza conexión IPv4 para evitar fallos de salida por IPv6 sin ruta en el contenedor.
- Diagnóstico SMTP ahora agrega explicación operativa cuando falla por red, timeout, autenticación o host inválido.
- Se mantiene el desacople: Socio y Capitán encolan emails, pero nunca esperan SMTP.

## No se tocó

- Motor de reservas.
- Capitán.
- Cierre/liquidación.
- Reapertura/recierre.
- Reasignaciones.
- Cálculo de cargos.
- PDF salvo el texto de versión que se genere desde esta versión en adelante.

## Validación local

- `python -m py_compile main.py`: OK.
- `pytest -q`: 40/40 OK.
