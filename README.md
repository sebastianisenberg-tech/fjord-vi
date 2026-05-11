# Fjord VI · Sistema de Reservas y Embarque

Versión: 1.16.11

Sistema web interno para gestionar salidas de fin de semana del Fjord VI, con foco en uso real desde celular para socios y capitán, y administración más completa desde escritorio.

## Filosofía operativa

El sistema prioriza eficacia, velocidad, claridad y prevención de errores. Las pantallas de Socio y Capitán deben ser livianas, rápidas y legibles en celulares pequeños, incluso con luz de día o durante una operación real de embarque. Administración puede ser más completa porque se usa como backoffice.

## Roles

- Socio: consulta salidas, reserva lugar, agrega invitados y cancela su lugar dentro de las reglas.
- Capitán: controla embarque, marca presentes, ausentes y no embarca; puede cancelar la salida por causa operativa, reabrir una salida y cerrar generando ficha.
- Administración: gestiona salidas, padrón, fichas, auditoría, liquidaciones, exportaciones y correcciones de backoffice.

## Reglas funcionales principales

- El socio que embarca no paga.
- El socio que no embarca después de la ventana reglamentaria puede generar cargo.
- El invitado común depende del socio responsable y no debe embarcar si el socio responsable no está presente, salvo reasignación válida.
- Los invitados institucionales/protocolares son una excepción: no dependen del socio para embarcar, no son desplazables por socios y no generan cargo.
- Si el capitán marca “No embarca / sin cargo”, se interpreta como decisión operativa o de seguridad y no genera cargo.
- Si el capitán cancela la salida por clima, rotura, marea u otra causa operativa, la salida no genera cargos mientras permanezca cancelada.
- El cierre genera ficha de navegación y liquidación consolidada. Si se reabre, la ficha vigente se anula y queda historial.

## UX del Capitán

La pantalla Capitán es un tablero operativo, no un formulario administrativo. Debe permitir ver rápido quién viene, marcar estados tocando, distinguir socios de invitados y evitar lectura redundante.

Desde 1.16.11 la tripulación se agrupa visualmente por socio: el socio titular aparece con mayor jerarquía y sus invitados debajo con la misma banda de color. Los institucionales quedan separados al final con banda neutra.

## Deploy

Proyecto FastAPI/Jinja. Archivos principales: `main.py`, `templates/`, `static/`, `requirements.txt`, `render.yaml`, `Procfile`.
