# Audit 1.16.9 - Capitán agrupado por socio

Cambios:
- Removido botón “Clave” de la barra superior del Capitán.
- Conservado botón “Cambio de clave” en el bloque inferior del Capitán.
- Agregado armado de `captain_groups` en backend, sin alterar reservas, cargos ni cierre.
- Render de tripulación por grupos: socio titular + invitados/menores.
- Protocolares/institucionales separados al final.
- CSS liviano, sin dependencias nuevas ni animaciones pesadas.

Validación:
- `python -m py_compile main.py` OK.
- Render Jinja de `captain.html` OK.
