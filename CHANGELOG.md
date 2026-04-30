# v37.0.0

- Versión plana definitiva.
- Elimina dependencia de `Jinja2Templates.TemplateResponse`, que estaba generando errores 500 opacos en Render.
- Agrega `SafeTemplates`, renderizador compatible con los HTML planos en raíz.
- Si una pantalla falla, devuelve error controlado visible en vez de Internal Server Error ciego.
- Mantiene estructura sin carpeta `templates` y sin HTML duplicados.
