# Fjord VI Embarque

Sistema web operativo para la gestión de reservas, embarque, check-in, cierre de navegación y liquidación del barco **Fjord VI** del Yacht Club Argentino.

Versión actual: **Fjord VI 1.6.7**

## Propósito

La aplicación centraliza el flujo completo de una navegación programada:

- publicación de salidas;
- reserva de socios;
- carga de invitados;
- lista de espera;
- check-in y control del Capitán;
- cierre de navegación;
- generación de ficha;
- liquidación de cargos;
- trazabilidad de cambios y fichas anuladas.

El objetivo es reemplazar procesos manuales dispersos por un sistema web rápido, claro, auditable y usable desde celular o computadora.

## Roles principales

### Socio

Permite al socio:

- ingresar con Nº de socio o documento;
- ver salidas disponibles;
- reservar su lugar;
- agregar invitados;
- cancelar su lugar o invitados;
- consultar estado de cupo, cargos y reglas;
- operar desde celular con interfaz simplificada.

### Capitán

Permite al Capitán:

- seleccionar la salida a controlar;
- marcar presentes, pendientes, no embarcó o sin cargo;
- generar QR de embarque;
- cerrar la navegación;
- reabrir dentro de la ventana operativa;
- ver ficha vigente e historial de fichas.

El Capitán no modifica la planificación previa de la salida ni la capacidad operativa definida por Administración.

### Administración

Permite a Administración:

- crear salidas;
- definir fecha, hora, capacidad operativa y reserva institucional;
- cargar y editar usuarios;
- asignar roles;
- consultar reservas;
- revisar fichas de cierre;
- exportar datos;
- mantener trazabilidad operativa.

## Participación protocolar

El sistema incorpora participación protocolar como una marca especial de reserva.

Una participación protocolar:

- ocupa plaza;
- no genera cargo;
- no genera deuda por no embarcar;
- no depende económicamente de un socio anfitrión;
- puede corresponder a un socio o a una persona externa;
- queda auditada como autorizada por Comisión Fjord VI.

La función se gestiona mediante permiso institucional **Comisión Fjord VI**, asignable desde Administración en sección avanzada.

## Capacidad operativa y reserva institucional

Cada salida puede tener:

- **Capacidad operativa**: cantidad total máxima de personas habilitadas para esa navegación, sin contar al Capitán.
- **Reserva institucional**: plazas reservadas para participación protocolar.

La lista de espera normal no consume la reserva institucional.

Esto permite manejar situaciones institucionales sin desplazar socios y sin mezclar cupos públicos con plazas reservadas.

## Cierre y liquidación

Al cerrar una navegación, el sistema genera una ficha de cierre con:

- navegantes;
- socios;
- invitados;
- cargos por invitados navegados;
- cargos por no-show o cancelación tardía;
- participaciones protocolares sin cargo;
- total general a liquidar;
- trazabilidad documental.

Si una salida se reabre y se vuelve a cerrar, la ficha anterior queda anulada y se genera una nueva ficha vigente.


## Seguridad de credenciales

La versión 1.3.1 incorpora **cambio obligatorio de clave inicial**.

Cuando un usuario entra por primera vez con clave temporal, el sistema lo deriva a una pantalla premium para definir su clave personal antes de acceder a Socio, Capitán o Administración.

Reglas mínimas:

- mínimo 6 caracteres;
- repetir clave correctamente;
- no usar la clave temporal;
- no usar Nº de socio;
- no usar documento.

La clave se guarda hasheada y el usuario queda habilitado para operar normalmente después del cambio.

## Stack técnico

- Python
- FastAPI
- Jinja2
- SQLAlchemy
- SQLite o PostgreSQL mediante `DATABASE_URL`
- HTML/CSS/JavaScript
- Deploy compatible con Render

## Archivos principales

```text
main.py
templates/
static/
requirements.txt
Procfile
Dockerfile
docker-compose.yml
render.yaml
start.sh
```

## Variables de entorno recomendadas

```text
SECRET_KEY
DATABASE_URL
APP_ENV
MAX_CREW
MIN_CREW
INVITED_FEE
```

En producción, `SECRET_KEY` debe ser una clave aleatoria fuerte.

## Deploy en Render

El repositorio incluye archivos compatibles con Render:

- `render.yaml`
- `Procfile`
- `requirements.txt`
- `start.sh`

La base de datos recomendada para uso real es PostgreSQL mediante `DATABASE_URL`.

## Limpieza del repositorio

Este ZIP corresponde a una versión limpia de producción/repo.

No incluye:

- archivos `AUDIT_*.txt`;
- `__pycache__`;
- archivos `.pyc`;
- residuos temporales de desarrollo.

Las auditorías históricas fueron útiles durante el desarrollo, pero no son necesarias para ejecutar ni desplegar el sistema.

## Autor

Software desarrollado para uso operativo del Fjord VI.

Autor registrado en metadata interna: **Sebastián Isenberg**.


## Gestión de claves

La versión 1.3.1 incorpora:

- cambio voluntario de clave desde Perfil;
- verificación de clave actual;
- reset administrativo de clave temporal;
- obligación de redefinir clave luego del reset;
- auditoría de cambios y resets.
