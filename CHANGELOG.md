# Changelog

## 1.3.6

- Corrección definitiva del ojo mostrar/ocultar clave con `onclick` directo por campo.
- Se elimina dependencia de listeners globales para el toggle.
- Enter fluido también queda inline por campo.


## 1.3.5

- Corrección robusta de ojos mostrar/ocultar en pantallas de clave.
- Toggle directo por contenedor `.passwordWrap`, sin depender de IDs frágiles.
- Captura de evento para evitar que el foco o el browser bloqueen el click.


## 1.3.4

- Corrección de ojos mostrar/ocultar en pantalla Cambiar mi clave.
- Enter fluido: clave actual → nueva clave → repetir clave → guardar.
- Botón Volver al sistema y cruz de cierre en cambio voluntario.
- Al guardar correctamente vuelve al sistema.


## 1.3.3

- Botón visible “Cambiar mi clave” dentro de Perfil de Socio.
- Link discreto de clave para Capitán/Admin.
- Corrección de link anterior que había quedado fuera del HTML visible.


## 1.3.2

- Corrección precisa de alineación del ícono mostrar/ocultar clave.
- Centrado real dentro del campo con `top:0`, `bottom:0` y `margin:auto`.
- Elimina efecto visual de botón externo caído.


## 1.3.1

- Cambio obligatorio de clave inicial.
- Nuevos usuarios quedan con clave temporal y deben definir clave personal.
- Usuarios que ingresan con `demo1234` son derivados a cambio de clave.
- Nueva pantalla premium `Crear clave personal`.
- Validación de doble clave, longitud mínima y bloqueo de clave temporal/Nº socio/documento.


## 1.2.7

- Ajuste del login con control mostrar/ocultar clave.
- Mantiene foco en el campo de clave al tocar el ojo.
- Evita movimientos de pantalla o scroll inesperado en mobile.

## 1.2.5

- Reemplazo del botón grande “Ver” por ícono de ojo integrado al campo de clave.
- Mejora estética del login mobile/desktop.

## 1.2.4

- Agregado de mostrar/ocultar clave en login.
- Autofocus en Nº de socio/documento.
- Enter en usuario pasa a clave.
- Enter en clave ingresa.

## 1.2.3

- Pantalla amable para sesión vencida.
- Evita JSON crudo `{"detail":"Sesión requerida"}`.
- Redirección segura al ingreso.

## 1.2.2

- Nombre visible permanente en participaciones protocolares.
- Badge PROTOCOLAR sin duplicación.
- Refuerzo visual en Capitán, Socio y Ficha.

## 1.2.0

- Participación protocolar completa.
- Reserva institucional por salida.
- Capacidad pública separada de reserva institucional.
- Permiso institucional Comisión Fjord VI.
- Protocolar sin cargo y sin dependencia económica del socio anfitrión.

## 1.1.x

- Blindaje de datos.
- Cierre y reapertura de salidas.
- Fichas vigentes/anuladas.
- Exportaciones.
- Mejoras UX mobile y administración.
