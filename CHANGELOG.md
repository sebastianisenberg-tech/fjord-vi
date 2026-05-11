# Fjord VI 1.18.3 · Pruebas lógicas Capitán en Sistema

- Agrega diagnóstico aislado de reglas críticas del módulo Capitán dentro de Sistema.
- No toca datos reales ni modifica salidas, reservas, fichas o liquidaciones.
- Incluye tests para socio ausente con cargo, no embarca/sin cargo, institucionales, reasignación, liquidación e invariantes.
- Expone resultados en Sistema, JSON y TXT para soporte.


## 1.18.2 - Capitán: cascada operativa y económica
- Restaura cascada de invitados comunes cuando el socio responsable no embarca.
- Socio ausente/con cargo: invitados comunes quedan Ausente con cargo al socio original, salvo reasignación.
- Socio No embarca/sin cargo: invitados comunes quedan No embarca sin cargo, salvo reasignación.
- Institucionales/protocolares quedan fuera de la cascada económica y operativa del socio.
- Cierre aplica la misma cascada antes de validar y liquidar.


## v1.18.1
- Capitán: separación visual más clara entre grupos operativos por socio responsable.
- Se mantiene intacta la lógica de embarque, cierre, reapertura, espera y liquidación.
- Versión actualizada a 1.18.1.


## 1.16.12 - Capitán UX refinada
- Elimina indicador TAP redundante; el menú ⋯ queda como acción excepcional.
- Reasignar invitado queda contextualizado dentro del menú ⋯ para reducir ruido vertical.
- Agrega indicador visual de scroll en filtros superiores.
- Refuerza jerarquía de métricas, estados, institucionales y cancelación por capitán.
- Agrega Guía rápida del Capitán en el bloque inferior de cuenta.
- Mantiene intacta la lógica de cargos, cierre, cancelación, reapertura y liquidación.

# CHANGELOG consolidado

## 1.16.11
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


## 1.18.4
- Sistema ordenado sin rediseño visual.
- Pruebas lógicas Capitán bajo demanda desde Sistema.
- Limpieza de textos/checks obsoletos de fases internas.
- Advertencia no bloqueante principal: SMTP pendiente.

## v1.18.5
- Exportaciones pasa a "Exportaciones e importaciones" sin rediseñar el módulo.
- Nuevo bloque de Migración operativa: exporta paquete ZIP completo para clonar beta/staging.
- Nuevo importador controlado por frase de confirmación con backup previo obligatorio.
- Reporte de integridad JSON para detectar referencias huérfanas y fichas vigentes duplicadas.
- Exportación incluye usuarios, salidas, reservas, fichas, auditoría y configuración básica.

## v1.18.6
- Exportaciones e importaciones: se agregan modos de importación.
- Clonar completo: reemplazo total del entorno operativo y metadatos.
- Reemplazo operativo: limpia salidas/reservas/fichas y conserva accesos/configuración local.
- Agregar/actualizar: modo excepcional sin borrado previo.
- Validar paquete: dry-run sin modificar datos reales.
- Importación conserva campos institucionales/protocolares.
