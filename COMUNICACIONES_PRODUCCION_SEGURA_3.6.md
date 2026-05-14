Fjord VI v3.7.3.1 · Comunicaciones producción segura

Objetivo:
Cerrar el módulo de Comunicaciones con controles explícitos para prueba, simulación y producción real.

Incluye:
- Simulación visible.
- Producción real visible.
- Prueba real controlada al receptor de pruebas.
- Límite por corrida para evitar envíos accidentales masivos.
- Detalle persistente de validación SMTP: host, TLS, fecha/hora y resultado.
- Panel de advertencia de producción real.
- Semáforos ampliados.

Regla:
Antes de apagar Modo prueba o Redirect, validar SMTP, revisar eventos ON, revisar cola pendiente y confirmar límite por corrida.
