# Fjord VI 3.9.0 OPERATIONAL RC1N

Objetivo: hardening mínimo de integridad para evitar duplicación del socio titular en una misma salida.

Cambios:
- Defensa liviana de unicidad por socio/DNI dentro de una salida.
- `Reservar mi lugar` reutiliza/reactiva una reserva existente del socio en vez de crear una segunda fila equivalente.
- La vista de Socio selecciona una reserva titular canónica usando DNI normalizado.
- Si se detectan duplicados equivalentes de socio titular en la lectura de una salida, se mantiene una única fila operativa y las otras quedan canceladas operativamente, sin borrar auditoría.

No se tocó:
- Motor de emails / SMTP / worker.
- Capitán.
- Cierres.
- PDFs.
- Liquidaciones.
- Lógica reglamentaria de cargos.
