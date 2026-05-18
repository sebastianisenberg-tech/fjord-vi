# Fjord VI 3.9.0-OPERATIONAL-RC1J

Release de refinamiento controlado de comunicaciones.

## Alcance

- Mejora asuntos y cuerpos de emails operativos para socios.
- Simplifica estados visibles en emails: Confirmado, En espera, Cancelado, No embarcó, Embarcado, Pendiente.
- Limpia duplicaciones como "Lista de espera / Lista de espera" y categorías repetidas de menores.
- Mantiene leyenda de modo prueba QA al final del mensaje.
- Unifica versión interna como `3.9.0-OPERATIONAL-RC1J`.

## No tocado

- Motor de reservas.
- Socio.
- Capitán.
- Cierres, reaperturas y recierres.
- Liquidaciones.
- PDFs.
- Scheduler/worker SMTP.
- Cola de emails.
- Delays y política de obsolescencia.
- Lógica reglamentaria.

## Rollback

Volver a `FjordVI_3.9.0_OPERATIONAL_RC1H_AUTO_WORKER_LOOP.zip` si se detecta cualquier problema operativo no textual.
