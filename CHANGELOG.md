# v68.4 - Login e identidad blindada

- Login prioriza Nº de socio sobre DNI cuando ambos podrían coincidir.
- Bloqueo de login si hay Nº de socio duplicado.
- Auditoría de conflictos ambiguos de identidad.
- Importación de padrón detecta conflictos entre Nº de socio y DNI pertenecientes a personas distintas.
- Importación evita pisar usuarios si hay conflicto de identidad.
- Conversión invitado → socio valida Nº de socio duplicado.
- Mantiene importador CSV, WhatsApp separado y categorías YCA.
