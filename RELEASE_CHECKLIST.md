# Fjord VI · Checklist fija de release/deploy

Antes de considerar oficial un ZIP o deploy, correr primero:

```bash
python scripts/release_check.py
```

El release no debe considerarse apto si ese script falla.

Controles mínimos:

1. Versión unificada en `VERSION.txt`, `main.py`, `software_metadata.json` y `README.md`.
2. `compileall` OK sobre código principal.
3. No hay `__pycache__` ni `.pyc` en el paquete.
4. Templates críticos y static críticos presentes.
5. `render.yaml` y `software_metadata.json` presentes.
6. Manejo de `DATABASE_URL` previsto para producción.
7. Tests mínimos de negocio y release en verde.
8. Root, login, logout y cambio de clave siguen disponibles.
9. PostgreSQL y checks internos siguen visibles desde Sistema.
10. El ZIP final no contiene basura técnica evitable.
