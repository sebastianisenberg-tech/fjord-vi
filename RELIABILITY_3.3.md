# Fjord VI v3.3 · Reliability & Usability Hardening

## Objetivo

Esta release no agrega una función visible principal. Endurece el sistema para que sea confiable, auditable y usable antes de cargar muchos datos reales.

## Principios

1. Ningún estado crítico debe depender solo de la interfaz.
2. Toda acción sensible debe ser validada por backend.
3. Los cierres, reaperturas, liquidaciones y cargos no se borran: se versionan o anulan con trazabilidad.
4. La UI debe explicar lo que está bloqueado y por qué.
5. El sistema debe ser fácil de usar o el usuario vuelve a WhatsApp, papel o Excel.

## Invariantes de negocio

- Ocupación nunca mayor a 9.
- Una sola ficha/liquidación vigente por salida.
- Un socio no debe duplicar reserva en la misma salida.
- Un invitado no debe duplicarse por DNI/documento en la misma salida.
- Un socio identificado no debe cargarse como invitado común.
- Reapertura debe dejar trazabilidad y anular ficha anterior si corresponde.
- Reserva incumplida no es navegación efectiva: es cargo reglamentario por plaza comprometida.
- SMTP en modo prueba no debe enviar a destinatarios reales.

## Checklist de piloto

- Login Socio, Capitán y Administración.
- Reserva de socio.
- Agregado de invitado.
- Lista de espera.
- Cancelación antes y después de T-48.
- Cierre por Capitán.
- Reapertura.
- Nueva ficha.
- PDF.
- SMTP test mode.
- Registro de mails.
- Mobile Android vertical.
- Desktop Administración.
- Versión visible única.

## Comando recomendado antes de deploy

```bash
python scripts/release_check.py
```
