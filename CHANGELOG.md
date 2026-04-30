# Fjord VI · Embarque

## v33.0.0
- Agrega QR fijo del barco: `/embarque`.
- El QR fijo pide DNI/documento y detecta automáticamente la salida activa del día.
- Solo registra si el documento figura en la salida de hoy como socio, invitado, menor o lista de espera válida.
- Si no figura, rechaza con mensaje claro.
- La autorización final de embarque sigue siendo del capitán.
- Agrega página imprimible `/qr_fijo` para QR metálico, cartelera, portería o guardia náutica.
- Mantiene QR dinámico por salida, cierre inteligente, ventana de 48h, auditoría y enclavamiento socio-invitado.
