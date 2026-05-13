"""
Release check Fjord VI 3.3

Script de verificación estática para correr antes de deploy:
    python scripts/release_check.py

No requiere base de datos. Controla versión, templates, archivos críticos,
configuración SMTP segura y ausencia de basura común.
"""

from __future__ import annotations

import json
import py_compile
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "3.3"

CRITICAL_FILES = [
    "main.py",
    "VERSION.txt",
    "software_metadata.json",
    "templates/socio.html",
    "templates/admin.html",
    "templates/captain.html",
    "static/style.css",
]

REQUIRED_EMAIL_TEMPLATES = [
    "reserva_confirmada.html",
    "invitado_agregado.html",
    "lista_espera.html",
    "cancelacion_registrada.html",
    "reserva_incumplida.html",
    "recordatorio_24h.html",
    "embarque_cerrado_admin.html",
    "email_prueba.html",
]

def fail(msg: str, errors: list[str]) -> None:
    errors.append(msg)

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    for rel in CRITICAL_FILES:
        if not (ROOT / rel).exists():
            fail(f"Archivo crítico faltante: {rel}", errors)

    version_file = ROOT / "VERSION.txt"
    if version_file.exists():
        version = read(version_file).strip()
        if version != TARGET_VERSION:
            fail(f"VERSION.txt debe ser {TARGET_VERSION}, encontrado {version!r}", errors)

    metadata = ROOT / "software_metadata.json"
    if metadata.exists():
        try:
            data = json.loads(read(metadata))
            versions = [v for k, v in data.items() if "version" in k.lower()]
            if TARGET_VERSION not in [str(v) for v in versions]:
                fail("software_metadata.json no contiene versión objetivo.", errors)
        except Exception as exc:
            fail(f"software_metadata.json inválido: {exc}", errors)

    # Compile Python
    for py in ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            py_compile.compile(str(py), doraise=True)
        except Exception as exc:
            fail(f"Python no compila: {py.relative_to(ROOT)}: {exc}", errors)

    # Old visible versions
    old_refs = []
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix.lower() in {".py", ".html", ".css", ".js", ".json", ".txt", ".md"}:
            text = read(p)
            if re.search(r"\b(?:v?3\.0|v?3\.1|v?3\.2|v?2\.\d+)\b", text):
                old_refs.append(str(p.relative_to(ROOT)))
    if old_refs:
        fail("Referencias de versión viejas detectadas: " + ", ".join(sorted(set(old_refs))[:20]), errors)

    # Email templates
    email_dir = ROOT / "templates" / "emails"
    for tpl in REQUIRED_EMAIL_TEMPLATES:
        if not (email_dir / tpl).exists():
            fail(f"Template email faltante: {tpl}", errors)

    # SMTP safety defaults
    smtp_example = ROOT / "smtp_settings.example.json"
    if smtp_example.exists():
        try:
            smtp = json.loads(read(smtp_example))
            if smtp.get("smtp_enabled") is not False:
                fail("smtp_settings.example.json debe iniciar con smtp_enabled=false.", errors)
            if smtp.get("smtp_test_mode") is not True:
                fail("smtp_settings.example.json debe iniciar con smtp_test_mode=true.", errors)
            if smtp.get("smtp_force_redirect_in_test") is not True:
                fail("smtp_force_redirect_in_test debe iniciar true.", errors)
        except Exception as exc:
            fail(f"smtp_settings.example.json inválido: {exc}", errors)
    else:
        warnings.append("smtp_settings.example.json no encontrado.")

    # Garbage
    garbage = []
    for pattern in ("__pycache__", ".DS_Store", "Thumbs.db"):
        for p in ROOT.rglob(pattern):
            garbage.append(str(p.relative_to(ROOT)))
    if garbage:
        fail("Basura detectada: " + ", ".join(garbage[:20]), errors)

    print("Fjord VI release check", TARGET_VERSION)
    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(" -", w)
    if errors:
        print("ERRORES:")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
