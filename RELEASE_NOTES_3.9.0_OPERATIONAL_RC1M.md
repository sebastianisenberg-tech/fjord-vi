# Fjord VI 3.9.0 OPERATIONAL RC1M

## Objetivo
Fortalecer comunicaciones operativas sin tocar Socio, Capitán, reservas, cierres, PDFs ni liquidaciones.

## Cambios
- Activación automática de eventos esenciales de email en bases existentes de Render.
- `actualizacion_invitados_socio` queda habilitado junto con su plantilla.
- Si un evento esencial está apagado por una versión previa, se reactiva al encolar.
- Si no se puede encolar por falta de email, evento o plantilla, queda registro en `NotificationLog` en vez de fallar en silencio.
- Mantiene cola desacoplada, worker automático y SMTP fuera del flujo de Socio/Capitán.

## No tocado
- Motor de reservas.
- Capitán.
- Socio visual.
- Cierre, reapertura, recierre.
- Fichas, PDFs y liquidaciones.
