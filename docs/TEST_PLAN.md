# Plan de tests Fjord VI

## Smoke tests actuales

Validan que el paquete no salga incompleto: archivos críticos, templates, static, documentación y versión.

## Tests que conviene sumar

1. Login admin, socio y capitán.
2. Cambio obligatorio de clave temporal.
3. Reserva de socio.
4. Invitado agregado y cancelado.
5. Regla de cupo.
6. Capitán marca presente/no embarca.
7. Cierre de salida.
8. Generación de ficha.
9. Reset de clave por administración.
10. Rutas admin protegidas por rol.

## Criterio profesional

Ninguna versión debería deployarse si falla un test crítico.
