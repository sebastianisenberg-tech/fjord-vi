
## v65.8 - Versión centralizada
- La versión visible sale de una única constante `VERSION` en `main.py`.
- Se reemplazaron textos hardcodeados de versión en templates.
- CSS/JS usan `?v={{version}}` para evitar mezcla de caché.
- Ficha, preflight y listados muestran la versión del sistema.

# v65.7 - Preflight socio responsable + ficha total label

- Agrega validación bloqueante: invitado presente no puede quedar asociado a socio no presente.
- Revalida la regla justo antes de cerrar, después de convertir pendientes a ausentes.
- Cambia el rótulo final de ficha de "por invitados" a "TOTAL GENERAL A LIQUIDAR".

# v65.6 - Estado final limpio y liquidación reglamentaria

- La liquidación queda basada exclusivamente en el estado final de cada persona.
- Socio presente: $0.
- Socio no vino: 70% de la tarifa de invitado.
- Invitado presente: 100% de la tarifa de invitado.
- Invitado no vino: 100% de la tarifa de invitado.
- No embarca por decisión del capitán: $0.
- Al volver a Presente se limpian cargos previos de no-show.
