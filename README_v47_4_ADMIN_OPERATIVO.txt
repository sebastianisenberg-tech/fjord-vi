Fjord VI v47.4 ADMIN OPERATIVO PROBADO

Base: v47.1 funcional.
Cambios:
- ZIP completo, no archivo suelto.
- Administración vuelve a usar backend real y formularios reales.
- Menú lateral usa /admin?page=... servido por FastAPI/Jinja.
- Versión visible arriba: v47.4.
- Capitán/Socio no fueron tocados.
- Probado con TestClient: login admin y páginas de admin principales devuelven 200.

Subir el ZIP completo con deploy limpio, no mezclar con archivos sueltos anteriores.
