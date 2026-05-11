

## v1.16.13 hotfix Capitán
- Corrige error de render en captain.html: variable de vista de reserva inicializada dentro del macro.
- Alinea todas las filas de tripulación a la izquierda.
- Simplifica la barra lateral a un solo color por grupo de socio.
- Mantiene institucionales y espera con el color del socio responsable.
# Changelog

## 1.16.13 - Capitán alineado y colores por grupo

- Tripulación de Capitán alineada a la izquierda para lectura rápida en celular.
- Eliminadas las barras laterales múltiples y los desplazamientos visuales que generaban ruido.
- Socio e invitados comparten un único color lateral de grupo.
- Institucionales y espera conservan el color del socio responsable para trazabilidad visual.
- Se mantiene versión 1.16.13 centralizada en `VERSION.txt` y `main.py`.

## 1.16.13 - Capitán grupos operativos conservadores
- Tripulación del Capitán reorganizada visualmente por socio responsable.
- Invitados comunes indentados debajo del socio correspondiente.
- Institucionales/protocolares separados en bloque propio al final.
- Lista de espera separada al final, indicando de qué socio depende cada persona.
- Badge Socio integrado junto al nombre, no alejado a la derecha.
- Guía rápida responsive y versión 1.16.13 unificada en sistema, ficha y PDF.
- Ajuste conservador del PDF para evitar segunda hoja en blanco en la impresión móvil.


## 1.16.13 - Capitán UX refinada
- Elimina indicador TAP redundante; el menú ⋯ queda como acción excepcional.
- Reasignar invitado queda contextualizado dentro del menú ⋯ para reducir ruido vertical.
- Agrega indicador visual de scroll en filtros superiores.
- Refuerza jerarquía de métricas, estados, institucionales y cancelación por capitán.
- Agrega Guía rápida del Capitán en el bloque inferior de cuenta.
- Mantiene intacta la lógica de cargos, cierre, cancelación, reapertura y liquidación.

# CHANGELOG consolidado

## 1.16.13
- Capitán: agrupación visual por socio con banda de color compartida.
- Socio titular con más jerarquía tipográfica.
- Invitados subordinados con menos texto redundante.
- Institucionales/protocolares separados al final con estilo neutro.
- Se mantiene intacta la lógica de cargos, cierre, reapertura y liquidación.
- Limpieza de documentación suelta en raíz: se consolida la memoria útil del proyecto.

## 1.16.10
- Mejora de contraste operativo para Capitán.
- Eliminación de redundancias visuales en institucionales.

## 1.16.9
- Agrupación inicial de tripulación en Capitán.
- Eliminación de botón Clave redundante en barra superior.

## Memoria de diseño
El proyecto separa tres experiencias: Socio simple, Capitán operativo y Administración completa. La prioridad es evitar confusión y mantener velocidad real de uso.
