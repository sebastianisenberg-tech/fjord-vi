FJORD VI v51.4.1 - REVISION INTEGRAL FINAL

Cambios aplicados:
- Version interna actualizada a v51.4.1.
- VERSION.txt sincronizado.
- Cache busting de CSS/JS actualizado en templates para evitar que Render/navegador sirvan archivos viejos.
- No se modifica logica de reservas, cancelaciones, reincorporacion, invitados, capitan, administracion, cargos, tooltips ni toasts.

Validacion:
- main.py compila.
- Templates Jinja parsean.
- app.js pasa node --check.
- /health responde.
- Login socio/capitan/admin redirige correctamente.
- /socio, /captain, /admin y /static/reglamento.html responden 200 en TestClient.
- Reglamento conserva Volver directo a /socio.
