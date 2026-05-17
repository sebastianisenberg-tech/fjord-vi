from __future__ import annotations
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET_VERSION = "RC8_EMAIL_HTML_FIX3"

CRITICAL = [
    "main.py",
    "VERSION.txt",
    "software_metadata.json",
    "templates/socio.html",
    "templates/admin.html",
    "templates/captain.html",
    "static/style.css",
]

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")

def main() -> int:
    errors = []

    for rel in CRITICAL:
        if not (ROOT / rel).exists():
            errors.append(f"Archivo crítico faltante: {rel}")

    vf = ROOT / "VERSION.txt"
    if vf.exists() and read(vf).strip() != TARGET_VERSION:
        errors.append(f"VERSION.txt no coincide: {read(vf).strip()}")

    meta = ROOT / "software_metadata.json"
    if meta.exists():
        try:
            data = json.loads(read(meta))
            vals = [str(v) for k,v in data.items() if "version" in k.lower()]
            if TARGET_VERSION not in vals:
                errors.append("software_metadata.json no contiene versión RC8_EMAIL_HTML_FIX3")
        except Exception as e:
            errors.append(f"software_metadata.json inválido: {e}")

    for py in ROOT.rglob("*.py"):
        if "__pycache__" in str(py):
            continue
        try:
            compile(read(py), str(py), "exec")
        except Exception as e:
            errors.append(f"Python no compila {py.relative_to(ROOT)}: {e}")

    # SMTP safety defaults
    smtp = ROOT / "smtp_settings.example.json"
    if smtp.exists():
        try:
            data = json.loads(read(smtp))
            if data.get("smtp_enabled") is not False:
                errors.append("smtp_enabled debe iniciar false")
            if data.get("smtp_test_mode") is not True:
                errors.append("smtp_test_mode debe iniciar true")
            if data.get("smtp_force_redirect_in_test") is not True:
                errors.append("smtp_force_redirect_in_test debe iniciar true")
        except Exception as e:
            errors.append(f"smtp_settings.example.json inválido: {e}")

    garbage = []
    for pat in ("__pycache__", ".DS_Store", "Thumbs.db"):
        garbage += [str(p.relative_to(ROOT)) for p in ROOT.rglob(pat)]
    if garbage:
        errors.append("Basura detectada: " + ", ".join(garbage[:10]))

    print("Fjord VI release check", TARGET_VERSION)
    if errors:
        print("ERRORES:")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0

if __name__ == "__main__":
    sys.exit(main())
