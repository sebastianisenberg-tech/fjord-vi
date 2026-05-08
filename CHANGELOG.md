# Changelog

## 1.7.3

- Robustness Guard transversal.
- Anti doble-submit en formularios desde frontend.
- `X-Fjord-Request-ID` para detectar acciones duplicadas.
- Middleware backend de bloqueo de POST duplicado por pocos segundos.
- Handler global de excepción para evitar pantallas blancas.
- Botones muestran `Procesando...` y se bloquean durante la acción.
- Recuperación automática al volver con botón atrás del navegador.
- Mensaje recuperable si una acción POST falla.
- Sin cambios en reglas de reservas, cargos, cierres ni QR.
