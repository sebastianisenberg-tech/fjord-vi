## v68.7
- Auditoría de reapertura: conserva la trazabilidad de invitados reasignados al reabrir y volver a cerrar.
- Evita duplicar textos de cargo en cierres sucesivos.
- Actualiza textos visibles/versionado desfasados.

# v68.4 - Login e identidad blindada

- Login prioriza Nº de socio sobre DNI cuando ambos podrían coincidir.
- Bloqueo de login si hay Nº de socio duplicado.
- Auditoría de conflictos ambiguos de identidad.
- Importación de padrón detecta conflictos entre Nº de socio y DNI pertenecientes a personas distintas.
- Importación evita pisar usuarios si hay conflicto de identidad.
- Conversión invitado → socio valida Nº de socio duplicado.
- Mantiene importador CSV, WhatsApp separado y categorías YCA.

## v68.6
- Preserva trazabilidad de invitados reasignados en la ficha de cierre.
- La ficha distingue mejor No vino / No-show con cargo e incluye motivo operativo.
- Mantiene la regla de cargo único: el invitado reasignado se cobra al socio responsable final, no al socio original.
