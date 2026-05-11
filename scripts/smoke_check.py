"""Smoke check local para Fjord VI.
Uso: python scripts/smoke_check.py
No requiere base de datos. Verifica estructura, versión y archivos críticos.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "main.py", "requirements.txt", "Dockerfile", "VERSION.txt", "software_metadata.json",
    "templates/login.html", "templates/admin.html", "templates/socio.html", "templates/captain.html",
    "static/style.css", "static/app.js", "app/__init__.py",
]

errors = []
for item in REQUIRED:
    if not (ROOT / item).exists():
        errors.append(f"Falta archivo crítico: {item}")

version = (ROOT / "VERSION.txt").read_text().strip() if (ROOT / "VERSION.txt").exists() else ""
main = (ROOT / "main.py").read_text(errors="ignore") if (ROOT / "main.py").exists() else ""
if version and f'APP_VERSION = "{version}"' not in main:
    errors.append("La versión de VERSION.txt no coincide con APP_VERSION en main.py")

for forbidden in list(ROOT.rglob("__pycache__")) + list(ROOT.rglob("*.pyc")):
    errors.append(f"No subir cache Python: {forbidden.relative_to(ROOT)}")

if errors:
    print("SMOKE CHECK: FALLÓ")
    for e in errors:
        print("-", e)
    sys.exit(1)

print(f"SMOKE CHECK: OK · Fjord VI {version}")
