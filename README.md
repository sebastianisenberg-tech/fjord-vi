# YCA · Fjord VI · Embarque · v26.9.3

Sistema piloto para gestionar paseos de fin de semana del Fjord VI.

## Qué incluye

- Login por rol: socio, capitán y administración.
- Reserva de socio titular.
- Alta de invitados y menores asociados a socio responsable.
- Corte de 48h para invitados condicionales.
- Lista de espera con prioridad: antes del corte de 48h, un socio puede desplazar a un invitado/menor activo si el cupo está completo.
- Después del corte de 48h, la tripulación queda congelada; ante vacantes se promueve la lista de espera por orden de inscripción.
- La lista de espera no genera cargos mientras la persona no entre al cupo.
- Control de embarque por capitán.
- Cierre de salida con cálculo de cargos.
- Exportación CSV de manifest y liquidaciones.
- Interfaz mobile-first más presentable para demo.
- Reinicio de datos demo desde administración.

## Reglas implementadas

- Mínimo de tripulantes: 2.
- Máximo de tripulantes: 9, sin contar capitán.
- Invitados condicionales hasta 48h antes de la salida.
- Invitado no embarca si no embarca su socio responsable.
- Socio no-show o cancelación tardía: 70% de la tarifa de invitado.
- Invitado no-show: 100% de la tarifa de invitado.
- Hijo menor hasta 13 años: sin cargo en el piloto.

## Usuarios demo

- Socio: `20123456` / `demo1234`
- Capitán: `30999111` / `demo1234`
- Admin: `27999111` / `demo1234`

## Ejecutar localmente

```bash
docker-compose up --build
```

Abrir:

```text
http://localhost:8000
```

## Ejecutar sin Docker

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## Deploy Render

El paquete incluye `render.yaml`. Para demo puede subirse como Web Service usando Docker.

Variables sugeridas:

```text
SECRET_KEY=poner-una-clave-larga
DATA_DIR=/data
MAX_CREW=9
MIN_CREW=2
INVITED_FEE=45000
LATE_SOCIO_RATE=0.70
```

## Qué NO es todavía

No es producción real. Falta integrar padrón oficial, autenticación institucional, backups automáticos, HTTPS bajo dominio del Club, auditoría formal, pruebas con usuarios reales y revisión reglamentaria final.


## v26.9.3
- Ajuste de producción: Procfile/start.sh apuntan a `main:app`.
- La selección automática prioriza salidas operables sobre salidas canceladas.
- Mensajes de cancelación homogeneizados: sin cargos ni preliquidaciones vigentes.


### v26.9.8
Versión de ajuste fino: feedback documental, refuerzo de cupo y administración más clara.

### v27.6.0
Versión con panel de administración orientado a oficina: planificación de salidas, revisión posterior al fin de semana, liquidación y exportación contable.

### v27.6.0 ESTABLE
Versión ajustada para prueba operativa: solo paseos de fin de semana, módulo Socio y Capitán mobile-first, Administración de oficina pensada para PC y liquidación manual posterior.

### v27.7.0
- Corrección visual puntual en Administración: botón “Salir” del header en blanco, más grande y visible, consistente con Socio/Capitán.
- Sin cambios de lógica, reservas, cargos ni reglas.
