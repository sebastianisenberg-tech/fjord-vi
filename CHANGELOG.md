# Fjord VI 1.0 - Release operativa premium

- Versión pública unificada: Fjord VI 1.0.
- ID único de liquidación en formato LIQ-YYYY-000000.
- Candados visuales para salida cerrada y liquidación congelada.
- Watermark ANULADA reforzado.
- Ficha, historial, administración y CSV con trazabilidad más clara.
- Se preservan cargos, QR, cierre/reapertura y reasignación blindada.

---

# v68.10 - Reasignación blindada

- Corrige un caso crítico detectado en auditoría: al marcar Presente/Por confirmar/Ausente/No embarca después de una reasignación, ya no se borra la traza de reasignación.
- Mantiene la regla de una sola reasignación por invitado/salida incluso si se reabre la salida y se cambia el estado varias veces.
- Conserva identidad visible: socios por N° de socio, invitados/menores no socios por DNI.
- No modifica cálculos de cargos, QR, base de datos ni flujo central de cierre/reapertura.

## v68.10

- Identidad visible institucional: socios por N° de socio; invitados/menores no socios por DNI.
- Capitán muestra DNI de invitados abreviado para no ensuciar la pantalla móvil.
- Reasignación blindada: un invitado solo puede reasignarse una vez por salida.
- Fichas con versión visible (Ficha V1, V2, V3) en ficha e historial.
- Tooltips y textos existentes preservados; sin cambios en cálculo de cargos, QR ni PostgreSQL.

## v68.8
- Pulido de trazabilidad y UX sin tocar la lógica de cargos ni el flujo central.
- Watermark ANULADA reforzado para pantalla e impresión.
- Fichas anuladas con bloque temporal: generada, anulada, motivo y reemplazo.
- Fichas vigentes con aviso de liquidación congelada.
- DNI visible de invitados/menores en ficha final y ayuda visual en tripulación del capitán.
- Tooltips y toasts operativos reforzados en cierre, reapertura, reasignación y preflight.
- Etiquetas más claras para No vino / cargo.

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
