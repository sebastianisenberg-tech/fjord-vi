# Fjord VI v68.4

Versión con padrón oficial e identidad blindada.

## Cambios clave

- Login por Nº de socio o DNI.
- Si un número coincide con Nº de socio y con DNI de otra persona, se prioriza Nº de socio.
- Si hay Nº de socio duplicado, se bloquea login y queda auditado.
- Importador de padrón con previsualización y validación de conflictos.
- Importador no pisa un usuario cuando Nº socio y DNI apuntan a personas distintas.
- WhatsApp separado de teléfono.
- Categorías YCA normalizadas.

## Base de datos

PostgreSQL como fuente principal; JSON solo exportación técnica según versiones previas.
