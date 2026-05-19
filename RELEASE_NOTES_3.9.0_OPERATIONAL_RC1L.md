# Fjord VI 3.9.0 OPERATIONAL RC1L

Intervención limitada a comunicaciones.

Objetivo:
- Mantener Socio y Capitán rápidos.
- No enviar SMTP dentro de acciones operativas.
- No depender de Administración, refresh, computadora ni celular abierto.
- Separar eventos críticos inmediatos de cambios consolidables de invitados.

Cambios:
- Nuevo email consolidado: actualizacion_invitados_socio.
- Altas, bajas, correcciones, reactivaciones y espera de invitados/menores actualizan un único aviso consolidado por socio + salida.
- El aviso incluye cambio puntual y resumen vigente completo de invitados asociados.
- Cambios de invitados usan ventana corta de estabilización, por defecto 5 minutos.
- Reserva confirmada, reserva en espera, cancelación del titular, salida cancelada y salida reprogramada quedan como eventos inmediatos.
- Worker automático de Render se mantiene autónomo.

No se tocó:
- motor de reservas;
- Capitán;
- cierre/reapertura/recierre;
- liquidaciones;
- PDFs;
- lógica reglamentaria.
