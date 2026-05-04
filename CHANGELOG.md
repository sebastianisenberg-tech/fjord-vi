# v61.0 - Capitán: estados inequívocos

- Renombra en Capitán el estado ambiguo “Ausente” como “No vino (cobra)”.
- Renombra “No embarca” como “No embarca (sin cargo)” en chips, botones, resumen y paneles.
- Mantiene intacta la lógica interna existente: Presente cobra si corresponde, Ausente genera cargo reglamentario, No embarca no genera cargo.
- Refuerza textos de ayuda y resumen para evitar confusión del capitán.
- Actualiza preflight y ficha para usar terminología más clara.

# Fjord VI v59.0 - Pre-cierre inteligente

- Revisión previa antes de cerrar y liquidar.
- Detecta errores bloqueantes: cupo excedido, documento duplicado, invitado sin DNI/documento, invitado presente sin socio responsable presente.
- Advierte DNI con formato atípico para revisar datos históricos o de prueba.
- Muestra resumen estimado: presentes, invitados navegados, no-show con cargo, subtotal navegación, subtotal no-show y total.
- Sugiere correcciones operativas antes del cierre.
- El cierre definitivo vuelve a validar para evitar inconsistencias.
- No toca Socio ni Fichas salvo calidad de datos del cierre.
